from __future__ import annotations

import json
from pathlib import Path

from .types import BenchmarkCase, BenchmarkTest, ModelConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_model_suite(config_path: Path | None = None) -> tuple[dict[str, object], list[ModelConfig]]:
    config_path = config_path or (REPO_ROOT / "configs" / "models.yaml")
    data = _read_json(config_path)
    defaults = data.get("defaults", {})
    models: list[ModelConfig] = []
    for raw_model in data.get("models", []):
        merged = {**defaults, **raw_model}
        models.append(ModelConfig(**merged))
    return defaults, models


def _load_manifest(path: Path) -> list[dict[str, object]]:
    data = _read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Manifest must be a list: {path}")
    return data


def load_benchmarks(metadata_dir: Path | None = None, splits: set[str] | None = None) -> list[BenchmarkCase]:
    metadata_dir = metadata_dir or (REPO_ROOT / "benchmarks" / "metadata")
    manifests = sorted(metadata_dir.glob("*_manifest.json"))
    cases: list[BenchmarkCase] = []
    for manifest_path in manifests:
        for raw_case in _load_manifest(manifest_path):
            split = raw_case["split"]
            if splits and split not in splits:
                continue
            cases.append(
                BenchmarkCase(
                    identifier=raw_case["id"],
                    split=split,
                    difficulty=raw_case["difficulty"],
                    tags=list(raw_case["tags"]),
                    source_path=REPO_ROOT / raw_case["source_path"],
                    entry_function=raw_case["entry_function"],
                    parameter_types=list(raw_case["parameter_types"]),
                    reference_ir_path=REPO_ROOT / raw_case["reference_ir_path"],
                    public_tests=[BenchmarkTest(**item) for item in raw_case["public_tests"]],
                    hidden_tests=[BenchmarkTest(**item) for item in raw_case["hidden_tests"]],
                    source_kind=raw_case.get("source_kind", "file"),
                )
            )
    return sorted(cases, key=lambda item: item.identifier)


def load_invalid_ir_manifest(path: Path | None = None) -> list[dict[str, object]]:
    path = path or (REPO_ROOT / "benchmarks" / "invalid_ir" / "manifest.json")
    items = _load_manifest(path)
    for item in items:
        item["path"] = str(REPO_ROOT / str(item["path"]))
    return items


def read_source(case: BenchmarkCase) -> str:
    return case.source_path.read_text(encoding="utf-8")
