from __future__ import annotations

import argparse
import json
import sys

from llm_ir_pipeline.runner import ExperimentRunner
from llm_ir_pipeline.toolchain import LLVMToolchain


def _parse_csv_set(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-assisted LLVM IR lowering research harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("smoke-test", help="Check LLVM toolchain availability")
    subparsers.add_parser("inventory", help="Print benchmark inventory")

    prepare = subparsers.add_parser("prepare-ground-truth", help="Emit clang reference IR for benchmarks")
    prepare.add_argument("--splits", help="Comma-separated benchmark splits (e.g. core,mutated)", default=None)
    prepare.add_argument("--force", action="store_true", help="Overwrite existing ground truth files")

    run = subparsers.add_parser("run", help="Run experiments")
    run.add_argument(
        "--models",
        help=(
            "Comma-separated model names from configs/models.yaml "
            "(default: all configured models). "
            "Example: --models qwen25_coder_small_local"
        ),
        default=None,
    )
    run.add_argument(
        "--splits",
        help=(
            "Comma-separated benchmark splits to run "
            "(default: all splits). "
            "Use 'core' to run only the core benchmarks first, "
            "add 'mutated' later once core is stable."
        ),
        default=None,
    )
    run.add_argument("--prompt", choices=["zero_shot", "few_shot"], default="zero_shot")
    run.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of benchmarks per model (useful for quick sanity checks)",
    )
    run.add_argument(
        "--repair-attempts",
        type=int,
        default=1,
        dest="repair_attempts",
        help=(
            "Number of LLM attempts per benchmark including the first generation. "
            "1 = generate once, no repair (default). "
            "3 = generate + up to 2 repair rounds."
        ),
    )
    run.add_argument(
        "--no-llm",
        action="store_true",
        dest="no_llm",
        help=(
            "Skip all LLM calls entirely. Every benchmark will receive an "
            "'llm_skipped' result. Use this to verify the toolchain pipeline "
            "is wired up correctly without consuming API quota or needing Ollama."
        ),
    )
    run.add_argument(
        "--tool-info",
        action="store_true",
        dest="tool_info",
        help="Print available LLVM tools and their roles before running.",
    )

    args = parser.parse_args()
    runner = ExperimentRunner()

    if args.command == "smoke-test":
        _print_tool_info()
        print(json.dumps(runner.smoke_test(), indent=2))
        return
    if args.command == "inventory":
        print(json.dumps(runner.benchmark_inventory(), indent=2))
        return
    if args.command == "prepare-ground-truth":
        print(json.dumps(runner.prepare_ground_truth(splits=_parse_csv_set(args.splits), force=args.force), indent=2))
        return
    if args.command == "run":
        if getattr(args, "tool_info", False):
            _print_tool_info()

        runs, artifacts = runner.run(
            model_names=_parse_csv_set(args.models),
            splits=_parse_csv_set(args.splits),
            prompt_name=args.prompt,
            limit=args.limit,
            no_llm=args.no_llm,
            repair_attempts=args.repair_attempts,
        )

        # ── per-benchmark failure breakdown ──────────────────────────────────
        total = len(runs)
        succeeded = sum(1 for r in runs if r.success)
        print(f"\n{'─'*60}", file=sys.stderr)
        print(f"  RESULTS  ({succeeded}/{total} accepted)", file=sys.stderr)
        print(f"{'─'*60}", file=sys.stderr)
        for r in runs:
            status = "✓" if r.success else "✗"
            fa = r.final_attempt()
            checks = (
                f"parse={'✓' if fa.validation.parse_ok else '✗'}  "
                f"verify={'✓' if fa.validation.verify_ok else '✗'}  "
                f"semantic={'✓' if fa.validation.semantic_ok else '✗'}"
            )
            cats = ", ".join(r.final_issue_categories) or "none"
            print(f"  {status} {r.benchmark_id:<40}  {checks}", file=sys.stderr)
            if not r.success:
                print(f"      issues: {cats}", file=sys.stderr)
        print(f"{'─'*60}\n", file=sys.stderr)

        rate_limited = sum(1 for r in runs if any("rate_limit" in c for c in r.final_issue_categories))
        timed_out = sum(1 for r in runs if any("timeout" in c for c in r.final_issue_categories))
        if rate_limited or timed_out:
            print(f"  ⚠  {rate_limited} rate-limited  |  {timed_out} timed-out", file=sys.stderr)
        # ─────────────────────────────────────────────────────────────────────

        print(
            json.dumps(
                {
                    "run_count": total,
                    "succeeded": succeeded,
                    "repair_attempts_cap": args.repair_attempts,
                    "artifacts": {name: str(path) for name, path in artifacts.items()},
                },
                indent=2,
            )
        )
        return


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOL_ROLES = {
    "clang": (
        "IR parse check (compile .ll → .obj),  "
        "IR verify check (re-emit as .ll),  "
        "semantic execution (compile + run executable)"
    ),
    "llvm_as": (
        "IR assembler: fastest parser for .ll → .bc  "
        "[preferred over clang when available]"
    ),
    "opt": (
        "Runs the LLVM verifier pass (-passes=verify)  "
        "[more precise structural checks than clang]"
    ),
    "lli": (
        "JIT-executes .ll directly — used for semantic tests  "
        "[preferred over clang compile+run when available]"
    ),
    "filecheck": (
        "Pattern-match tool output against expected strings  "
        "[not yet used in this pipeline]"
    ),
}


def _print_tool_info() -> None:
    tc = LLVMToolchain()
    status = tc.status.as_dict()
    print("\n  LLVM TOOL STATUS", file=sys.stderr)
    print("  " + "─" * 56, file=sys.stderr)
    for tool, path in status.items():
        role = _TOOL_ROLES.get(tool, "")
        mark = "✓" if path else "✗"
        label = f"[{path}]" if path else "[not found on PATH]"
        print(f"  {mark} {tool:<12} {label}", file=sys.stderr)
        print(f"              ↳ {role}", file=sys.stderr)
    print("  " + "─" * 56 + "\n", file=sys.stderr)


if __name__ == "__main__":
    main()
