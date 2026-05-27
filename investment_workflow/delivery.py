from __future__ import annotations

import json
from datetime import timedelta, timezone
from urllib.request import Request, urlopen

from .config import FeishuConfig
from .models import WorkflowReport


BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def format_beijing_timestamp(report: WorkflowReport) -> str:
    return report.generated_at.astimezone(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M 北京时间")


def build_feishu_message(report: WorkflowReport) -> dict[str, object]:
    title = f"投资结论简报 {format_beijing_timestamp(report)}"
    body = (
        f"{title}\n\n"
        f"{report.final_markdown}\n\n"
        f"事件数: {report.articles_collected}"
    )
    return {
        "msg_type": "text",
        "content": {
            "text": body[:30000],
        },
    }


def send_to_feishu(config: FeishuConfig, report: WorkflowReport, timeout: int) -> None:
    payload = json.dumps(build_feishu_message(report), ensure_ascii=False).encode("utf-8")
    request = Request(
        config.webhook_url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        raw_body = response.read().decode("utf-8", errors="replace")

    try:
        result = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unexpected Feishu response: {raw_body!r}") from exc

    if result.get("code") not in (0, None):
        raise RuntimeError(f"Feishu webhook rejected the message: {result}")
