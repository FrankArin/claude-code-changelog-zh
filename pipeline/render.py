from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

CATEGORY_SLUGS = {
    "新功能": "feature",
    "改进": "improvement",
    "修复": "fix",
    "破坏性变更": "breaking",
    "安全": "security",
}


def anchor(item_id: str) -> str:
    return "item-" + item_id.replace(".", "-")


def category_slug(category: str) -> str:
    return CATEGORY_SLUGS.get(category, "other")


def _num_span(value: str) -> str:
    return f'<span class="num">{value}</span>'


def num_filter(value: Any) -> Markup:
    return Markup(_num_span(str(value)))


def date_cn(value: str | None) -> str | Markup:
    if not value:
        return "日期未知"
    parts = value.split("-")
    if len(parts) != 3:
        return value
    return Markup(
        f"{_num_span(str(int(parts[0])))} 年 "
        f"{_num_span(str(int(parts[1])))} 月 "
        f"{_num_span(str(int(parts[2])))} 日"
    )


def month_cn(value: str | None) -> str | Markup:
    if not value or value == "unknown":
        return "日期未知"
    parts = value.split("-")
    if len(parts) < 2:
        return value
    return Markup(
        f"{_num_span(str(parts[0]))} 年 {_num_span(str(int(parts[1])))} 月"
    )


def inline_md(value: str | None) -> Markup:
    text = html.escape(value or "")
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" rel="noopener noreferrer">\1</a>',
        text,
    )
    return Markup(text)


def create_env(templates_dir: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["anchor"] = anchor
    env.filters["category_slug"] = category_slug
    env.filters["date_cn"] = date_cn
    env.filters["month_cn"] = month_cn
    env.filters["inline_md"] = inline_md
    env.filters["num"] = num_filter
    return env
