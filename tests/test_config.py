from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_ir_pipeline.config import load_benchmarks, load_model_suite


class ConfigTests(unittest.TestCase):
    def test_model_suite_loads(self) -> None:
        defaults, models = load_model_suite()
        self.assertEqual(defaults["repair_max_attempts"], 3)
        self.assertEqual(len(models), 2)
        self.assertTrue(any(model.access_mode == "local_ollama" for model in models))
        self.assertTrue(any(model.access_mode == "api_gemini" for model in models))

    def test_benchmark_corpus_size_and_splits(self) -> None:
        benchmarks = load_benchmarks()
        self.assertEqual(len(benchmarks), 18)
        splits = {benchmark.split for benchmark in benchmarks}
        self.assertEqual(splits, {"core", "mutated"})


if __name__ == "__main__":
    unittest.main()
