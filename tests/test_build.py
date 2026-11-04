from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.build import build_site

ROOT = Path(__file__).resolve().parents[1]

VERSION = {
    "schema_version": 1,
    "version": "2.1.2",
    "date": "2026-11-04",
    "source_url": "https://code.claude.com/docs/en/changelog",
    "source_hash": "abc",
    "translation": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "prompt_version": "v1",
        "glossary_version": "v1",
        "translated_at": "2026-11-04T09:00:00Z",
    },
    "groups": [
        {
            "kind": "fixes",
            "heading_en": "5 bug fixes",
            "heading_zh": "5 项修复",
            "items": [
                {
                    "id": "2.1.2-fixes-1",
                    "en": "Fixed a crash when `claude --continue` was used.",
                    "zh": "修复了使用 `claude --continue` 时发生的崩溃。",
                    "hash": "a" * 64,
                    "status": "translated",
                }
            ],
        }
    ],
    "summary": {
        "tldr": "修复了继续会话时的崩溃。",
        "highlights": [
            {
                "title": "继续会话崩溃修复",
                "category": "修复",
                "detail": "使用 --continue 时不再崩溃。",
                "action": None,
                "example": {"lang": "bash", "code": "claude --continue", "caption": None},
                "item_ids": ["2.1.2-fixes-1"],
            }
        ],
        "breaking": False,
    },
}

DIGEST = {
    "schema_version": 1,
    "date": "2026-11-04",
    "versions": ["2.1.2"],
    "tldr": "修复了继续会话时的崩溃。",
    "highlights": [
        {
            "title": "继续会话崩溃修复",
            "category": "修复",
            "detail": "使用 --continue 时不再崩溃。",
            "action": None,
            "example": {"lang": "bash", "code": "claude --continue", "caption": None},
            "version": "2.1.2",
            "item_ids": ["2.1.2-fixes-1"],
        }
    ],
    "breaking": False,
    "summary_hash": "b" * 64,
}


class BuildTests(unittest.TestCase):
    def test_build_outputs_pages_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            (data / "versions").mkdir(parents=True)
            (data / "digests").mkdir(parents=True)
            (data / "versions" / "2.1.2.json").write_text(
                json.dumps(VERSION, ensure_ascii=False), encoding="utf-8"
            )
            (data / "digests" / "2026-11-04.json").write_text(
                json.dumps(DIGEST, ensure_ascii=False), encoding="utf-8"
            )
            dist = root / "dist"
            result = build_site(
                data,
                ROOT / "templates",
                ROOT / "assets",
                dist,
                ROOT / "glossary.yml",
                site_base="/claude-code-changelog-zh",
                site_url="https://example.github.io/claude-code-changelog-zh",
            )

            self.assertEqual(result["versions"], 1)
            self.assertTrue((dist / "index.html").exists())
            self.assertTrue((dist / "v" / "2.1.2" / "index.html").exists())
            self.assertTrue((dist / "archive" / "index.html").exists())
            self.assertTrue((dist / "glossary" / "index.html").exists())
            self.assertTrue((dist / "about" / "index.html").exists())
            self.assertTrue((dist / "assets" / "style.css").exists())
            self.assertTrue((dist / "search" / "index.json").exists())
            self.assertTrue((dist / "rss.xml").exists())
            self.assertTrue((dist / "sitemap.xml").exists())

            index = (dist / "index.html").read_text(encoding="utf-8")
            self.assertIn("Claude Code", index)
            self.assertIn("更新日志", index)
            self.assertIn("2.1.2", index)
            self.assertIn("claude --continue", index)

            version = (dist / "v" / "2.1.2" / "index.html").read_text(encoding="utf-8")
            self.assertIn("修复了使用", version)
            self.assertIn("item-2-1-2-fixes-1", version)

            search = json.loads((dist / "search" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(search), 1)
            self.assertEqual(search[0]["v"], "2.1.2")


if __name__ == "__main__":
    unittest.main()
