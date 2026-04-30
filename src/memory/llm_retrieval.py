"""LLM-backed retrieval over local Markdown work memories.

This module implements the project's RAG-like read path without embeddings or
vector stores: local Markdown layers are chunked, each chunk is scored by an
LLM, and the top evidence chunks can optionally be used to synthesize an
answer.
"""

from dataclasses import dataclass, field
import hashlib
import json
import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:
    import memory_manager
except ImportError:  # pragma: no cover - package-only deployments may omit it
    memory_manager = None

logger = logging.getLogger(__name__)


DEFAULT_TOP_K = 5
DEFAULT_MAX_CHUNK_CHARS = 2400
DEFAULT_MAX_PROMPT_CHARS = 24000
DEFAULT_MAX_RESULT_CHARS = 4000


@dataclass
class RetrievalChunk:
    """A searchable Markdown chunk from one memory layer."""

    index: int
    chunk_id: str
    work_id: str
    layer_id: str
    layer_name: str
    layer_file: str
    heading_path: List[str]
    content: str

    def prompt_text(self, local_index: int) -> str:
        heading = " / ".join(self.heading_path) if self.heading_path else "（无标题）"
        return (
            f"[{local_index}]\n"
            f"层: {self.layer_name} ({self.layer_id})\n"
            f"标题路径: {heading}\n"
            f"内容:\n{self.content.strip()}"
        )


@dataclass
class RetrievalHit:
    """One ranked result produced by LLM retrieval."""

    chunk: RetrievalChunk
    score: float
    reason: str = ""
    matched_facts: List[str] = field(default_factory=list)

    def to_dict(self, rank: int, include_content: bool, max_result_chars: int) -> Dict[str, Any]:
        content = self.chunk.content.strip()
        clipped = _clip(content, max_result_chars)
        payload = {
            "rank": rank,
            "score": self.score,
            "reason": self.reason,
            "matched_facts": list(self.matched_facts),
            "chunk_id": self.chunk.chunk_id,
            "layer_id": self.chunk.layer_id,
            "layer_name": self.chunk.layer_name,
            "layer_file": self.chunk.layer_file,
            "heading_path": list(self.chunk.heading_path),
            "excerpt": clipped,
            "content_truncated": len(content) > len(clipped),
        }
        if include_content:
            payload["content"] = clipped
        return payload


@dataclass
class RetrievalRun:
    """Structured result returned by :class:`LLMWorkRetriever`."""

    work_id: str
    query: str
    hits: List[RetrievalHit]
    answer: str = ""
    answer_error: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(
        self,
        include_content: bool = True,
        max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
    ) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "query": self.query,
            "answer": self.answer,
            "answer_error": self.answer_error,
            "results": [
                hit.to_dict(index + 1, include_content, max_result_chars)
                for index, hit in enumerate(self.hits)
            ],
            "stats": dict(self.stats),
            "errors": list(self.errors),
        }


class LLMWorkRetriever:
    """Retrieve relevant local Markdown memory chunks with an LLM scorer."""

    def __init__(
        self,
        llm: Callable[[str], str],
        *,
        max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    ):
        if memory_manager is None:
            raise RuntimeError("memory_manager module is required")
        self.llm = llm
        self.max_prompt_chars = max(4000, int(max_prompt_chars or DEFAULT_MAX_PROMPT_CHARS))

    def retrieve(
        self,
        *,
        work_id: str,
        query: str,
        layer_ids: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        include_answer: bool = False,
        answer_instructions: str = "",
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        min_score: float = 0.0,
    ) -> RetrievalRun:
        """Run LLM retrieval over selected work layers.

        The method is read-only. It never mutates work memory files.
        """

        query = str(query or "").strip()
        if not query:
            raise ValueError("query is required")
        top_k = max(0, int(top_k or DEFAULT_TOP_K))
        if top_k <= 0:
            return RetrievalRun(work_id=work_id, query=query, hits=[], stats={"top_k": 0})

        chunks = self._load_chunks(
            work_id=work_id,
            layer_ids=layer_ids,
            max_chunk_chars=max_chunk_chars,
        )
        errors: List[str] = []
        scored_hits: List[RetrievalHit] = []
        llm_calls = 0

        for batch in self._batch_chunks(chunks):
            try:
                llm_calls += 1
                batch_hits = self._score_batch(query, batch, top_k)
                scored_hits.extend(batch_hits)
            except Exception as exc:
                message = f"LLM retrieval batch failed: {exc}"
                logger.warning(message)
                errors.append(message)
                raise RuntimeError(message) from exc

        deduped = self._dedupe_hits(scored_hits)
        filtered = [hit for hit in deduped if hit.score >= min_score]
        filtered.sort(key=lambda hit: hit.score, reverse=True)
        hits = filtered[:top_k]

        answer = ""
        answer_error = ""
        if include_answer and hits:
            try:
                answer = self._generate_answer(
                    query=query,
                    hits=hits,
                    answer_instructions=answer_instructions,
                )
            except Exception as exc:
                message = f"LLM answer generation failed: {exc}"
                logger.warning(message)
                raise RuntimeError(message) from exc

        return RetrievalRun(
            work_id=work_id,
            query=query,
            hits=hits,
            answer=answer,
            answer_error=answer_error,
            stats={
                "candidate_count": len(chunks),
                "scored_count": len(scored_hits),
                "returned_count": len(hits),
                "llm_calls": llm_calls,
                "top_k": top_k,
                "target_layers": layer_ids or [
                    layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS
                ],
                "max_chunk_chars": max_chunk_chars,
                "max_prompt_chars": self.max_prompt_chars,
                "retrieval_mode": "llm",
            },
            errors=errors,
        )

    def _load_chunks(
        self,
        *,
        work_id: str,
        layer_ids: Optional[List[str]],
        max_chunk_chars: int,
    ) -> List[RetrievalChunk]:
        valid_ids = {layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS}
        selected = layer_ids or [layer["layer_id"] for layer in memory_manager.LAYER_DEFINITIONS]
        normalized_layers: List[str] = []
        for layer_id in selected:
            if layer_id in valid_ids and layer_id not in normalized_layers:
                normalized_layers.append(layer_id)
        if not normalized_layers:
            raise ValueError("no valid target layers")

        chunks: List[RetrievalChunk] = []
        for layer_id in normalized_layers:
            layer = memory_manager.get_layer_content(work_id, layer_id)
            content = (layer.get("content") or "").strip()
            if not content:
                continue
            layer_chunks = _split_markdown(
                content,
                max_chunk_chars=max(600, int(max_chunk_chars or DEFAULT_MAX_CHUNK_CHARS)),
            )
            for heading_path, chunk_text in layer_chunks:
                chunk_index = len(chunks)
                chunk_id = _chunk_id(work_id, layer_id, chunk_index, chunk_text)
                chunks.append(
                    RetrievalChunk(
                        index=chunk_index,
                        chunk_id=chunk_id,
                        work_id=work_id,
                        layer_id=layer_id,
                        layer_name=layer["layer_name"],
                        layer_file=layer["layer_file"],
                        heading_path=heading_path,
                        content=chunk_text,
                    )
                )
        return chunks

    def _batch_chunks(self, chunks: List[RetrievalChunk]) -> Iterable[List[RetrievalChunk]]:
        prompt_overhead = 2600
        budget = max(1200, self.max_prompt_chars - prompt_overhead)
        batch: List[RetrievalChunk] = []
        batch_chars = 0
        for chunk in chunks:
            rendered_len = len(chunk.prompt_text(len(batch)))
            if batch and batch_chars + rendered_len > budget:
                yield batch
                batch = []
                batch_chars = 0
                rendered_len = len(chunk.prompt_text(0))
            batch.append(chunk)
            batch_chars += rendered_len
        if batch:
            yield batch

    def _score_batch(
        self,
        query: str,
        batch: List[RetrievalChunk],
        top_k: int,
    ) -> List[RetrievalHit]:
        prompt = _build_retrieval_prompt(query, batch, top_k=min(top_k, len(batch)))
        raw = self.llm(prompt)
        data = _parse_json_object(raw)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("LLM response does not contain a results array")

        hits: List[RetrievalHit] = []
        for item in data["results"]:
            if not isinstance(item, dict):
                raise ValueError(f"LLM result item must be an object: {item!r}")
            if "index" not in item:
                raise ValueError(f"LLM result item missing index: {item!r}")
            try:
                local_index = int(item.get("index"))
            except Exception as exc:
                raise ValueError(f"LLM result item has invalid index: {item!r}") from exc
            if local_index < 0 or local_index >= len(batch):
                raise ValueError(f"LLM result index out of range: {local_index}")
            if "relevance_score" in item:
                raw_score = item["relevance_score"]
            elif "score" in item:
                raw_score = item["score"]
            else:
                raise ValueError(f"LLM result item missing relevance_score: {item!r}")
            score = _parse_score(raw_score)
            reason = str(item.get("reason") or item.get("explanation") or "").strip()
            matched_facts = item.get("matched_facts") or item.get("facts") or []
            if isinstance(matched_facts, str):
                matched_facts = [matched_facts]
            if not isinstance(matched_facts, list):
                matched_facts = []
            hits.append(
                RetrievalHit(
                    chunk=batch[local_index],
                    score=score,
                    reason=reason,
                    matched_facts=[str(value) for value in matched_facts[:5]],
                )
            )
        return hits

    def _generate_answer(
        self,
        *,
        query: str,
        hits: List[RetrievalHit],
        answer_instructions: str,
    ) -> str:
        context = "\n\n".join(
            [
                (
                    f"[证据 {index + 1}] "
                    f"{hit.chunk.layer_name} / "
                    f"{' / '.join(hit.chunk.heading_path) or '无标题'}\n"
                    f"{hit.chunk.content.strip()}"
                )
                for index, hit in enumerate(hits)
            ]
        )
        instructions = answer_instructions.strip() or (
            "请只基于检索片段回答用户问题；如果片段不足以确认，请明确标注“待人工确认”。"
        )
        prompt = f"""# 本地记忆问答任务

## 用户问题
{query}

## 检索片段
{context}

## 回答要求
{instructions}

请直接输出最终答案，不要输出检索过程，不要编造检索片段中没有的事实。
"""
        return _strip_act_prefix(str(self.llm(prompt)).strip())

    def _dedupe_hits(self, hits: List[RetrievalHit]) -> List[RetrievalHit]:
        by_chunk: Dict[str, RetrievalHit] = {}
        for hit in hits:
            current = by_chunk.get(hit.chunk.chunk_id)
            if current is None or hit.score > current.score:
                by_chunk[hit.chunk.chunk_id] = hit
        return list(by_chunk.values())


def _build_retrieval_prompt(
    query: str,
    batch: List[RetrievalChunk],
    top_k: int,
) -> str:
    candidates = "\n\n".join(
        chunk.prompt_text(local_index)
        for local_index, chunk in enumerate(batch)
    )
    return f"""# LLM 本地文档检索任务

你是 pm-mem 的检索器。请阅读本批本地 Markdown 记忆片段，判断哪些片段最能回答用户查询。

## 用户查询
{query}

## 本批候选片段
{candidates}

## 输出要求
只输出一个 JSON 对象，不要使用 Markdown 代码块，不要添加解释性前后缀。
JSON 格式如下：
{{
  "results": [
    {{
      "index": 0,
      "relevance_score": 0.95,
      "reason": "该片段直接包含查询所需的人物关系或情节事实",
      "matched_facts": ["可选，列出命中的关键事实"]
    }}
  ]
}}

规则：
1. index 必须使用本批候选片段中的方括号编号。
2. relevance_score 是 0.0 到 1.0 的数字，1.0 表示可直接回答查询。
3. 最多返回本批最相关的 {top_k} 个片段，按相关性从高到低排列。
4. 不要返回与查询无关的片段；如果没有相关片段，返回 {{"results": []}}。
5. 不要编造候选片段以外的事实。
"""


def _split_markdown(content: str, max_chunk_chars: int) -> List[Tuple[List[str], str]]:
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    chunks: List[Tuple[List[str], str]] = []
    stack: List[str] = []
    current_lines: List[str] = []
    current_path: List[str] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if not text:
            return
        for part in _split_long_text(text, max_chunk_chars):
            chunks.append((list(current_path), part))

    for line in content.splitlines():
        match = heading_re.match(line)
        if match and current_lines:
            flush()
            current_lines = []
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            while len(stack) >= level:
                stack.pop()
            stack.append(title)
            current_path = list(stack)
        current_lines.append(line)
    flush()
    if not chunks and content.strip():
        return [([], part) for part in _split_long_text(content.strip(), max_chunk_chars)]
    return chunks


def _split_long_text(text: str, max_chars: int) -> List[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    parts: List[str] = []
    current: List[str] = []
    current_len = 0
    paragraphs = re.split(r"\n\s*\n", text)
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if current:
                parts.append("\n\n".join(current).strip())
                current = []
                current_len = 0
            parts.extend(_hard_wrap(paragraph, max_chars))
            continue
        if current and current_len + len(paragraph) + 2 > max_chars:
            parts.append("\n\n".join(current).strip())
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        parts.append("\n\n".join(current).strip())
    return parts or [text[:max_chars]]


def _hard_wrap(text: str, max_chars: int) -> List[str]:
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _parse_json_object(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        cleaned = (
            candidate.strip()
            .replace("…", "")
            .replace(",\n}", "\n}")
            .replace(",\n]", "\n]")
        )
        try:
            data = json.loads(cleaned)
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return None


def _parse_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception as exc:
        raise ValueError(f"invalid relevance score: {value!r}") from exc
    if not (0.0 <= score <= 1.0):
        raise ValueError(f"relevance score out of range [0.0, 1.0]: {score}")
    return round(score, 2)


def _chunk_id(work_id: str, layer_id: str, index: int, content: str) -> str:
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    return f"{work_id}:{layer_id}:{index}:{digest}"


def _clip(text: str, limit: int) -> str:
    text = str(text or "")
    if limit <= 0 or len(text) <= limit:
        return text
    half = max(1, (limit - 20) // 2)
    return f"{text[:half]}\n...（中间省略）...\n{text[-half:]}"


def _strip_act_prefix(value: str) -> str:
    text = value.strip()
    return text[4:].strip() if text.startswith("Act:") else text
