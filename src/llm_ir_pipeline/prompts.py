from __future__ import annotations

from textwrap import dedent

from .types import BenchmarkCase


SYSTEM_INSTRUCTION = (
    "You are an LLVM IR lowering assistant. Output only valid LLVM IR text with no "
    "markdown fences, prose, or commentary. Respect SSA, block terminators, typed "
    "operations, and control-flow structure."
)


FEW_SHOT_EXAMPLES = [
    {
        "source": "int add_two(int a, int b) { return a + b; }",
        "ir": dedent(
            """
            define i32 @add_two(i32 %a, i32 %b) {
            entry:
              %sum = add i32 %a, %b
              ret i32 %sum
            }
            """
        ).strip(),
    },
    {
        "source": "int choose_max(int a, int b) { if (a > b) { return a; } return b; }",
        "ir": dedent(
            """
            define i32 @choose_max(i32 %a, i32 %b) {
            entry:
              %cmp = icmp sgt i32 %a, %b
              br i1 %cmp, label %then, label %else

            then:
              ret i32 %a

            else:
              ret i32 %b
            }
            """
        ).strip(),
    },
]


def benchmark_context(case: BenchmarkCase) -> str:
    return dedent(
        f"""
        Benchmark id: {case.identifier}
        Difficulty: {case.difficulty}
        Tags: {", ".join(case.tags)}
        Entry function: {case.entry_function}
        Parameter types: {", ".join(case.parameter_types) if case.parameter_types else "(none)"}
        """
    ).strip()


def build_zero_shot_prompt(case: BenchmarkCase, source_code: str) -> str:
    return dedent(
        f"""
        Lower the following C-like program to LLVM IR.

        Constraints:
        - Use only valid LLVM IR text.
        - Preserve control-flow and data-flow structure.
        - Use typed instructions and valid basic block labels.
        - Do not emit explanations, comments, or markdown fences.
        - CRITICAL RULE: NEVER nest instructions. For example, `add i32 %a, mul i32 %b, 2` is INVALID. Every operation must be placed on its own separate line and assigned to a new temporary SSA variable (e.g., `%1 = mul i32 %b, 2` then `%2 = add i32 %a, %1`).

        {benchmark_context(case)}

        Source program:
        {source_code}
        """
    ).strip()


def build_few_shot_prompt(case: BenchmarkCase, source_code: str) -> str:
    exemplars = []
    for example in FEW_SHOT_EXAMPLES:
        exemplars.append(f"Source:\n{example['source']}\n\nLLVM IR:\n{example['ir']}")
    joined = "\n\n".join(exemplars)
    return dedent(
        f"""
        Lower the final source program to LLVM IR by following the style and structural discipline of the examples.

        {joined}

        Now lower this benchmark:
        {benchmark_context(case)}

        Source program:
        {source_code}
        """
    ).strip()


def build_repair_prompt(
    case: BenchmarkCase,
    source_code: str,
    previous_ir: str,
    diagnostics: list[str],
) -> str:
    diag_block = "\n".join(f"- {item}" for item in diagnostics) if diagnostics else "- Unknown failure"
    return dedent(
        f"""
        Repair the LLVM IR for the benchmark below.

        Requirements:
        - Return only corrected LLVM IR text.
        - Keep the same entry function name: {case.entry_function}
        - Fix structural, SSA, type, and control-flow issues.
        - CRITICAL RULE: NEVER nest instructions. For example, `add i32 %a, mul i32 %b, 2` is INVALID. Every operation must be placed on its own separate line and assigned to a new temporary SSA variable.

        Benchmark context:
        {benchmark_context(case)}

        Source program:
        {source_code}

        Reported diagnostics:
        {diag_block}

        Previous IR:
        {previous_ir}
        """
    ).strip()
