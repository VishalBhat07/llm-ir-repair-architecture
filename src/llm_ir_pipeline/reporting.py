from __future__ import annotations

import csv
import json
from pathlib import Path

from .eval import summarize_runs
from .types import RunRecord


def write_run_artifacts(run_records: list[RunRecord], timestamp: str, repo_root: Path) -> dict[str, list[Path]]:
    from collections import defaultdict
    
    grouped_runs = defaultdict(list)
    for record in run_records:
        grouped_runs[(record.model_name, record.split)].append(record)
    
    all_artifacts = defaultdict(list)

    for (model_name, split), records in grouped_runs.items():
        output_dir = repo_root / "results" / model_name / split / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        
        summary_md = output_dir / "summary.md"
        summary_json = output_dir / "summary.json"
        repair_csv = output_dir / "repair_trajectory.csv"
        failures_jsonl = output_dir / "failures_analysis.jsonl"
        
        summary = summarize_runs(records)
        summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary_md.write_text(_summary_to_markdown(summary), encoding="utf-8")
        
        _write_repair_trajectory_csv(records, repair_csv)
        _write_failures_analysis_jsonl(records, failures_jsonl)
        
        all_artifacts["summary_md"].append(summary_md)
        all_artifacts["summary_json"].append(summary_json)
        all_artifacts["repair_trajectory_csv"].append(repair_csv)
        all_artifacts["failures_analysis_jsonl"].append(failures_jsonl)

    return dict(all_artifacts)


def _write_repair_trajectory_csv(run_records: list[RunRecord], path: Path) -> None:
    fieldnames = [
        "benchmark_id",
        "attempt_index",
        "parse_ok",
        "verify_ok",
        "semantic_ok",
        "issue_category",
        "input_tokens",
        "output_tokens",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in run_records:
            for att in record.attempts:
                writer.writerow(
                    {
                        "benchmark_id": record.benchmark_id,
                        "attempt_index": att.attempt_index,
                        "parse_ok": att.validation.parse_ok,
                        "verify_ok": att.validation.verify_ok,
                        "semantic_ok": att.validation.semantic_ok,
                        "issue_category": ",".join(att.validation.issue_categories()),
                        "input_tokens": att.input_tokens,
                        "output_tokens": att.output_tokens,
                    }
                )


def _write_failures_analysis_jsonl(run_records: list[RunRecord], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in run_records:
            if not record.success:
                final_att = record.final_attempt()
                failure_payload = {
                    "benchmark_id": record.benchmark_id,
                    "model_name": record.model_name,
                    "split": record.split,
                    "prompt_used": final_att.prompt_text,
                    "generated_ir": final_att.raw_response_text,
                    "validation_issues": [
                        {
                            "category": issue.category,
                            "message": issue.message,
                            "severity": issue.severity,
                            "line": issue.line
                        } for issue in final_att.validation.issues
                    ]
                }
                handle.write(json.dumps(failure_payload, ensure_ascii=True) + "\n")


def _summary_to_markdown(summary: dict[str, object]) -> str:
    if not summary:
        return "# Experiment Summary\nNo runs recorded.\n"

    overall = summary["overall"]
    repair = summary["repair_analysis"]
    tokens = summary["token_metrics"]
    error_evol = summary["error_evolution"]
    persist = summary["persistent_failures"]

    lines = [
        "# Research Analysis Summary",
        "",
        "## Overall Statistics",
        f"- **Total Runs:** {overall.get('total_runs', 0)}",
        f"- **Success Rate:** {overall.get('success_rate', 0.0)}",
        f"- **Parse Rate:** {overall.get('parse_rate', 0.0)}",
        f"- **Verify Rate:** {overall.get('verify_rate', 0.0)}",
        f"- **Semantic Rate:** {overall.get('semantic_rate', 0.0)}",
        "",
        "## Repair Phase Analysis",
        f"- **Zero-Shot Pass Rate:** {repair.get('zero_shot_rate', 0.0)}",
        f"- **Repair Efficacy:** {repair.get('repair_efficacy_rate', 0.0)} (of {repair.get('total_items_needing_repair', 0)} items needing repair)",
        f"- **Average Attempts to Success:** {repair.get('avg_attempts_to_success', 0.0)}",
        "",
        "## Token & Latency Metrics",
        f"- **Avg Input Tokens per Attempt:** {tokens.get('avg_input_tokens_per_attempt', 0.0)}",
        f"- **Avg Output Tokens per Attempt:** {tokens.get('avg_output_tokens_per_attempt', 0.0)}",
        "",
        "## Error Evolution (Attempt Decay)",
        "| Attempt Index | Sample Size | Parse Rate | Verify Rate | Semantic Rate | Success Rate |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |"
    ]

    for ev in error_evol:
        lines.append(
            f"| {ev['attempt_index']} | {ev['sample_size']} | {ev['parse_rate']} | "
            f"{ev['verify_rate']} | {ev['semantic_rate']} | {ev['success_rate']} |"
        )

    lines.extend([
        "",
        "## Persistent Failures (Unresolved after max attempts)",
    ])
    if not persist:
        lines.append("- None")
    else:
        for cat, count in persist.items():
            lines.append(f"- **{cat}**: {count}")

    return "\n".join(lines) + "\n"
