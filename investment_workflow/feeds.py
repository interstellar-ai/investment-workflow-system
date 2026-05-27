from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .config import WorkflowConfig
from .models import NewsItem


USER_AGENT = "investment-workflow-system/1.0"


def _parse_published_at(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_rss_items(query: str, url: str, timeout: int) -> list[NewsItem]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()

    root = ElementTree.fromstring(payload)
    items: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        summary = unescape((item.findtext("description") or "").strip())
        source = (item.findtext("source") or "Google News").strip()
        published_at = _parse_published_at(item.findtext("pubDate"))
        if not title or not link:
            continue
        items.append(
            NewsItem(
                title=title,
                link=link,
                source=source,
                published_at=published_at,
                summary=summary,
                query=query,
            )
        )
    return items


def deduplicate_items(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen: set[tuple[str, str]] = set()
    unique_items: list[NewsItem] = []
    for item in sorted(items, key=lambda entry: entry.published_at, reverse=True):
        key = (" ".join(item.title.lower().split()), item.link.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def collect_news(config: WorkflowConfig) -> tuple[list[NewsItem], list[str]]:
    collected: list[NewsItem] = []
    warnings: list[str] = []

    for query, url in config.google_news_urls():
        try:
            items = fetch_rss_items(query, url, config.request_timeout_seconds)
        except Exception as exc:
            warnings.append(f"Failed to fetch query '{query}': {exc}")
            continue
        collected.extend(items[: config.max_articles_per_query])

    unique_items = deduplicate_items(collected)
    return unique_items[: config.max_articles_total], warnings
