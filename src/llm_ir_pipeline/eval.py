from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .types import RunRecord


def _ratio(values: list[bool]) -> float:
    return round(sum(1 for value in values if value) / len(values), 4) if values else 0.0


def summarize_runs(run_records: list[RunRecord]) -> dict[str, object]:
    overall = {
        "total_runs": len(run_records),
        "success_rate": _ratio([record.success for record in run_records]),
        "parse_rate": _ratio([record.final_attempt().validation.parse_ok for record in run_records]),
        "verify_rate": _ratio([record.final_attempt().validation.verify_ok for record in run_records]),
        "semantic_rate": _ratio([record.final_attempt().validation.semantic_ok for record in run_records]),
        "avg_attempts": round(mean([len(record.attempts) for record in run_records]), 3) if run_records else 0.0,
    }

    by_model: dict[str, list[RunRecord]] = defaultdict(list)
    by_split: dict[str, list[RunRecord]] = defaultdict(list)
    by_prompt: dict[str, list[RunRecord]] = defaultdict(list)
    by_tag: dict[str, list[RunRecord]] = defaultdict(list)
    failure_categories: dict[str, int] = defaultdict(int)

    for record in run_records:
        by_model[record.model_name].append(record)
        by_split[record.split].append(record)
        by_prompt[record.prompt_name].append(record)
        for tag in record.tags:
            by_tag[tag].append(record)
        for category in record.final_issue_categories:
            failure_categories[category] += 1

    def bucket_summary(bucket: dict[str, list[RunRecord]]) -> dict[str, dict[str, float]]:
        return {
            key: {
                "runs": len(records),
                "success_rate": _ratio([record.success for record in records]),
                "verify_rate": _ratio([record.final_attempt().validation.verify_ok for record in records]),
                "semantic_rate": _ratio([record.final_attempt().validation.semantic_ok for record in records]),
            }
            for key, records in sorted(bucket.items())
        }

    return {
        "overall": overall,
        "by_model": bucket_summary(by_model),
        "by_split": bucket_summary(by_split),
        "by_prompt": bucket_summary(by_prompt),
        "by_tag": bucket_summary(by_tag),
        "failure_categories": dict(sorted(failure_categories.items())),
    }
