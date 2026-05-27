from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from investment_workflow.config import load_dotenv, load_config
from investment_workflow.delivery import build_feishu_message
from investment_workflow.feeds import deduplicate_items
from investment_workflow.models import NewsItem
from investment_workflow.pipeline import _build_theme_signals, build_conclusion, enrich_items
from investment_workflow.renderers import render_structured_markdown


class PipelineTests(unittest.TestCase):
    def test_deduplicate_items_keeps_latest(self) -> None:
        now = datetime.now(timezone.utc)
        older = NewsItem(
            title="AI chip demand surges",
            link="https://example.com/1",
            source="Example",
            published_at=now - timedelta(hours=2),
            summary="Older duplicate",
            query="artificial intelligence",
        )
        newer = NewsItem(
            title="AI chip demand surges",
            link="https://example.com/1",
            source="Example",
            published_at=now - timedelta(hours=1),
            summary="Newer duplicate",
            query="artificial intelligence",
        )

        unique = deduplicate_items([older, newer])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].summary, "Newer duplicate")

    def test_enrich_items_classifies_direction(self) -> None:
        item = NewsItem(
            title="Semiconductor equipment orders surge after strong AI investment",
            link="https://example.com/2",
            source="Example",
            published_at=datetime.now(timezone.utc) - timedelta(hours=3),
            summary="Chipmakers see strong growth.",
            query="semiconductor",
        )

        [enriched] = enrich_items([item])
        self.assertIn("Semiconductor cycle", enriched.themes)
        self.assertEqual(enriched.sentiment, "positive")
        self.assertGreater(enriched.score, 0)

    def test_build_conclusion_returns_expected_lists(self) -> None:
        positive_item = NewsItem(
            title="AI datacenter expansion supported by record orders",
            link="https://example.com/3",
            source="Example",
            published_at=datetime.now(timezone.utc) - timedelta(hours=1),
            summary="Cloud demand remains strong.",
            query="artificial intelligence",
        )
        negative_item = NewsItem(
            title="New tariffs raise risk for exporters and supply chain",
            link="https://example.com/4",
            source="Example",
            published_at=datetime.now(timezone.utc) - timedelta(hours=1),
            summary="Trade conflict intensifies.",
            query="geopolitics",
        )

        signals = _build_theme_signals(enrich_items([positive_item, negative_item]))
        conclusion = build_conclusion(signals, [])
        self.assertTrue(conclusion.best_directions)
        self.assertEqual(len(conclusion.avoid_directions), 2)
        self.assertNotIn("{top_negative_names}", conclusion.aggressive_strategy)

    def test_config_parses_multiple_delivery_targets(self) -> None:
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory

        original = dict(os.environ)
        try:
            with TemporaryDirectory() as temp_dir:
                project_root = Path(temp_dir)
                (project_root / ".env").write_text(
                    "DELIVERY_MODE=file,feishu\n"
                    "FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/test\n",
                    encoding="utf-8",
                )
                config = load_config(project_root)
                self.assertEqual(config.delivery_modes, ["file", "feishu"])
                self.assertIsNotNone(config.feishu)
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_build_feishu_message_uses_report_markdown(self) -> None:
        from investment_workflow.models import WorkflowReport

        conclusion = build_conclusion([], [])
        markdown = render_structured_markdown(conclusion, 0)
        report = WorkflowReport(
            generated_at=datetime.now(timezone.utc),
            articles_collected=0,
            signals=[],
            conclusion=conclusion,
            final_markdown=markdown,
        )

        payload = build_feishu_message(report)
        self.assertEqual(payload["msg_type"], "text")
        self.assertIn("最终投资结论", payload["content"]["text"])


if __name__ == "__main__":
    unittest.main()
