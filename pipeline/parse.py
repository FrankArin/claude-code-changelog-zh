from __future__ import annotations

import re
from typing import Any

from .util import item_hash, semver_key, sha256_text

MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

DATE_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s*(\d{4})\s*$"
)
DOCS_VERSION_RE = re.compile(r"^\*\*(\d+\.\d+\.\d+)\*\*[ \t]*$", re.MULTILINE)
RAW_VERSION_RE = re.compile(
    r"^##[ \t]+\[?(\d+\.\d+\.\d+)\]?(?:[ \t]+-[ \t]+[^\n]+)?[ \t]*$",
    re.MULTILINE,
)
HEADING_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
BULLET_RE = re.compile(r"^[*-]\s+(.*)$")
IMPROVEMENTS_RE = re.compile(r"^(\d+)\s+improvements?$", re.IGNORECASE)
FIXES_RE = re.compile(r"^(\d+)\s+bug\s*fixes?$", re.IGNORECASE)


class ParseError(ValueError):
    pass


def parse_date(text: str) -> str | None:
    match = DATE_RE.match(text.strip())
    if not match:
        return None
    month, day, year = match.groups()
    return f"{int(year):04d}-{MONTHS[month]:02d}-{int(day):02d}"


def classify_heading(text: str, glossary: dict[str, Any]) -> tuple[str, str]:
    raw = text.strip()
    low = raw.lower()
    translations = glossary.get("translate", {}) or {}

    if low.startswith("added"):
        return "added", translations.get("Added", "新增")
    if low.startswith("changed"):
        return "changed", translations.get("Changed", "变更")
    if low.startswith("changes"):
        return "changed", translations.get("Changes", "变更")
    if low.startswith("improved"):
        return "improvements", translations.get("Improved", "改进")

    match = IMPROVEMENTS_RE.match(raw)
    if match:
        return "improvements", f"{match.group(1)} 项改进"

    match = FIXES_RE.match(raw)
    if match:
        return "fixes", f"{match.group(1)} 项修复"

    translated = translations.get(raw) or translations.get(low)
    return "other", translated or raw


def _append_item(items: list[str], line: str) -> None:
    text = line.strip()
    if items:
        items[-1] = f"{items[-1]} {text}".strip()
    else:
        items.append(text)


def _parse_block(block: str, glossary: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    date = None
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    items: list[str] = []

    def flush() -> None:
        nonlocal current, items
        if current is not None:
            current["items_text"] = items
            groups.append(current)
        current = None
        items = []

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parsed_date = parse_date(stripped)
        if parsed_date:
            date = parsed_date
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            flush()
            heading_en = heading.group(1).strip()
            kind, heading_zh = classify_heading(heading_en, glossary)
            current = {
                "kind": kind,
                "heading_en": heading_en,
                "heading_zh": heading_zh,
            }
            continue

        bullet = BULLET_RE.match(stripped)
        if bullet:
            if current is None:
                current = {
                    "kind": "other",
                    "heading_en": "Changes",
                    "heading_zh": (glossary.get("translate", {}) or {}).get("Changed", "变更"),
                }
            items.append(bullet.group(1).strip())
            continue

        if current is not None and items:
            _append_item(items, stripped)

    flush()
    return date, groups


def _finalize_items(version: str, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    counter = 0
    for group in groups:
        texts = group.pop("items_text", [])
        items = []
        for text in texts:
            if not text:
                continue
            counter += 1
            items.append(
                {
                    "id": f"{version}-{group['kind']}-{counter}",
                    "en": text,
                    "zh": None,
                    "hash": item_hash(text),
                    "status": "pending",
                }
            )
        if items:
            group["items"] = items
            result.append(group)
    return result


def parse_docs(markdown: str, glossary: dict[str, Any]) -> list[dict[str, Any]]:
    parts = DOCS_VERSION_RE.split(markdown)
    if len(parts) < 3:
        raise ParseError("No version blocks found in docs changelog")

    versions = []
    for index in range(1, len(parts) - 1, 2):
        version = parts[index]
        block = parts[index + 1].strip()
        date, groups = _parse_block(block, glossary)
        finalized = _finalize_items(version, groups)
        versions.append(
            {
                "version": version,
                "date": date,
                "source_hash": sha256_text(block),
                "groups": finalized,
            }
        )
    return versions


def parse_raw(
    markdown: str, dates: dict[str, str], glossary: dict[str, Any]
) -> list[dict[str, Any]]:
    parts = RAW_VERSION_RE.split(markdown)
    if len(parts) < 3:
        return []

    versions = []
    for index in range(1, len(parts) - 1, 2):
        version = parts[index]
        block = parts[index + 1].strip()
        items_text = []
        for line in block.splitlines():
            bullet = BULLET_RE.match(line.strip())
            if bullet:
                items_text.append(bullet.group(1).strip())
            elif items_text and line.strip():
                _append_item(items_text, line.strip())
        if not items_text:
            continue
        group = {
            "kind": "other",
            "heading_en": "Changes",
            "heading_zh": (glossary.get("translate", {}) or {}).get("Changed", "变更"),
        }
        group["items_text"] = items_text
        versions.append(
            {
                "version": version,
                "date": dates.get(version),
                "source_hash": sha256_text(block),
                "groups": _finalize_items(version, [group]),
            }
        )
    return versions


def merge_versions(
    primary: list[dict[str, Any]], fallback: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_version = {entry["version"]: entry for entry in primary}
    for entry in fallback:
        existing = by_version.get(entry["version"])
        if existing is None:
            by_version[entry["version"]] = entry
            continue
        if not existing.get("date") and entry.get("date"):
            existing["date"] = entry["date"]
        if not existing.get("groups") and entry.get("groups"):
            existing["groups"] = entry["groups"]

    def sort_key(entry: dict[str, Any]) -> tuple[int, str, tuple[int, ...]]:
        return (
            1 if entry.get("date") else 0,
            entry.get("date") or "",
            semver_key(entry["version"]),
        )

    return sorted(by_version.values(), key=sort_key, reverse=True)


def version_item_count(entry: dict[str, Any]) -> int:
    return sum(len(group.get("items", [])) for group in entry.get("groups", []))
