from __future__ import annotations

import json
import os
import re
from typing import Any

from .translate import LLMClient, LLMError, _extract_json
from .util import extract_code_tokens, sha256_text
from .validate import CATEGORIES, sanitize_summary, validate_summary

SUMMARY_PROMPT_VERSION = "v1"


def _items_for_prompt(version_data: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for group in version_data.get("groups", []):
        for item in group.get("items", []):
            text = item.get("zh") if item.get("status") == "translated" else item.get("en")
            rows.append(
                {
                    "id": item["id"],
                    "group": group.get("kind", "other"),
                    "text": text or item.get("en") or "",
                    "status": item.get("status", "translated"),
                }
            )
    return rows


def _summary_system_prompt() -> str:
    categories = "、".join(sorted(CATEGORIES))
    return f"""You write concise Chinese release-note summaries for Claude Code developers.

Return valid JSON only:
{{"tldr":"...","highlights":[{{"title":"...","category":"...","detail":"...","action":null,"example":null,"item_ids":["..."]}}],"breaking":false}}

Rules:
- tldr: one sentence, at most 60 Chinese characters.
- highlights: 3-6 items for a normal release; 1-2 when the release has fewer items.
- category must be one of: {categories}.
- Always include breaking changes, changes that require user action, and security fixes.
- Mark 破坏性变更 only for removed or renamed settings/flags, dropped platforms or models, or behavior that requires the user to act. Never mark a bug fix, a restoration, or a new addition as breaking.
- title at most 20 Chinese characters.
- detail at most 120 Chinese characters and explains impact, not a copy of the source line.
- action is a string only when the user must do something; otherwise null.
- example: only when a referenced item already contains a command, flag, path, or config snippet. Copy it verbatim into {{"lang":"bash","code":"...","caption":"..."}}. Never invent an example. Otherwise null.
- item_ids must reference ids from the input.
- breaking is true only when at least one highlight has category 破坏性变更.
- Do not invent features or fixes that are not in the input.
"""


def _fallback_summary(version_data: dict[str, Any]) -> dict[str, Any]:
    rows = _items_for_prompt(version_data)
    highlights = []
    for row in rows[:4]:
        text = row["text"]
        code = None
        tokens = extract_code_tokens(text)
        if tokens:
            code = tokens[0]
        category = {
            "added": "新功能",
            "changed": "改进",
            "improvements": "改进",
            "fixes": "修复",
            "other": "改进",
        }.get(row["group"], "改进")
        title = re.sub(r"\s+", " ", text).strip()[:20]
        highlights.append(
            {
                "title": title or version_data["version"],
                "category": category,
                "detail": re.sub(r"\s+", " ", text).strip()[:120],
                "action": None,
                "example": (
                    {"lang": "bash", "code": code, "caption": None} if code else None
                ),
                "item_ids": [row["id"]],
            }
        )
    return {
        "tldr": f"{version_data['version']} 共 {len(rows)} 项更新",
        "highlights": highlights,
        "breaking": False,
    }


def summarize_version(
    version_data: dict[str, Any],
    client: LLMClient,
    model: str | None = None,
) -> dict[str, Any]:
    rows = _items_for_prompt(version_data)
    if not rows:
        return _fallback_summary(version_data)

    prompt = (
        "Summarize this Claude Code release. Input items:\n"
        + json.dumps({"version": version_data["version"], "items": rows}, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": _summary_system_prompt()},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(2):
        try:
            content = client.chat(messages, json_mode=True)
            summary = _extract_json(content)
            errors = validate_summary(summary, version_data)
            if errors:
                if attempt == 0:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Fix these schema errors and return JSON again: "
                            + "; ".join(errors),
                        }
                    )
                    continue
                raise LLMError("; ".join(errors))
            summary = sanitize_summary(summary, version_data)
            summary["breaking"] = bool(summary.get("breaking"))
            return summary
        except (LLMError, json.JSONDecodeError):
            if attempt == 0:
                continue

    return _fallback_summary(version_data)


def _day_prompt(date: str, versions: list[dict[str, Any]]) -> str:
    payload = {
        "date": date,
        "versions": [
            {
                "version": entry["version"],
                "summary": entry.get("summary") or {},
            }
            for entry in versions
        ],
    }
    return (
        "Aggregate these Claude Code release summaries into one daily digest. "
        "Return JSON with keys tldr, highlights, breaking. Each highlight must include "
        "version and item_ids. Keep 3-6 highlights, prioritize breaking changes and "
        "required user actions. Do not invent anything.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _fallback_day(date: str, versions: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    seen = set()
    for entry in versions:
        for highlight in (entry.get("summary") or {}).get("highlights", []):
            title = highlight.get("title") or ""
            if title in seen:
                continue
            seen.add(title)
            item = dict(highlight)
            item["version"] = entry["version"]
            item.setdefault("example", None)
            highlights.append(item)
            if len(highlights) >= 6:
                break
        if len(highlights) >= 6:
            break
    return {
        "tldr": f"今日共 {len(versions)} 个版本更新",
        "highlights": highlights,
        "breaking": any((entry.get("summary") or {}).get("breaking") for entry in versions),
    }


def summarize_day(
    date: str,
    versions: list[dict[str, Any]],
    client: LLMClient,
) -> dict[str, Any]:
    if len(versions) == 1:
        entry = versions[0]
        summary = dict(entry.get("summary") or _fallback_summary(entry))
        summary["highlights"] = [
            {**highlight, "version": entry["version"]}
            for highlight in summary.get("highlights", [])
        ]
        return summary

    messages = [
        {
            "role": "system",
            "content": (
                "You aggregate Claude Code release summaries into a concise Chinese daily digest. "
                "Return valid JSON only: {\"tldr\":\"...\",\"highlights\":[...],\"breaking\":false}. "
                "Each highlight must include title, category, detail, action, example, version, item_ids."
            ),
        },
        {"role": "user", "content": _day_prompt(date, versions)},
    ]
    try:
        content = client.chat(messages, json_mode=True)
        summary = _extract_json(content)
        if not isinstance(summary, dict):
            raise LLMError("daily summary is not an object")
        summary.setdefault("tldr", "")
        summary.setdefault("highlights", [])
        summary.setdefault("breaking", False)
        if not summary["tldr"] or not (1 <= len(summary["highlights"]) <= 6):
            raise LLMError("daily summary schema is invalid")
        return summary
    except (LLMError, json.JSONDecodeError):
        return _fallback_day(date, versions)


def day_summary_hash(versions: list[dict[str, Any]]) -> str:
    payload = [
        {"version": entry["version"], "summary": entry.get("summary")}
        for entry in sorted(versions, key=lambda item: item["version"])
    ]
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def summary_model(default: str) -> str:
    return os.environ.get("SUMMARY_MODEL") or default
