from __future__ import annotations

import unittest

from pipeline.validate import ground_examples, validate_summary, validate_translation

VERSION = {
    "version": "2.1.2",
    "groups": [
        {
            "kind": "fixes",
            "items": [
                {
                    "id": "2.1.2-fixes-1",
                    "en": "Fixed a crash when `claude --continue` was used.",
                    "zh": "修复了使用 `claude --continue` 时发生的崩溃。",
                    "status": "translated",
                }
            ],
        }
    ],
}


class ValidateTests(unittest.TestCase):
    def test_translation_accepts_good_output(self) -> None:
        self.assertEqual(
            validate_translation(
                "Fixed a crash when `claude --continue` was used.",
                "修复了使用 `claude --continue` 时发生的崩溃。",
            ),
            [],
        )

    def test_translation_rejects_missing_code(self) -> None:
        errors = validate_translation(
            "Fixed a crash when `claude --continue` was used.",
            "修复了使用 continue 时发生的崩溃。",
        )
        self.assertTrue(any("missing code token" in error for error in errors))

    def test_translation_rejects_identical_long_text(self) -> None:
        text = "Fixed a crash when `claude --continue` was used in a session."
        errors = validate_translation(text, text)
        self.assertTrue(any("identical" in error for error in errors))

    def test_summary_accepts_valid(self) -> None:
        summary = {
            "tldr": "修复了继续会话时的崩溃。",
            "highlights": [
                {
                    "title": "继续会话崩溃修复",
                    "category": "修复",
                    "detail": "使用 --continue 时不再崩溃。",
                    "action": None,
                    "example": None,
                    "item_ids": ["2.1.2-fixes-1"],
                }
            ],
            "breaking": False,
        }
        self.assertEqual(validate_summary(summary, VERSION), [])

    def test_summary_rejects_unknown_item(self) -> None:
        summary = {
            "tldr": "修复。",
            "highlights": [
                {
                    "title": "修复",
                    "category": "修复",
                    "detail": "详情",
                    "action": None,
                    "example": None,
                    "item_ids": ["missing"],
                }
            ],
            "breaking": False,
        }
        errors = validate_summary(summary, VERSION)
        self.assertTrue(any("unknown item" in error for error in errors))

    def test_example_must_be_grounded(self) -> None:
        summary = {
            "tldr": "修复。",
            "highlights": [
                {
                    "title": "修复",
                    "category": "修复",
                    "detail": "详情",
                    "action": None,
                    "example": {"code": "claude --invented"},
                    "item_ids": ["2.1.2-fixes-1"],
                }
            ],
            "breaking": False,
        }
        ground_examples(summary, VERSION)
        self.assertIsNone(summary["highlights"][0]["example"])

    def test_example_grounding_keeps_real_code(self) -> None:
        summary = {
            "tldr": "修复。",
            "highlights": [
                {
                    "title": "修复",
                    "category": "修复",
                    "detail": "详情",
                    "action": None,
                    "example": {"code": "claude --continue"},
                    "item_ids": ["2.1.2-fixes-1"],
                }
            ],
            "breaking": False,
        }
        ground_examples(summary, VERSION)
        self.assertIsNotNone(summary["highlights"][0]["example"])


if __name__ == "__main__":
    unittest.main()
