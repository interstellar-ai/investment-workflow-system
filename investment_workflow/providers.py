from __future__ import annotations

import json
from urllib.request import Request, urlopen

from .config import LLMConfig
from .models import StructuredConclusion, ThemeSignal


class OpenAICompatibleSummarizer:
    def __init__(self, config: LLMConfig, timeout: int) -> None:
        self._config = config
        self._timeout = timeout

    def render_markdown(
        self,
        conclusion: StructuredConclusion,
        signals: list[ThemeSignal],
        articles_collected: int,
    ) -> str:
        signal_lines: list[str] = []
        for signal in signals[:6]:
            signal_lines.append(
                f"- Theme: {signal.name}; direction: {signal.direction}; "
                f"score: {signal.score:.2f}; reasons: {'; '.join(signal.reasons[:3])}"
            )

        prompt = (
            "You are producing a concise investment research brief. "
            "Use the structured data below to write a compact markdown report in Chinese. "
            "Do not add chain-of-thought. Do not invent facts beyond the input.\n\n"
            f"Articles collected: {articles_collected}\n"
            f"Overall judgment: {conclusion.overall_judgment}\n"
            f"Best directions: {', '.join(conclusion.best_directions)}\n"
            f"Avoid directions: {', '.join(conclusion.avoid_directions)}\n"
            f"Watchlist: {', '.join(conclusion.watchlist)}\n"
            f"Conservative strategy: {conclusion.conservative_strategy}\n"
            f"Balanced strategy: {conclusion.balanced_strategy}\n"
            f"Aggressive strategy: {conclusion.aggressive_strategy}\n"
            f"Single action: {conclusion.single_action}\n"
            f"Major risks: {', '.join(conclusion.major_risks)}\n"
            f"Confidence: {conclusion.confidence}\n"
            f"Rationale: {'; '.join(conclusion.rationale)}\n"
            f"Collection warnings: {'; '.join(conclusion.collection_warnings) or 'none'}\n"
            "Signals:\n"
            + "\n".join(signal_lines)
            + "\n\n"
            "Return markdown with these sections exactly:\n"
            "## 最终投资结论\n"
            "- 今日总体判断\n"
            "- 最值得配置的3个方向\n"
            "- 最应该回避的2个方向\n"
            "- 建议策略（保守型 / 平衡型 / 激进型）\n"
            "- 如果只做一个动作\n"
            "- 主要风险\n"
            "- 结论置信度\n"
        )

        payload = json.dumps(
            {
                "model": self._config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")

        request = Request(
            f"{self._config.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request, timeout=self._timeout) as response:
            result = json.loads(response.read().decode("utf-8"))

        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {result!r}") from exc
