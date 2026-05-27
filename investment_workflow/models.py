from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class NewsItem:
    title: str
    link: str
    source: str
    published_at: datetime
    summary: str
    query: str
    themes: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    horizon: str = "medium"
    risk_level: str = "medium"
    score: float = 0.0
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        return payload


@dataclass(slots=True)
class ThemeSignal:
    name: str
    score: float
    direction: str
    industries: list[str]
    assets: list[str]
    reasons: list[str]
    supporting_items: list[NewsItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "direction": self.direction,
            "industries": self.industries,
            "assets": self.assets,
            "reasons": self.reasons,
            "supporting_items": [item.to_dict() for item in self.supporting_items],
        }


@dataclass(slots=True)
class StructuredConclusion:
    overall_judgment: str
    best_directions: list[str]
    avoid_directions: list[str]
    watchlist: list[str]
    conservative_strategy: str
    balanced_strategy: str
    aggressive_strategy: str
    single_action: str
    major_risks: list[str]
    confidence: str
    rationale: list[str]
    collection_warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowReport:
    generated_at: datetime
    articles_collected: int
    signals: list[ThemeSignal]
    conclusion: StructuredConclusion
    final_markdown: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "articles_collected": self.articles_collected,
            "signals": [signal.to_dict() for signal in self.signals],
            "conclusion": self.conclusion.to_dict(),
            "final_markdown": self.final_markdown,
        }
