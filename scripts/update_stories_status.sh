#!/bin/bash

[ -f .env ] && set -a && . ./.env && set +a
source ./venv/bin/activate 2>/dev/null || true

# JIRA配置
JIRA_DOMAIN="${JIRA_DOMAIN:-ouyangshixiong.atlassian.net}"
EMAIL="${ATLASSIAN_EMAIL:-}"
API_TOKEN="${ATLASSIAN_API_TOKEN:-}"
[ -z "$EMAIL" ] && echo "Missing ATLASSIAN_EMAIL" >&2 && exit 1
[ -z "$API_TOKEN" ] && echo "Missing ATLASSIAN_API_TOKEN" >&2 && exit 1

# Story列表
STORIES=("PM-23" "PM-24" "PM-25" "PM-26" "PM-27" "PM-28" "PM-29" "PM-30")

echo "开始批量更新Story状态为In Progress..."

for STORY in "${STORIES[@]}"; do
    echo "处理Story: $STORY"

    # 更新状态为In Progress (transition ID: 21)
    curl -u "$EMAIL:$API_TOKEN" -X POST \
      -H "Content-Type: application/json" \
      "https://$JIRA_DOMAIN/rest/api/3/issue/$STORY/transitions" \
      -d '{"transition":{"id":"21"}}'

    # 添加进度评论
    curl -u "$EMAIL:$API_TOKEN" -X POST \
      -H "Content-Type: application/json" \
      "https://$JIRA_DOMAIN/rest/api/3/issue/$STORY/comment" \
      -d '{"body":{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"2025-12-12 11:45 CST: Scrum Master Agent开始协调Sprint 5开发。Story状态已更新为In Progress，即将协调Development Team Agent执行开发任务。"}]}]}}'

    echo "完成Story: $STORY"
    echo "---"
done

echo "所有Story状态更新完成！"
