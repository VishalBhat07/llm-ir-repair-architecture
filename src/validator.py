from __future__ import annotations

from pathlib import Path

from llm_ir_pipeline.validator import LLVMIRValidator


def check_ir_validity(ir_filepath: str) -> tuple[bool, str]:
    validator = LLVMIRValidator()
    ir_text = Path(ir_filepath).read_text(encoding="utf-8")
    result = validator.validate(ir_text, case=None)
    if result.parse_ok and result.verify_ok:
        return True, "Success"
    messages = [f"{issue.category}: {issue.message}" for issue in result.issues]
    return False, "\n".join(messages)
