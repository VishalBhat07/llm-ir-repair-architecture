from __future__ import annotations

from .config import read_source
from .llm_client import LLMClient
from .prompts import build_few_shot_prompt, build_repair_prompt, build_zero_shot_prompt
from .types import AttemptRecord, BenchmarkCase
from .validator import LLVMIRValidator


def _diagnostic_messages(validation) -> list[str]:
    return [f"{issue.category}: {issue.message}" for issue in validation.issues]


def run_repair_loop(
    case: BenchmarkCase,
    client: LLMClient,
    validator: LLVMIRValidator,
    prompt_name: str = "zero_shot",
    max_attempts: int | None = None,
) -> list[AttemptRecord]:
    source_code = read_source(case)
    max_attempts = max_attempts or client.model_config.repair_max_attempts
    attempts: list[AttemptRecord] = []
    current_prompt_name = prompt_name
    current_prompt = (
        build_few_shot_prompt(case, source_code) if prompt_name == "few_shot" else build_zero_shot_prompt(case, source_code)
    )

    for attempt_index in range(max_attempts):
        response = client.generate(current_prompt)
        validation = validator.validate(response.text, case=case)
        attempts.append(
            AttemptRecord(
                attempt_index=attempt_index,
                prompt_name=current_prompt_name,
                prompt_text=current_prompt,
                raw_response_text=response.text,
                validation=validation,
                diagnostics_used=_diagnostic_messages(validation),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_seconds=response.latency_seconds,
                estimated_cost_usd=response.estimated_cost_usd,
            )
        )
        if validation.accepted:
            break
        current_prompt_name = "repair"
        current_prompt = build_repair_prompt(
            case=case,
            source_code=source_code,
            previous_ir=validation.sanitized_ir or response.text,
            diagnostics=_diagnostic_messages(validation),
        )
    return attempts
