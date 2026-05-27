from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus


DEFAULT_NEWS_QUERIES = [
    "artificial intelligence",
    "semiconductor",
    "cloud computing",
    "cybersecurity",
    "energy transition",
    "biotech",
    "federal reserve",
    "geopolitics",
    "supply chain",
]


@dataclass(slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(slots=True)
class FeishuConfig:
    webhook_url: str


@dataclass(slots=True)
class WorkflowConfig:
    news_queries: list[str]
    max_articles_per_query: int
    max_articles_total: int
    request_timeout_seconds: int
    delivery_modes: list[str]
    output_dir: Path
    feishu: FeishuConfig | None
    llm: LLMConfig | None

    def google_news_urls(self) -> list[tuple[str, str]]:
        urls: list[tuple[str, str]] = []
        for query in self.news_queries:
            encoded_query = quote_plus(query)
            url = (
                "https://news.google.com/rss/search"
                f"?q={encoded_query}+when:7d&hl=en-US&gl=US&ceid=US:en"
            )
            urls.append((query, url))
        return urls


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_list(value: str | None, default: Iterable[str]) -> list[str]:
    if value is None or not value.strip():
        return list(default)
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0, got {value}")
    return value


def _parse_llm_config() -> LLMConfig | None:
    base_url = os.getenv("LLM_API_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    provided = [bool(base_url), bool(api_key), bool(model)]
    if any(provided) and not all(provided):
        raise ValueError(
            "LLM_API_BASE_URL, LLM_API_KEY, and LLM_MODEL must all be set together."
        )
    if not any(provided):
        return None
    return LLMConfig(base_url=base_url.rstrip("/"), api_key=api_key, model=model)


def _parse_delivery_modes() -> list[str]:
    raw_value = os.getenv("DELIVERY_MODE", "file")
    values = [part.strip().lower() for part in raw_value.split(",") if part.strip()]
    if not values:
        values = ["file"]

    allowed = {"file", "stdout", "feishu"}
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ValueError(
            "DELIVERY_MODE supports only 'file', 'stdout', and 'feishu', "
            f"got invalid values: {', '.join(invalid)}."
        )
    return values


def _parse_feishu_config(delivery_modes: list[str]) -> FeishuConfig | None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if "feishu" in delivery_modes and not webhook_url:
        raise ValueError("FEISHU_WEBHOOK_URL must be set when DELIVERY_MODE includes 'feishu'.")
    if not webhook_url:
        return None
    return FeishuConfig(webhook_url=webhook_url)


def load_config(project_root: Path) -> WorkflowConfig:
    load_dotenv(project_root / ".env")

    delivery_modes = _parse_delivery_modes()

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    return WorkflowConfig(
        news_queries=_parse_list(os.getenv("NEWS_QUERIES"), DEFAULT_NEWS_QUERIES),
        max_articles_per_query=_parse_int("MAX_ARTICLES_PER_QUERY", 8),
        max_articles_total=_parse_int("MAX_ARTICLES_TOTAL", 30),
        request_timeout_seconds=_parse_int("REQUEST_TIMEOUT_SECONDS", 20),
        delivery_modes=delivery_modes,
        output_dir=output_dir,
        feishu=_parse_feishu_config(delivery_modes),
        llm=_parse_llm_config(),
    )
