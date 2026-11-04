from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from pipeline.parse import merge_versions, parse_date, parse_docs, parse_raw

ROOT = Path(__file__).resolve().parents[1]


def glossary() -> dict:
    with (ROOT / "glossary.yml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class ParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = (ROOT / "tests" / "fixtures" / "changelog_sample.md").read_text(
            encoding="utf-8"
        )
        self.versions = parse_docs(self.sample, glossary())

    def test_parse_date(self) -> None:
        self.assertEqual(parse_date("November 4, 2026"), "2026-11-04")
        self.assertIsNone(parse_date("not a date"))

    def test_version_count_and_order(self) -> None:
        self.assertEqual([v["version"] for v in self.versions], ["2.1.2", "2.1.1", "2.1.0"])
        self.assertEqual(self.versions[0]["date"], "2026-11-04")

    def test_groups_and_continuation(self) -> None:
        groups = self.versions[0]["groups"]
        self.assertEqual([g["kind"] for g in groups], ["added", "improvements", "fixes"])
        self.assertEqual([g["heading_zh"] for g in groups], ["新增", "3 项改进", "5 项修复"])
        self.assertEqual(len(groups[0]["items"]), 2)
        self.assertIn("that accepts `ask` and `auto`", groups[0]["items"][1]["en"])

    def test_no_group_heading(self) -> None:
        groups = self.versions[1]["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["kind"], "other")
        self.assertEqual(len(groups[0]["items"]), 1)

    def test_item_ids_unique_and_hashes_present(self) -> None:
        ids = []
        for version in self.versions:
            for group in version["groups"]:
                for item in group["items"]:
                    ids.append(item["id"])
                    self.assertEqual(len(item["hash"]), 64)
        self.assertEqual(len(ids), len(set(ids)))

    def test_raw_parse_and_merge_fills_missing(self) -> None:
        raw = """## 2.1.3

- Added a raw-only release.

## 2.1.2

- Added a `foo` command for inspecting sessions.
"""
        raw_versions = parse_raw(raw, {"2.1.3": "2026-11-05"}, glossary())
        merged = merge_versions(self.versions, raw_versions)
        self.assertEqual(merged[0]["version"], "2.1.3")
        self.assertEqual(merged[0]["date"], "2026-11-05")
        self.assertEqual(len(merged), 4)


if __name__ == "__main__":
    unittest.main()
