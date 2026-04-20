from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .types import RunRecord


def _ratio(values: list[bool]) -> float:
    return round(sum(1 for value in values if value) / len(values), 4) if values else 0.0


def _average(values: list[float | int | None]) -> float:
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 4) if valid else 0.0


def summarize_runs(run_records: list[RunRecord]) -> dict[str, object]:
    if not run_records:
        return {}

    # Core Rates
    total_runs = len(run_records)
    success_rate = _ratio([record.success for record in run_records])
    parse_rate = _ratio([record.final_attempt().validation.parse_ok for record in run_records])
    verify_rate = _ratio([record.final_attempt().validation.verify_ok for record in run_records])
    semantic_rate = _ratio([record.final_attempt().validation.semantic_ok for record in run_records])

    # Repair Phase Analysis
    zero_shot_success = [r.attempts[0].validation.accepted for r in run_records if r.attempts]
    zero_shot_rate = _ratio(zero_shot_success)

    needs_repair = [r for r in run_records if r.attempts and not r.attempts[0].validation.accepted]
    repair_efficacy = _ratio([r.success for r in needs_repair]) if needs_repair else 0.0

    successful_runs = [r for r in run_records if r.success]
    avg_attempts_to_success = _average([len(r.attempts) for r in successful_runs])

    # Token Metrics
    all_input_tokens = []
    all_output_tokens = []
    for r in run_records:
        for att in r.attempts:
            all_input_tokens.append(att.input_tokens)
            all_output_tokens.append(att.output_tokens)
    
    avg_input_tokens = _average(all_input_tokens)
    avg_output_tokens = _average(all_output_tokens)

    # Error Evolution (Attempt Decay)
    max_attempts = max((len(r.attempts) for r in run_records), default=0)
    error_evolution = []
    for i in range(max_attempts):
        attempts_at_i = [r.attempts[i] for r in run_records if len(r.attempts) > i]
        if not attempts_at_i:
            continue
        error_evolution.append({
            "attempt_index": i + 1,
            "sample_size": len(attempts_at_i),
            "parse_rate": _ratio([a.validation.parse_ok for a in attempts_at_i]),
            "verify_rate": _ratio([a.validation.verify_ok for a in attempts_at_i]),
            "semantic_rate": _ratio([a.validation.semantic_ok for a in attempts_at_i]),
            "success_rate": _ratio([a.validation.accepted for a in attempts_at_i])
        })

    # Persistent Failures
    failed_runs = [r for r in run_records if not r.success]
    persistent_failures: dict[str, int] = defaultdict(int)
    for r in failed_runs:
        for cat in r.final_issue_categories:
            persistent_failures[cat] += 1

    return {
        "overall": {
            "total_runs": total_runs,
            "success_rate": success_rate,
            "parse_rate": parse_rate,
            "verify_rate": verify_rate,
            "semantic_rate": semantic_rate,
        },
        "repair_analysis": {
            "zero_shot_rate": zero_shot_rate,
            "repair_efficacy_rate": repair_efficacy,
            "avg_attempts_to_success": avg_attempts_to_success,
            "total_items_needing_repair": len(needs_repair)
        },
        "token_metrics": {
            "avg_input_tokens_per_attempt": avg_input_tokens,
            "avg_output_tokens_per_attempt": avg_output_tokens
        },
        "error_evolution": error_evolution,
        "persistent_failures": dict(sorted(persistent_failures.items(), key=lambda item: item[1], reverse=True))
    }
