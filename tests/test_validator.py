from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_ir_pipeline.config import load_invalid_ir_manifest
from llm_ir_pipeline.validator import sanitize_ir_text, structural_checks


class ValidatorTests(unittest.TestCase):
    def test_sanitize_ir_text_removes_markdown(self) -> None:
        raw = "Here is your IR:\n```llvm\ndefine i32 @f() {\nentry:\n  ret i32 0\n}\n```"
        cleaned = sanitize_ir_text(raw)
        self.assertTrue(cleaned.startswith("define i32 @f()"))
        self.assertNotIn("```", cleaned)

    def test_invalid_ir_manifest_categories_are_detected(self) -> None:
        manifest = load_invalid_ir_manifest()
        for item in manifest:
            ir_text = Path(item["path"]).read_text(encoding="utf-8")
            categories = {issue.category for issue in structural_checks(ir_text)}
            expected = set(item["expected_categories"])
            self.assertTrue(expected & categories)


if __name__ == "__main__":
    unittest.main()
