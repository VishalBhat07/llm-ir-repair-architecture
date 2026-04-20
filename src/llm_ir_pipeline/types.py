from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkTest:
    args: list[int]
    expected_return: int


@dataclass
class BenchmarkCase:
    identifier: str
    split: str
    difficulty: str
    tags: list[str]
    source_path: Path
    entry_function: str
    parameter_types: list[str]
    reference_ir_path: Path
    public_tests: list[BenchmarkTest]
    hidden_tests: list[BenchmarkTest]
    source_kind: str = "file"


@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str
    access_mode: str
    base_url: str | None = None
    context_window: int | None = None
    env_api_key: str | None = None
    reasoning_effort: str | None = None
    pricing: dict[str, float | None] = field(default_factory=dict)
    notes: str | None = None
    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 2048
    timeout_seconds: int = 120
    repair_max_attempts: int = 3
    request_max_retries: int = 3
    request_backoff_seconds: float = 2.0
    preflight_timeout_seconds: int = 60


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class ToolchainStatus:
    clang: str | None
    llvm_as: str | None
    opt: str | None
    lli: str | None
    filecheck: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass
class ValidationIssue:
    category: str
    message: str
    line: int | None = None
    severity: str = "error"


@dataclass
class ValidationResult:
    sanitized_ir: str
    parse_ok: bool
    verify_ok: bool
    structural_ok: bool
    semantic_ok: bool
    accepted: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    parse_result: CommandResult | None = None
    verify_result: CommandResult | None = None
    semantic_results: list[dict[str, Any]] = field(default_factory=list)

    def issue_categories(self) -> list[str]:
        return [issue.category for issue in self.issues]


@dataclass
class LLMResponse:
    text: str
    raw_payload: dict[str, Any]
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None
    estimated_cost_usd: float | None = None


@dataclass
class AttemptRecord:
    attempt_index: int
    prompt_name: str
    prompt_text: str
    raw_response_text: str
    validation: ValidationResult
    diagnostics_used: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validation"]["issues"] = [asdict(issue) for issue in self.validation.issues]
        return payload


@dataclass
class RunRecord:
    benchmark_id: str
    split: str
    difficulty: str
    tags: list[str]
    model_name: str
    provider: str
    prompt_name: str
    repair_enabled: bool
    attempts: list[AttemptRecord]
    success: bool
    final_issue_categories: list[str]
    toolchain_available: dict[str, str | None]

    def final_attempt(self) -> AttemptRecord:
        return self.attempts[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "split": self.split,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "model_name": self.model_name,
            "provider": self.provider,
            "prompt_name": self.prompt_name,
            "repair_enabled": self.repair_enabled,
            "success": self.success,
            "final_issue_categories": self.final_issue_categories,
            "toolchain_available": self.toolchain_available,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }
