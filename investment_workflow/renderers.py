from __future__ import annotations

import json
from pathlib import Path

from .models import StructuredConclusion, WorkflowReport


def render_structured_markdown(
    conclusion: StructuredConclusion,
    articles_collected: int,
) -> str:
    best_directions = "\n".join(
        f"{index}. {value}" for index, value in enumerate(conclusion.best_directions, start=1)
    )
    avoid_directions = "\n".join(
        f"{index}. {value}" for index, value in enumerate(conclusion.avoid_directions, start=1)
    )
    risks = "\n".join(f"- {risk}" for risk in conclusion.major_risks)
    rationale = "\n".join(f"- {reason}" for reason in conclusion.rationale)
    warnings = "\n".join(f"- {warning}" for warning in conclusion.collection_warnings)

    sections = [
        "## 最终投资结论",
        f"- **今日总体判断**：{conclusion.overall_judgment}",
        f"- **采集到的事件数**：{articles_collected}",
        "- **最值得配置的3个方向**：",
        best_directions,
        "- **最应该回避的2个方向**：",
        avoid_directions,
        "- **建议策略**：",
        f"  - 保守型：{conclusion.conservative_strategy}",
        f"  - 平衡型：{conclusion.balanced_strategy}",
        f"  - 激进型：{conclusion.aggressive_strategy}",
        f"- **如果只做一个动作**：{conclusion.single_action}",
        "- **主要风险**：",
        risks,
        f"- **结论置信度**：{conclusion.confidence}",
        "",
        "## 关键理由",
        rationale,
    ]

    if conclusion.collection_warnings:
        sections.extend(["", "## 采集告警", warnings])

    return "\n".join(section for section in sections if section != "")


def write_report_files(report: WorkflowReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir / report.generated_at.strftime("%Y%m%d-%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = report_dir / "report.md"
    json_path = report_dir / "report.json"

    markdown_path.write_text(report.final_markdown + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_dir
