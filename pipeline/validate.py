from __future__ import annotations

import re
from typing import Any

from .util import extract_code_tokens, normalize_text

CATEGORIES = {"新功能", "改进", "修复", "破坏性变更", "安全"}


def validate_translation(en: str, zh: str) -> list[str]:
    errors: list[str] = []
    if not zh or not zh.strip():
        return ["translation is empty"]

    if len(en) > 40 and normalize_text(en) == normalize_text(zh):
        errors.append("translation is identical to English")

    for token in extract_code_tokens(en):
        if token not in zh:
            errors.append(f"missing code token: {token}")

    ratio = len(zh) / max(len(en), 1)
    if ratio < 0.2 or ratio > 2.5:
        errors.append(f"length ratio out of range: {ratio:.2f}")

    return errors


def validate_summary(summary: Any, version_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(summary, dict):
        return ["summary is not an object"]

    tldr = summary.get("tldr")
    if not isinstance(tldr, str) or not tldr.strip():
        errors.append("summary.tldr is empty")
    elif len(tldr) > 120:
        errors.append("summary.tldr is too long")

    highlights = summary.get("highlights")
    if not isinstance(highlights, list) or not (1 <= len(highlights) <= 6):
        errors.append("summary.highlights must contain 1-6 items")
        highlights = []

    item_ids = {
        item["id"]
        for group in version_data.get("groups", [])
        for item in group.get("items", [])
    }

    breaking = False
    for index, highlight in enumerate(highlights):
        prefix = f"summary.highlights[{index}]"
        if not isinstance(highlight, dict):
            errors.append(f"{prefix} is not an object")
            continue
        for field in ("title", "detail"):
            value = highlight.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} is empty")
        if highlight.get("category") not in CATEGORIES:
            errors.append(f"{prefix}.category is invalid")
        if highlight.get("category") == "破坏性变更":
            breaking = True
        ids = highlight.get("item_ids")
        if not isinstance(ids, list) or not ids:
            errors.append(f"{prefix}.item_ids is empty")
        else:
            for item_id in ids:
                if item_id not in item_ids:
                    errors.append(f"{prefix}.item_ids references unknown item: {item_id}")
        example = highlight.get("example")
        if example is not None:
            if not isinstance(example, dict) or not isinstance(example.get("code"), str):
                errors.append(f"{prefix}.example is invalid")
        action = highlight.get("action")
        if action is not None and not isinstance(action, str):
            errors.append(f"{prefix}.action must be a string or null")

    if summary.get("breaking") is True and not breaking:
        errors.append("summary.breaking is true but no breaking highlight exists")
    if breaking and summary.get("breaking") is not True:
        errors.append("summary.breaking must be true when a breaking highlight exists")

    return errors


def ground_examples(summary: dict[str, Any], version_data: dict[str, Any]) -> None:
    items = {
        item["id"]: item
        for group in version_data.get("groups", [])
        for item in group.get("items", [])
    }
    for highlight in summary.get("highlights", []) or []:
        example = highlight.get("example")
        if not example:
            continue
        code = (example or {}).get("code") or ""
        if not code:
            highlight["example"] = None
            continue
        grounded = False
        for item_id in highlight.get("item_ids", []) or []:
            item = items.get(item_id)
            if not item:
                continue
            if code in (item.get("en") or "") or code in (item.get("zh") or ""):
                grounded = True
                break
        if not grounded:
            highlight["example"] = None


ENV_ASSIGN_RE = re.compile(r"^[A-Z][A-Z0-9_]*=\S")


def _example_kind(token: str) -> str | None:
    value = token.strip()
    if not value:
        return None
    if value.startswith(("claude ", "npm ", "git ", "export ", "/")):
        return "command"
    if value.startswith(("{", "[")):
        return "json"
    if value.startswith(("CLAUDE_", "ANTHROPIC_")) and "=" in value:
        return "config"
    if ENV_ASSIGN_RE.match(value):
        return "config"
    if " --" in value:
        return "command"
    if value.startswith(("CLAUDE_", "ANTHROPIC_")):
        return "env_name"
    return None


CAPTIONS = {
    "command": "命令示例",
    "config": "配置示例",
    "env_name": "相关环境变量",
    "json": "配置示例",
}


def fill_examples(summary: dict[str, Any], version_data: dict[str, Any]) -> None:
    items = {
        item["id"]: item
        for group in version_data.get("groups", [])
        for item in group.get("items", [])
    }
    for highlight in summary.get("highlights", []) or []:
        if highlight.get("example"):
            continue
        for item_id in highlight.get("item_ids", []) or []:
            item = items.get(item_id)
            if not item:
                continue
            for token in extract_code_tokens(item.get("en") or ""):
                kind = _example_kind(token)
                if kind:
                    highlight["example"] = {
                        "lang": "json" if kind == "json" else "bash",
                        "code": token,
                        "caption": CAPTIONS[kind],
                    }
                    break
            if highlight.get("example"):
                break


def sanitize_summary(summary: dict[str, Any], version_data: dict[str, Any]) -> dict[str, Any]:
    summary.setdefault("tldr", "")
    summary.setdefault("highlights", [])
    summary.setdefault("breaking", False)
    version = version_data.get("version") or ""
    if version:
        stripped = re.sub(
            rf"^{re.escape(version)}\s*[:：\-–—]?\s*",
            "",
            str(summary.get("tldr") or ""),
        ).strip()
        if len(stripped) >= 10:
            summary["tldr"] = stripped
    ground_examples(summary, version_data)
    fill_examples(summary, version_data)
    return summary
