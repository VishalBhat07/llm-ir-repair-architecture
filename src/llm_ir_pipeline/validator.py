from __future__ import annotations

import re
import tempfile
from pathlib import Path

from .toolchain import LLVMToolchain
from .types import BenchmarkCase, ValidationIssue, ValidationResult

IR_START_PATTERN = re.compile(
    r"^\s*(;|source_filename|target\s+(triple|datalayout)|declare\b|define\b|attributes\b|!\w+)",
    re.IGNORECASE,
)
SSA_DEF_PATTERN = re.compile(r"^\s*(%[-\w.$]+)\s*=")
LABEL_PATTERN = re.compile(r"^\s*([-\w.$]+):")
VALUE_TOKEN_PATTERN = re.compile(r"%[-\w.$]+")
DEFINE_PATTERN = re.compile(r"^\s*(declare|define)\s+(\w+)\s+@([-\w.$]+)\((.*?)\)")
CALL_PATTERN = re.compile(r"call\s+\w+\s+@([-\w.$]+)\((.*?)\)")
BINARY_OP_PATTERN = re.compile(r"=\s*(add|sub|mul|sdiv|udiv|srem|urem|and|or|xor)\s+(\w+)\s+(.+)")
TERMINATOR_PATTERN = re.compile(
    r"^\s*(ret|br|switch|indirectbr|invoke|resume|unreachable|callbr|catchswitch|cleanupret|catchret)\b"
)


def sanitize_ir_text(text: str) -> str:
    raw = text.strip()
    fenced = re.findall(r"```(?:llvm|ir)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced[-1].strip()
    cleaned_lines: list[str] = []
    started = False
    for line in raw.splitlines():
        if not started and not IR_START_PATTERN.match(line):
            continue
        started = True
        if line.strip().startswith("```"):
            continue
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _split_functions(ir_text: str) -> list[list[str]]:
    functions: list[list[str]] = []
    current: list[str] = []
    inside = False
    depth = 0
    for line in ir_text.splitlines():
        if line.strip().startswith("define "):
            if current:
                functions.append(current)
            current = [line]
            inside = True
            depth = line.count("{") - line.count("}")
            continue
        if inside:
            current.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                functions.append(current)
                current = []
                inside = False
    if current:
        functions.append(current)
    return functions


def structural_checks(ir_text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    signatures: dict[str, int] = {}
    signatures_types: dict[str, list[str]] = {}

    for line_no, line in enumerate(ir_text.splitlines(), start=1):
        match = DEFINE_PATTERN.match(line)
        if match:
            _, _, func_name, params = match.groups()
            param_chunks = [chunk.strip() for chunk in params.split(",") if chunk.strip()]
            signatures[func_name] = len(param_chunks)
            signatures_types[func_name] = [chunk.split()[0] for chunk in param_chunks if chunk.split()]

    for function in _split_functions(ir_text):
        labels = {"entry"}
        defined_values: set[str] = set()
        value_types: dict[str, str] = {}
        first_line = function[0]
        header_match = DEFINE_PATTERN.match(first_line)
        if header_match:
            _, return_type, _, params = header_match.groups()
            value_types["@return"] = return_type
            for param in [chunk.strip() for chunk in params.split(",") if chunk.strip()]:
                pieces = param.split()
                if len(pieces) >= 2 and pieces[-1].startswith("%"):
                    value_types[pieces[-1]] = pieces[0]
                    defined_values.add(pieces[-1])

        current_block: list[tuple[int, str]] = []
        blocks: list[list[tuple[int, str]]] = []
        for line_no, line in enumerate(function, start=1):
            label_match = LABEL_PATTERN.match(line)
            if label_match:
                labels.add(label_match.group(1))
                if current_block:
                    blocks.append(current_block)
                current_block = [(line_no, line)]
                continue
            current_block.append((line_no, line))
            def_match = SSA_DEF_PATTERN.match(line)
            if def_match:
                name = def_match.group(1)
                if name in defined_values:
                    issues.append(ValidationIssue("duplicate_ssa_name", f"Duplicate SSA value {name}", line_no))
                defined_values.add(name)
                binary_match = BINARY_OP_PATTERN.search(line)
                if binary_match:
                    _, op_type, _ = binary_match.groups()
                    value_types[name] = op_type
                if " icmp " in line:
                    value_types[name] = "i1"
                call_signature = re.search(r"=\s*call\s+(\w+)\s+@[-\w.$]+", line)
                if call_signature:
                    value_types[name] = call_signature.group(1)
        if current_block:
            blocks.append(current_block)

        for block in blocks:
            meaningful_lines = [
                item for item in block
                if item[1].strip()
                and not LABEL_PATTERN.match(item[1])
                and not item[1].strip().startswith("define ")
                and not item[1].strip() == "}"
            ]
            if not meaningful_lines:
                continue
            if not TERMINATOR_PATTERN.match(meaningful_lines[-1][1]):
                issues.append(
                    ValidationIssue(
                        "missing_terminator",
                        "Basic block does not end with a terminator instruction",
                        meaningful_lines[-1][0],
                    )
                )

        for line_no, line in enumerate(function, start=1):
            if " phi " in line:
                incoming_pairs = re.findall(r"\[.*?\]", line)
                if len(incoming_pairs) < 2:
                    issues.append(
                        ValidationIssue("bad_phi", "Phi node does not have at least two incoming pairs", line_no)
                    )
            for target in re.findall(r"label %([-\w.$]+)", line):
                if target not in labels:
                    issues.append(ValidationIssue("bad_label", f"Branch target %{target} is undefined", line_no))
            call_match = CALL_PATTERN.search(line)
            if call_match:
                callee, arg_blob = call_match.groups()
                arg_chunks = [chunk.strip() for chunk in arg_blob.split(",") if chunk.strip()]
                if callee in signatures and len(arg_chunks) != signatures[callee]:
                    issues.append(
                        ValidationIssue(
                            "signature_mismatch",
                            f"Call to @{callee} has {len(arg_chunks)} args but signature expects {signatures[callee]}",
                            line_no,
                        )
                    )
            binary_match = BINARY_OP_PATTERN.search(line)
            if binary_match:
                _, op_type, operands = binary_match.groups()
                operand_values = [chunk.strip() for chunk in operands.split(",")]
                for operand in operand_values:
                    if operand.startswith("%"):
                        if operand not in defined_values and operand not in {f"%{label}" for label in labels}:
                            issues.append(
                                ValidationIssue("undefined_value", f"Value {operand} is used before definition", line_no)
                            )
                        inferred_type = value_types.get(operand)
                        if inferred_type and inferred_type != op_type:
                            issues.append(
                                ValidationIssue(
                                    "type_width_mismatch",
                                    f"Operand {operand} has type {inferred_type} but instruction expects {op_type}",
                                    line_no,
                                )
                            )
            elif "=" in line:
                lhs_match = SSA_DEF_PATTERN.match(line)
                tokens = VALUE_TOKEN_PATTERN.findall(line)
                lhs = lhs_match.group(1) if lhs_match else None
                for token in tokens:
                    if token == lhs:
                        continue
                    if token not in defined_values and token not in {f"%{label}" for label in labels}:
                        issues.append(ValidationIssue("undefined_value", f"Value {token} is used before definition", line_no))
    return issues


def _diagnostics_from_tool_result(stderr: str) -> list[ValidationIssue]:
    diagnostics: list[ValidationIssue] = []
    lowered = stderr.lower()
    if "phi" in lowered:
        diagnostics.append(ValidationIssue("bad_phi", stderr.strip()))
    if "use of undefined value" in lowered:
        diagnostics.append(ValidationIssue("undefined_value", stderr.strip()))
    if "terminator" in lowered:
        diagnostics.append(ValidationIssue("missing_terminator", stderr.strip()))
    if "label" in lowered:
        diagnostics.append(ValidationIssue("bad_label", stderr.strip()))
    if "type" in lowered:
        diagnostics.append(ValidationIssue("type_width_mismatch", stderr.strip()))
    if "multiple definition" in lowered or "redefinition" in lowered:
        diagnostics.append(ValidationIssue("duplicate_ssa_name", stderr.strip()))
    if not diagnostics and stderr.strip():
        diagnostics.append(ValidationIssue("tool_diagnostic", stderr.strip()))
    return diagnostics


class LLVMIRValidator:
    def __init__(self, toolchain: LLVMToolchain | None = None) -> None:
        self.toolchain = toolchain or LLVMToolchain()

    def validate(self, ir_text: str, case: BenchmarkCase | None = None) -> ValidationResult:
        sanitized = sanitize_ir_text(ir_text)
        issues = structural_checks(sanitized)
        parse_ok = False
        verify_ok = False
        semantic_ok = False
        parse_result = None
        verify_result = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "candidate.ll"
            temp_path.write_text(sanitized, encoding="utf-8")

            if self.toolchain.has("llvm_as"):
                parse_result = self.toolchain.run_tool(
                    "llvm_as", [str(temp_path), "-o", str(temp_path.with_suffix(".bc"))]
                )
                parse_ok = parse_result.ok
                if not parse_ok:
                    issues.extend(_diagnostics_from_tool_result(parse_result.stderr))
            elif self.toolchain.has("clang"):
                parse_output_path = temp_path.with_suffix(".obj")
                parse_result = self.toolchain.run_tool(
                    "clang",
                    [str(temp_path), "-c", "-Wno-override-module", "-o", str(parse_output_path)],
                )
                parse_ok = parse_result.ok
                if not parse_ok:
                    issues.extend(_diagnostics_from_tool_result(parse_result.stderr))
            else:
                issues.append(ValidationIssue("tool_unavailable", "llvm-as/clang not available for parse validation"))

            if parse_ok and self.toolchain.has("opt"):
                verify_result = self.toolchain.run_tool("opt", ["-passes=verify", "-disable-output", str(temp_path)])
                verify_ok = verify_result.ok
                if not verify_ok:
                    issues.extend(_diagnostics_from_tool_result(verify_result.stderr))
            elif parse_ok and self.toolchain.has("clang"):
                verify_output_path = temp_path.with_suffix(".verified.ll")
                verify_result = self.toolchain.run_tool(
                    "clang",
                    [str(temp_path), "-S", "-emit-llvm", "-Wno-override-module", "-o", str(verify_output_path)],
                )
                verify_ok = verify_result.ok
                if not verify_ok:
                    issues.extend(_diagnostics_from_tool_result(verify_result.stderr))
            elif parse_ok:
                issues.append(ValidationIssue("tool_unavailable", "opt/clang not available for verifier checks"))

            structural_ok = not [issue for issue in issues if issue.category != "tool_unavailable"]

            semantic_results: list[dict[str, object]] = []
            if parse_ok and verify_ok and case is not None:
                semantic_ok, semantic_results = self._run_semantic_checks(temp_path, sanitized, case)
                if not semantic_ok and not semantic_results:
                    issues.append(ValidationIssue("tool_unavailable", "lli or clang not available for semantic checks"))
                if not semantic_ok and semantic_results:
                    issues.append(ValidationIssue("semantic_mismatch", "Semantic execution did not match expectations"))
            elif case is not None and not (self.toolchain.has("lli") or self.toolchain.has("clang")):
                issues.append(ValidationIssue("tool_unavailable", "No semantic execution engine available"))
                semantic_results = []
                semantic_ok = False
            else:
                semantic_results = []

        accepted = parse_ok and verify_ok and semantic_ok and not [issue for issue in issues if issue.category not in {"tool_unavailable"}]
        return ValidationResult(
            sanitized_ir=sanitized,
            parse_ok=parse_ok,
            verify_ok=verify_ok,
            structural_ok=structural_ok,
            semantic_ok=semantic_ok,
            accepted=accepted,
            issues=issues,
            parse_result=parse_result,
            verify_result=verify_result,
            semantic_results=semantic_results,
        )

    def _run_semantic_checks(self, temp_path: Path, sanitized_ir: str, case: BenchmarkCase) -> tuple[bool, list[dict[str, object]]]:
        if not (self.toolchain.has("lli") or self.toolchain.has("clang")):
            return False, []
        results: list[dict[str, object]] = []
        all_tests = case.public_tests + case.hidden_tests
        all_ok = True
        for index, test in enumerate(all_tests):
            combined_ir = sanitized_ir
            if case.entry_function != "main":
                call_args = ", ".join(
                    f"{param_type} {value}" for param_type, value in zip(case.parameter_types, test.args, strict=False)
                )
                wrapper = (
                    "\n\ndefine i32 @main() {\n"
                    f"entry:\n  %call = call i32 @{case.entry_function}({call_args})\n"
                    "  ret i32 %call\n}\n"
                )
                combined_ir = sanitized_ir.rstrip() + wrapper
            with tempfile.TemporaryDirectory() as tmp_dir:
                run_path = Path(tmp_dir) / f"semantic_{index}.ll"
                run_path.write_text(combined_ir, encoding="utf-8")
                if self.toolchain.has("lli"):
                    execution = self.toolchain.run_tool("lli", [str(run_path)])
                else:
                    exe_path = Path(tmp_dir) / f"semantic_{index}.exe"
                    build = self.toolchain.run_tool("clang", [str(run_path), "-Wno-override-module", "-o", str(exe_path)])
                    if not build.ok:
                        execution = build
                    else:
                        execution = self.toolchain.run([str(exe_path)])
            observed_return = execution.returncode
            # Exit codes are unsigned 8-bit on most OSes (0-255).
            # We compare directly without requiring returncode==0,
            # because the test harness uses the exit code as the return value.
            passed = observed_return == test.expected_return
            results.append(
                {
                    "args": test.args,
                    "expected_return": test.expected_return,
                    "observed_return": observed_return,
                    "passed": passed,
                    "stderr": execution.stderr.strip(),
                }
            )
            all_ok = all_ok and passed
        return all_ok, results
