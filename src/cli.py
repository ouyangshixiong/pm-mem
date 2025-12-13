import argparse
import os
from typing import Optional
import dotenv
from src.agent.remem_agent import ReMemAgent

dotenv.load_dotenv()


def _create_llm(provider: Optional[str]):
    if provider == "mock":
        from src.llm.mock_llm import MockLLM

        return MockLLM()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        from src.llm.mock_llm import MockLLM

        return MockLLM()

    timeout_env = os.getenv("LLM_TIMEOUT")
    max_retries_env = os.getenv("LLM_MAX_RETRIES")
    kwargs = {}
    if timeout_env:
        try:
            kwargs["timeout"] = int(timeout_env)
        except ValueError:
            pass
    if max_retries_env:
        try:
            kwargs["max_retries"] = int(max_retries_env)
        except ValueError:
            pass

    from src.llm.deepseek_client import DeepSeekClient

    return DeepSeekClient.from_env(**kwargs)


def _run_single_task(args: argparse.Namespace) -> int:
    llm = _create_llm(args.llm)
    agent = ReMemAgent(
        llm=llm,
        persist_path=args.persist,
        max_iterations=args.max_iterations,
        retrieval_k=args.retrieval_k,
    )
    result = agent.run_task(args.task)
    print(result["action"])
    return 0


def _interactive(args: argparse.Namespace) -> int:
    llm = _create_llm(args.llm)
    agent = ReMemAgent(
        llm=llm,
        persist_path=args.persist,
        max_iterations=args.max_iterations,
        retrieval_k=args.retrieval_k,
    )
    print("pm-mem 交互模式，输入任务，Ctrl-C 退出")
    while True:
        try:
            task = input("> ").strip()
            if not task:
                continue
            result = agent.run_task(task)
            print(result["action"])
        except KeyboardInterrupt:
            print("\n退出")
            break
    return 0


def _demo(_: argparse.Namespace) -> int:
    from examples.basic_usage import basic_usage_example

    basic_usage_example()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pm-mem")
    subparsers = parser.add_subparsers(dest="cmd")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--llm", choices=["mock", "deepseek"], default=None)
    common.add_argument("--persist", default="./data/memory.json")
    common.add_argument("--max-iterations", type=int, default=8)
    common.add_argument("--retrieval-k", type=int, default=5)

    p_run = subparsers.add_parser("run", parents=[common])
    p_run.add_argument("--task", required=True)
    p_run.set_defaults(func=_run_single_task)

    p_inter = subparsers.add_parser("interactive", parents=[common])
    p_inter.set_defaults(func=_interactive)

    p_demo = subparsers.add_parser("demo")
    p_demo.set_defaults(func=_demo)

    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        args.cmd = "interactive"
        args.func = _interactive
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
