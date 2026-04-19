from __future__ import annotations

import csv
import json
from pathlib import Path

from .eval import summarize_runs
from .types import RunRecord


def write_run_artifacts(run_records: list[RunRecord], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_jsonl = output_dir / "runs.jsonl"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    flat_csv = output_dir / "runs_flat.csv"

    with runs_jsonl.open("w", encoding="utf-8") as handle:
        for record in run_records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=True) + "\n")

    summary = summarize_runs(run_records)
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md.write_text(_summary_to_markdown(summary), encoding="utf-8")
    _write_flat_csv(run_records, flat_csv)
    return {
        "runs_jsonl": runs_jsonl,
        "summary_json": summary_json,
        "summary_md": summary_md,
        "runs_flat_csv": flat_csv,
    }


def _write_flat_csv(run_records: list[RunRecord], path: Path) -> None:
    fieldnames = [
        "benchmark_id",
        "split",
        "difficulty",
        "model_name",
        "provider",
        "prompt_name",
        "repair_enabled",
        "attempt_count",
        "success",
        "parse_ok",
        "verify_ok",
        "semantic_ok",
        "final_issue_categories",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in run_records:
            final_validation = record.final_attempt().validation
            writer.writerow(
                {
                    "benchmark_id": record.benchmark_id,
                    "split": record.split,
                    "difficulty": record.difficulty,
                    "model_name": record.model_name,
                    "provider": record.provider,
                    "prompt_name": record.prompt_name,
                    "repair_enabled": record.repair_enabled,
                    "attempt_count": len(record.attempts),
                    "success": record.success,
                    "parse_ok": final_validation.parse_ok,
                    "verify_ok": final_validation.verify_ok,
                    "semantic_ok": final_validation.semantic_ok,
                    "final_issue_categories": ",".join(record.final_issue_categories),
                }
            )


def _summary_to_markdown(summary: dict[str, object]) -> str:
    overall = summary["overall"]
    lines = [
        "# Experiment Summary",
        "",
        f"- Total runs: {overall['total_runs']}",
        f"- Success rate: {overall['success_rate']}",
        f"- Parse rate: {overall['parse_rate']}",
        f"- Verify rate: {overall['verify_rate']}",
        f"- Semantic rate: {overall['semantic_rate']}",
        f"- Average attempts: {overall['avg_attempts']}",
        "",
        "## By Model",
        "",
        "| Model | Runs | Success | Verify | Semantic |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for model_name, payload in summary["by_model"].items():
        lines.append(
            f"| {model_name} | {payload['runs']} | {payload['success_rate']} | "
            f"{payload['verify_rate']} | {payload['semantic_rate']} |"
        )
    lines.extend(["", "## Failure Categories", ""])
    for category, count in summary["failure_categories"].items():
        lines.append(f"- {category}: {count}")
    return "\n".join(lines) + "\n"
