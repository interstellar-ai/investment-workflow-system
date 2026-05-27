from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import fabs

from .config import WorkflowConfig
from .feeds import collect_news
from .models import NewsItem, StructuredConclusion, ThemeSignal, WorkflowReport
from .providers import OpenAICompatibleSummarizer
from .renderers import render_structured_markdown


POSITIVE_KEYWORDS = {
    "beat",
    "beats",
    "approval",
    "approved",
    "launch",
    "partnership",
    "growth",
    "expansion",
    "record",
    "strong",
    "subsidy",
    "funding",
    "breakthrough",
    "surge",
    "investment",
    "orders",
}

NEGATIVE_KEYWORDS = {
    "ban",
    "probe",
    "investigation",
    "delay",
    "cut",
    "cuts",
    "weak",
    "miss",
    "risk",
    "tariff",
    "lawsuit",
    "hack",
    "attack",
    "conflict",
    "shortage",
    "downgrade",
    "recall",
}

THEME_DEFINITIONS = {
    "AI infrastructure": {
        "keywords": {"ai", "gpu", "datacenter", "model", "inference", "compute"},
        "industries": ["AI", "Cloud", "Semiconductors"],
        "assets": ["US growth equities", "Semiconductor leaders"],
        "weight": 1.35,
    },
    "Semiconductor cycle": {
        "keywords": {"semiconductor", "chip", "wafer", "foundry", "memory", "fab"},
        "industries": ["Semiconductors", "Equipment"],
        "assets": ["Chipmakers", "Semiconductor equipment"],
        "weight": 1.25,
    },
    "Cloud software": {
        "keywords": {"cloud", "saas", "software", "enterprise", "subscription"},
        "industries": ["Software", "Cloud"],
        "assets": ["Large-cap software", "Cloud platforms"],
        "weight": 1.1,
    },
    "Cybersecurity": {
        "keywords": {"cybersecurity", "cyber", "breach", "security", "ransomware", "hack"},
        "industries": ["Cybersecurity"],
        "assets": ["Security software", "Defensive tech"],
        "weight": 1.05,
    },
    "Energy transition": {
        "keywords": {"battery", "solar", "wind", "grid", "power", "energy", "utility"},
        "industries": ["Utilities", "Industrial electrification", "Renewables"],
        "assets": ["Grid equipment", "Utilities", "Energy transition equities"],
        "weight": 1.1,
    },
    "Biotech and healthcare": {
        "keywords": {"biotech", "drug", "trial", "fda", "therapy", "healthcare"},
        "industries": ["Biotech", "Healthcare"],
        "assets": ["Biotech innovators", "Healthcare defensives"],
        "weight": 1.0,
    },
    "Rates and liquidity": {
        "keywords": {"federal reserve", "inflation", "rate", "yields", "liquidity", "treasury"},
        "industries": ["Financials", "Rate-sensitive growth"],
        "assets": ["US equities", "Treasuries", "Dollar-sensitive assets"],
        "weight": 1.2,
    },
    "Geopolitics and trade": {
        "keywords": {"tariff", "geopolitics", "sanction", "war", "trade", "conflict"},
        "industries": ["Industrials", "Exporters", "Global supply chain"],
        "assets": ["Global cyclicals", "Safe havens", "Oil"],
        "weight": 1.3,
    },
    "Supply chain resilience": {
        "keywords": {"supply chain", "shipping", "logistics", "inventory", "port", "freight"},
        "industries": ["Logistics", "Industrials", "Manufacturing"],
        "assets": ["Industrial automation", "Transport", "Regional manufacturers"],
        "weight": 1.05,
    },
}


def _normalize_text(item: NewsItem) -> str:
    return " ".join(
        (item.title + " " + item.summary + " " + item.query).lower().replace("/", " ").split()
    )


def _match_themes(text: str) -> list[str]:
    matched: list[str] = []
    for theme_name, definition in THEME_DEFINITIONS.items():
        if any(keyword in text for keyword in definition["keywords"]):
            matched.append(theme_name)
    return matched or ["Broad market"]


def _score_sentiment(text: str) -> tuple[str, float, list[str]]:
    positive_hits = sorted(keyword for keyword in POSITIVE_KEYWORDS if keyword in text)
    negative_hits = sorted(keyword for keyword in NEGATIVE_KEYWORDS if keyword in text)
    reasons: list[str] = []
    if positive_hits:
        reasons.append(f"positive catalysts: {', '.join(positive_hits[:3])}")
    if negative_hits:
        reasons.append(f"negative catalysts: {', '.join(negative_hits[:3])}")

    score = float(len(positive_hits) - len(negative_hits))
    if score > 0:
        return "positive", score, reasons
    if score < 0:
        return "negative", score, reasons
    return "neutral", 0.25, ["signal is mostly informational rather than directional"]


def _infer_horizon(text: str) -> str:
    if any(keyword in text for keyword in {"today", "this week", "guidance", "quarter", "earnings"}):
        return "short"
    if any(keyword in text for keyword in {"buildout", "investment", "policy", "roadmap", "capacity"}):
        return "long"
    return "medium"


def _infer_risk_level(sentiment: str, text: str) -> str:
    if sentiment == "negative" and any(keyword in text for keyword in {"war", "hack", "tariff", "ban"}):
        return "high"
    if sentiment == "positive":
        return "medium"
    return "low"


def enrich_items(items: list[NewsItem]) -> list[NewsItem]:
    now = datetime.now(timezone.utc)
    for item in items:
        text = _normalize_text(item)
        matched_themes = _match_themes(text)
        sentiment, sentiment_score, reasons = _score_sentiment(text)

        industries: list[str] = []
        assets: list[str] = []
        theme_weight = 1.0
        for theme_name in matched_themes:
            definition = THEME_DEFINITIONS.get(theme_name)
            if definition is None:
                continue
            industries.extend(definition["industries"])
            assets.extend(definition["assets"])
            theme_weight = max(theme_weight, float(definition["weight"]))

        age_hours = max(1.0, (now - item.published_at).total_seconds() / 3600)
        recency_weight = max(0.55, 1.4 - min(age_hours, 96.0) / 120.0)
        base_score = max(fabs(sentiment_score), 0.75)
        signed_score = base_score * theme_weight * recency_weight
        if sentiment == "negative":
            signed_score *= -1

        item.themes = matched_themes
        item.industries = sorted(set(industries))
        item.assets = sorted(set(assets))
        item.sentiment = sentiment
        item.horizon = _infer_horizon(text)
        item.risk_level = _infer_risk_level(sentiment, text)
        item.score = round(signed_score, 2)
        item.rationale = reasons
    return items


def _build_theme_signals(items: list[NewsItem]) -> list[ThemeSignal]:
    grouped: dict[str, list[NewsItem]] = defaultdict(list)
    for item in items:
        for theme in item.themes:
            grouped[theme].append(item)

    signals: list[ThemeSignal] = []
    for theme_name, grouped_items in grouped.items():
        total_score = round(sum(item.score for item in grouped_items), 2)
        direction = "positive" if total_score > 0.8 else "negative" if total_score < -0.8 else "mixed"
        industries = sorted({industry for item in grouped_items for industry in item.industries})
        assets = sorted({asset for item in grouped_items for asset in item.assets})
        reasons: list[str] = []
        for item in grouped_items[:3]:
            if item.rationale:
                reasons.extend(item.rationale[:1])
        if not reasons:
            reasons.append("signal cluster has limited directional evidence")
        signals.append(
            ThemeSignal(
                name=theme_name,
                score=total_score,
                direction=direction,
                industries=industries,
                assets=assets,
                reasons=reasons[:3],
                supporting_items=sorted(
                    grouped_items,
                    key=lambda entry: abs(entry.score),
                    reverse=True,
                )[:3],
            )
        )
    return sorted(signals, key=lambda signal: abs(signal.score), reverse=True)


def _signal_label(signal: ThemeSignal) -> str:
    focus = signal.assets[0] if signal.assets else signal.name
    return f"{signal.name} -> {focus}"


def build_conclusion(signals: list[ThemeSignal], warnings: list[str]) -> StructuredConclusion:
    positive_signals = [signal for signal in signals if signal.score > 0.8]
    negative_signals = [signal for signal in signals if signal.score < -0.8]
    mixed_signals = [signal for signal in signals if -0.8 <= signal.score <= 0.8]

    positive_score = sum(signal.score for signal in positive_signals)
    negative_score = sum(signal.score for signal in negative_signals)
    net_score = positive_score + negative_score

    if net_score > 5:
        overall_judgment = "偏多"
    elif net_score < -5:
        overall_judgment = "偏谨慎"
    else:
        overall_judgment = "中性偏选择性"

    best_directions = [_signal_label(signal) for signal in positive_signals[:3]]
    if len(best_directions) < 3:
        best_directions.extend(_signal_label(signal) for signal in mixed_signals[: 3 - len(best_directions)])
    if len(best_directions) < 3:
        best_directions.extend(
            f"{signal.name} -> look for higher-quality entry points"
            for signal in negative_signals[: 3 - len(best_directions)]
        )
    if len(best_directions) < 3:
        best_directions.extend(
            ["防守型现金流龙头", "短久期债券", "仅观察不追价的仓位"][
                : 3 - len(best_directions)
            ]
        )

    avoid_directions = [_signal_label(signal) for signal in negative_signals[:2]]
    if len(avoid_directions) < 2:
        avoid_directions.extend(
            f"{signal.name} -> wait for cleaner catalysts"
            for signal in mixed_signals[: 2 - len(avoid_directions)]
        )
    if len(avoid_directions) < 2:
        avoid_directions.extend(
            f"{signal.name} -> avoid adding before sentiment stabilizes"
            for signal in positive_signals[: 2 - len(avoid_directions)]
        )
    if len(avoid_directions) < 2:
        avoid_directions.extend(
            ["缺乏业绩支撑的高波动主题", "催化减弱但交易拥挤的方向"][
                : 2 - len(avoid_directions)
            ]
        )

    watchlist = [signal.name for signal in mixed_signals[:3]] or [signal.name for signal in signals[:3]]

    top_positive_names = ", ".join(signal.name for signal in positive_signals[:2]) or "高质量防守方向"
    top_negative_names = ", ".join(signal.name for signal in negative_signals[:2]) or "过热但缺少新催化的主题"

    conservative_strategy = (
        f"偏向防守和高确定性方向，优先围绕 {top_positive_names} 中现金流更稳的龙头，"
        "并保留更高现金或短久期仓位。"
    )
    balanced_strategy = (
        f"在 {top_positive_names} 中做趋势配置，同时降低对 {top_negative_names} 的暴露，"
        "保持行业分散。"
    )
    aggressive_strategy = (
        f"优先追踪最强催化方向 {top_positive_names}，但只在事件确认后加仓，"
        f"并对 {top_negative_names} 设更紧的止损或仓位上限。"
    )

    if positive_signals:
        single_action = f"优先研究并筛选 {positive_signals[0].name} 里基本面最强的领先标的。"
    elif negative_signals:
        single_action = f"先降低 {negative_signals[0].name} 相关暴露，等待风险降温。"
    else:
        single_action = "先维持观察仓位，等待更清晰的趋势确认。"

    major_risks = [f"{signal.name}: {signal.reasons[0]}" for signal in negative_signals[:3]]
    if not major_risks:
        major_risks = ["当前信号分化较大，市场可能更依赖后续财报和政策确认。"]

    rationale: list[str] = []
    for signal in positive_signals[:2]:
        rationale.append(f"{signal.name} 当前得分为 {signal.score:.2f}，说明利好催化更集中。")
    for signal in negative_signals[:2]:
        rationale.append(f"{signal.name} 仍是主要拖累项，因为 {signal.reasons[0]}。")
    if not rationale and signals:
        rationale.append(f"{signals[0].name} 是当前绝对分值最高的主题簇。")
    if not rationale:
        rationale.append("当前样本不足，建议先把输出视为观察清单而不是直接交易指令。")

    if len(signals) >= 6 and positive_signals and negative_signals:
        confidence = "中"
    elif len(signals) >= 4:
        confidence = "中高"
    else:
        confidence = "低"

    return StructuredConclusion(
        overall_judgment=overall_judgment,
        best_directions=best_directions[:3],
        avoid_directions=avoid_directions[:2],
        watchlist=watchlist[:3],
        conservative_strategy=conservative_strategy,
        balanced_strategy=balanced_strategy,
        aggressive_strategy=aggressive_strategy,
        single_action=single_action,
        major_risks=major_risks[:3],
        confidence=confidence,
        rationale=rationale[:5],
        collection_warnings=warnings[:5],
    )


def run_workflow(config: WorkflowConfig) -> WorkflowReport:
    items, warnings = collect_news(config)
    enriched_items = enrich_items(items)
    signals = _build_theme_signals(enriched_items)
    conclusion = build_conclusion(signals, warnings)

    if config.llm is None:
        final_markdown = render_structured_markdown(conclusion, len(enriched_items))
    else:
        summarizer = OpenAICompatibleSummarizer(config.llm, config.request_timeout_seconds)
        final_markdown = summarizer.render_markdown(conclusion, signals, len(enriched_items))

    return WorkflowReport(
        generated_at=datetime.now(timezone.utc),
        articles_collected=len(enriched_items),
        signals=signals,
        conclusion=conclusion,
        final_markdown=final_markdown,
    )
