from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from .config import REPO_ROOT, load_benchmarks, load_model_suite
from .llm_client import LLMClient, LLMRequestTimeoutError
from .repair import run_repair_loop
from .reporting import write_run_artifacts
from .toolchain import LLVMToolchain
from .types import AttemptRecord, RunRecord, ValidationResult, ValidationIssue
from .validator import LLVMIRValidator


class ExperimentRunner:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or REPO_ROOT
        self.toolchain = LLVMToolchain()
        self.validator = LLVMIRValidator(self.toolchain)
        self.defaults, self.models = load_model_suite(self.repo_root / "configs" / "models.yaml")
        self.benchmarks = load_benchmarks(self.repo_root / "benchmarks" / "metadata")

    def smoke_test(self) -> dict[str, object]:
        return self.toolchain.smoke_test()

    def prepare_ground_truth(self, splits: set[str] | None = None, force: bool = False) -> list[dict[str, object]]:
        if not self.toolchain.has("clang"):
            raise RuntimeError("clang is required to generate reference LLVM IR")
        records: list[dict[str, object]] = []
        for case in self.benchmarks:
            if splits and case.split not in splits:
                continue
            output_path = case.reference_ir_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists() and not force:
                records.append({"benchmark_id": case.identifier, "status": "skipped", "path": str(output_path)})
                continue
            result = self.toolchain.run_tool(
                "clang",
                [
                    "-S",
                    "-emit-llvm",
                    "-O0",
                    "-Xclang",
                    "-disable-O0-optnone",
                    str(case.source_path),
                    "-o",
                    str(output_path),
                ],
            )
            records.append(
                {
                    "benchmark_id": case.identifier,
                    "status": "ok" if result.ok else "failed",
                    "path": str(output_path),
                    "stderr": result.stderr.strip(),
                }
            )
        return records

    def run(
        self,
        model_names: set[str] | None = None,
        splits: set[str] | None = None,
        prompt_name: str = "zero_shot",
        limit: int | None = None,
        no_llm: bool = False,
        repair_attempts: int | None = None,
    ) -> tuple[list[RunRecord], dict[str, Path]]:
        """Run the experiment.

        Parameters
        ----------
        repair_attempts:
            Override the per-model ``repair_max_attempts`` setting.
            Pass ``1`` to disable repair entirely (generate-once mode).
            ``None`` (default) uses the value from configs/models.yaml.
        no_llm:
            When True, skip ALL LLM calls and treat every benchmark as
            'llm_skipped'.  Useful to verify the toolchain alone.
        """
        selected_models = [model for model in self.models if not model_names or model.name in model_names]
        # When no_llm is requested we still need one synthetic model entry so
        # the outer loop runs once and produces records.
        if no_llm:
            selected_models = selected_models[:1] if selected_models else [self.models[0]]

        selected_benchmarks = [case for case in self.benchmarks if not splits or case.split in splits]
        if limit is not None:
            selected_benchmarks = selected_benchmarks[:limit]

        print(
            f"[runner] {len(selected_models)} model(s), "
            f"{len(selected_benchmarks)} benchmark(s), "
            f"no_llm={no_llm}",
            file=sys.stderr,
        )

        runs: list[RunRecord] = []
        for model in selected_models:
            client = LLMClient(model)

            # ── preflight: skip gracefully if Ollama is not running ──────────
            if not no_llm:
                try:
                    client.preflight()
                except RuntimeError as exc:
                    print(f"[runner] preflight FAILED for {model.name}: {exc}", file=sys.stderr)
                    print("[runner] skipping this model entirely.", file=sys.stderr)
                    continue

            for idx, case in enumerate(selected_benchmarks, 1):
                print(
                    f"[runner] [{idx}/{len(selected_benchmarks)}] "
                    f"{model.name} / {case.identifier}",
                    file=sys.stderr,
                    flush=True,
                )

                if no_llm:
                    # Produce a synthetic failed attempt record with a
                    # 'llm_skipped' issue so the CSV / summary stay consistent.
                    dummy_validation = ValidationResult(
                        sanitized_ir="",
                        parse_ok=False,
                        verify_ok=False,
                        structural_ok=False,
                        semantic_ok=False,
                        accepted=False,
                        issues=[ValidationIssue(category="llm_skipped", message="LLM calls disabled (--no-llm)")],
                    )
                    dummy_attempt = AttemptRecord(
                        attempt_index=0,
                        prompt_name=prompt_name,
                        prompt_text="",
                        raw_response_text="",
                        validation=dummy_validation,
                        diagnostics_used=[],
                    )
                    attempts = [dummy_attempt]
                else:
                    try:
                        max_att = repair_attempts if repair_attempts is not None else model.repair_max_attempts
                        attempts = run_repair_loop(
                            case=case,
                            client=client,
                            validator=self.validator,
                            prompt_name=prompt_name,
                            max_attempts=max_att,
                        )
                    except LLMRequestTimeoutError as exc:
                        print(f"[runner]   ✗ timeout: {exc}", file=sys.stderr)
                        attempts = _make_error_attempts(prompt_name, "llm_timeout", str(exc))
                    except RuntimeError as exc:
                        # Catch rate-limit (HTTP 429 exhausted) and other
                        # transient API errors without killing the whole run.
                        msg = str(exc)
                        category = "llm_rate_limit" if "429" in msg else "llm_error"
                        print(f"[runner]   ✗ {category}: {exc}", file=sys.stderr)
                        attempts = _make_error_attempts(prompt_name, category, msg)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[runner]   ✗ unexpected error: {exc}", file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        attempts = _make_error_attempts(prompt_name, "llm_error", str(exc))

                final_attempt = attempts[-1]
                success = final_attempt.validation.accepted
                print(
                    f"[runner]   {'✓ accepted' if success else '✗ failed'} "
                    f"(attempt {len(attempts)})",
                    file=sys.stderr,
                )
                runs.append(
                    RunRecord(
                        benchmark_id=case.identifier,
                        split=case.split,
                        difficulty=case.difficulty,
                        tags=case.tags,
                        model_name=model.name,
                        provider=model.provider,
                        prompt_name=prompt_name,
                        repair_enabled=not no_llm,
                        attempts=attempts,
                        success=success,
                        final_issue_categories=final_attempt.validation.issue_categories(),
                        toolchain_available=self.toolchain.status.as_dict(),
                    )
                )

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_dir = self.repo_root / "results" / timestamp
        artifacts = write_run_artifacts(runs, output_dir)
        return runs, artifacts

    def benchmark_inventory(self) -> list[dict[str, object]]:
        return [
            {
                "id": case.identifier,
                "split": case.split,
                "difficulty": case.difficulty,
                "tags": case.tags,
                "source_path": str(case.source_path),
                "reference_ir_path": str(case.reference_ir_path),
                "public_tests": len(case.public_tests),
                "hidden_tests": len(case.hidden_tests),
            }
            for case in self.benchmarks
        ]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _make_error_attempts(
    prompt_name: str,
    issue_category: str,
    message: str,
) -> list[AttemptRecord]:
    """Return a single-element attempt list representing an LLM-side error.

    This keeps every benchmark in the result CSV / JSONL even when the LLM
    call fails (rate-limit, network outage, timeout, …).
    """
    failed_validation = ValidationResult(
        sanitized_ir="",
        parse_ok=False,
        verify_ok=False,
        structural_ok=False,
        semantic_ok=False,
        accepted=False,
        issues=[ValidationIssue(category=issue_category, message=message)],
    )
    return [
        AttemptRecord(
            attempt_index=0,
            prompt_name=prompt_name,
            prompt_text="",
            raw_response_text="",
            validation=failed_validation,
            diagnostics_used=[],
        )
    ]
