from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .delivery import send_to_feishu
from .pipeline import run_workflow
from .renderers import write_report_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="investment_workflow",
        description="Generate a compact investment brief from current tech and macro event flows.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the final Markdown report to stdout.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override OUTPUT_DIR for file delivery.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config = load_config(project_root)
    if args.output_dir is not None:
        config.output_dir = args.output_dir.resolve()

    report = run_workflow(config)
    if args.stdout or "stdout" in config.delivery_modes:
        print(report.final_markdown)
    if "file" in config.delivery_modes:
        report_dir = write_report_files(report, config.output_dir)
        print(f"Report written to {report_dir}")
    if "feishu" in config.delivery_modes:
        if config.feishu is None:
            raise RuntimeError("Feishu delivery requested but FEISHU_WEBHOOK_URL is not configured.")
        send_to_feishu(config.feishu, report, config.request_timeout_seconds)
        print("Report sent to Feishu")
    return 0
