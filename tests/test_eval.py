from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_ir_pipeline.eval import summarize_runs
from llm_ir_pipeline.types import AttemptRecord, RunRecord, ValidationIssue, ValidationResult


class EvalTests(unittest.TestCase):
    def test_summary_counts_success_and_failure(self) -> None:
        successful_validation = ValidationResult(
            sanitized_ir="define i32 @ok() { ret i32 0 }",
            parse_ok=True,
            verify_ok=True,
            structural_ok=True,
            semantic_ok=True,
            accepted=True,
            issues=[],
        )
        failed_validation = ValidationResult(
            sanitized_ir="define i32 @bad() {",
            parse_ok=False,
            verify_ok=False,
            structural_ok=False,
            semantic_ok=False,
            accepted=False,
            issues=[ValidationIssue("bad_label", "missing label")],
        )
        runs = [
            RunRecord(
                benchmark_id="a",
                split="core",
                difficulty="low",
                tags=["branch"],
                model_name="m1",
                provider="ollama",
                prompt_name="zero_shot",
                repair_enabled=True,
                attempts=[AttemptRecord(0, "zero_shot", "p", "r", successful_validation)],
                success=True,
                final_issue_categories=[],
                toolchain_available={},
            ),
            RunRecord(
                benchmark_id="b",
                split="mutated",
                difficulty="high",
                tags=["phi"],
                model_name="m1",
                provider="ollama",
                prompt_name="repair",
                repair_enabled=True,
                attempts=[AttemptRecord(0, "repair", "p", "r", failed_validation)],
                success=False,
                final_issue_categories=["bad_label"],
                toolchain_available={},
            ),
        ]
        summary = summarize_runs(runs)
        self.assertEqual(summary["overall"]["total_runs"], 2)
        self.assertEqual(summary["overall"]["success_rate"], 0.5)
        self.assertEqual(summary["failure_categories"]["bad_label"], 1)


if __name__ == "__main__":
    unittest.main()
