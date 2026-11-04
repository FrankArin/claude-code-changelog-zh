from __future__ import annotations

import html
import json
import os
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import yaml

from .render import create_env
from .util import read_json, semver_key, write_json, write_text

SITE_NAME = "Claude Code 中文更新日志"
SITE_DESCRIPTION = (
    "Claude Code 官方 changelog 的非官方简体中文翻译，摘要优先，支持逐条中英对照和全文搜索。"
)
MAX_SEARCH_BYTES = 2 * 1024 * 1024


def _load_overrides(data_dir: Path) -> dict[str, str]:
    data = read_json(Path(data_dir) / "overrides" / "zh-CN.json", default={}) or {}
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, dict) else {}


def _apply_overrides(version: dict[str, Any], overrides: dict[str, str]) -> None:
    for group in version.get("groups", []):
        for item in group.get("items", []):
            zh = overrides.get(item.get("hash") or "")
            if zh:
                item["zh"] = zh
                item["status"] = "translated"


def _load_versions(data_dir: Path) -> list[dict[str, Any]]:
    versions = []
    overrides = _load_overrides(data_dir)
    for path in sorted((data_dir / "versions").glob("*.json")):
        data = read_json(path)
        if data:
            _apply_overrides(data, overrides)
            versions.append(data)

    def sort_key(entry: dict[str, Any]) -> tuple[int, str, tuple[int, ...]]:
        return (
            1 if entry.get("date") else 0,
            entry.get("date") or "",
            semver_key(entry.get("version") or "0.0.0"),
        )

    versions.sort(key=sort_key, reverse=True)
    return versions


def _load_digests(data_dir: Path) -> list[dict[str, Any]]:
    digests = []
    for path in sorted((data_dir / "digests").glob("*.json")):
        data = read_json(path)
        if data:
            digests.append(data)
    digests.sort(key=lambda entry: entry.get("date") or "", reverse=True)
    return digests


def _item_count(version: dict[str, Any]) -> int:
    return sum(len(group.get("items", [])) for group in version.get("groups", []))


def _changes(version: dict[str, Any]) -> dict[str, int]:
    result = {"added": 0, "changed": 0, "improvements": 0, "fixes": 0, "other": 0}
    for group in version.get("groups", []):
        result[group.get("kind", "other")] = result.get(group.get("kind", "other"), 0) + len(
            group.get("items", [])
        )
    return result


def _fallback_days(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for version in versions:
        if version.get("date"):
            by_date.setdefault(version["date"], []).append(version)

    days = []
    for date, entries in sorted(by_date.items(), reverse=True):
        highlights = []
        for entry in entries:
            for highlight in (entry.get("summary") or {}).get("highlights", [])[:2]:
                highlights.append({**highlight, "version": entry["version"]})
        days.append(
            {
                "date": date,
                "versions": [entry["version"] for entry in entries],
                "tldr": f"今日共 {len(entries)} 个版本更新",
                "highlights": highlights[:6],
                "breaking": any(
                    (entry.get("summary") or {}).get("breaking") for entry in entries
                ),
                "version_entries": entries,
            }
        )
    return days


def _prepare_days(
    versions: list[dict[str, Any]], digests: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_version = {entry["version"]: entry for entry in versions}
    days = []
    for digest in digests:
        entries = [by_version[v] for v in digest.get("versions", []) if v in by_version]
        if not entries:
            continue
        days.append({**digest, "version_entries": entries})
    known = {day["date"] for day in days}
    for day in _fallback_days(versions):
        if day["date"] not in known:
            days.append(day)
    days.sort(key=lambda entry: entry.get("date") or "", reverse=True)
    return days


def _version_links(versions: list[dict[str, Any]]) -> None:
    for index, version in enumerate(versions):
        version["prev"] = versions[index - 1] if index > 0 else None
        version["next"] = versions[index + 1] if index + 1 < len(versions) else None
        version["item_count"] = _item_count(version)
        version["changes"] = _changes(version)


def _search_rows(versions: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for version in versions:
        for group in version.get("groups", []):
            for item in group.get("items", []):
                rows.append(
                    {
                        "v": version["version"],
                        "d": version.get("date") or "",
                        "g": group.get("kind", "other"),
                        "id": item["id"],
                        "zh": item.get("zh") or "",
                        "en": item.get("en") or "",
                    }
                )
    return rows


def _write_search(dist: Path, rows: list[dict[str, str]]) -> None:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    search_dir = dist / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    if len(payload) <= MAX_SEARCH_BYTES:
        (search_dir / "index.json").write_bytes(payload)
        return

    shards: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        year = (row.get("d") or "unknown")[:4]
        shards.setdefault(year, []).append(row)
    for year, shard_rows in shards.items():
        (search_dir / f"{year}.json").write_text(
            json.dumps(shard_rows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    write_json(
        search_dir / "index.json",
        {"shards": sorted(shards.keys(), reverse=True), "latest": sorted(shards.keys(), reverse=True)[0]},
    )


def _rss(dist: Path, days: list[dict[str, Any]], site_url: str) -> None:
    now = datetime.now(timezone.utc)
    items = []
    for day in days[:30]:
        link = f"{site_url}/#day-{day['date']}"
        description_parts = [day.get("tldr") or ""]
        for highlight in day.get("highlights", []):
            description_parts.append(f"- {highlight.get('title', '')}：{highlight.get('detail', '')}")
        description = "\n".join(part for part in description_parts if part)
        try:
            published = datetime.fromisoformat(day["date"] + "T00:00:00+00:00")
        except (KeyError, ValueError):
            published = now
        items.append(
            "<item>"
            f"<title>{html.escape(day.get('date', '') + ' 更新')}</title>"
            f"<link>{html.escape(link)}</link>"
            f"<guid isPermaLink=\"false\">{html.escape(link)}</guid>"
            f"<pubDate>{format_datetime(published)}</pubDate>"
            f"<description><![CDATA[{description.replace(']]>', ']]&gt;')}]]></description>"
            "</item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{html.escape(SITE_NAME)}</title>"
        f"<link>{html.escape(site_url)}</link>"
        f"<description>{html.escape(SITE_DESCRIPTION)}</description>"
        f"<language>zh-CN</language>"
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    write_text(dist / "rss.xml", xml)


def _sitemap(
    dist: Path,
    versions: list[dict[str, Any]],
    site_url: str,
) -> None:
    urls = [
        ("/", versions[0].get("date") if versions else None),
        ("/archive/", versions[0].get("date") if versions else None),
        ("/glossary/", None),
        ("/about/", None),
    ]
    for version in versions:
        urls.append((f"/v/{version['version']}/", version.get("date")))

    body = []
    for path, lastmod in urls:
        entry = f"<url><loc>{html.escape(site_url + path)}</loc>"
        if lastmod:
            entry += f"<lastmod>{html.escape(lastmod)}</lastmod>"
        entry += "</url>"
        body.append(entry)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(body)
        + "</urlset>\n"
    )
    write_text(dist / "sitemap.xml", xml)


def build_site(
    data_dir: Path,
    templates_dir: Path,
    assets_dir: Path,
    dist_dir: Path,
    glossary_path: Path,
    site_base: str = "",
    site_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    data_dir = Path(data_dir)
    dist = Path(dist_dir)
    versions = _load_versions(data_dir)
    if not versions:
        raise ValueError("No version data found. Run `python -m pipeline update` first.")

    digests = _load_digests(data_dir)
    days = _prepare_days(versions, digests)
    _version_links(versions)

    with Path(glossary_path).open("r", encoding="utf-8") as fh:
        glossary = yaml.safe_load(fh) or {}

    site_base = (site_base or "").rstrip("/")
    site_url = (site_url or "").rstrip("/")
    env = create_env(Path(templates_dir))

    def url(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{site_base}{path}"

    env.globals["url"] = url
    env.globals["site_name"] = SITE_NAME
    env.globals["site_description"] = SITE_DESCRIPTION
    env.globals["site_url"] = site_url
    env.globals["site_base"] = site_base
    env.globals["build_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True, exist_ok=True)
    shutil.copytree(assets_dir, dist / "assets", dirs_exist_ok=True)

    latest = versions[0]
    total_items = sum(version["item_count"] for version in versions)
    stats = {
        "versions": len(versions),
        "items": total_items,
        "latest": latest["version"],
        "latest_date": latest.get("date"),
    }

    month_map: dict[str, list[dict[str, Any]]] = {}
    for version in versions:
        key = (version.get("date") or "unknown")[:7]
        month_map.setdefault(key, []).append(version)
    months = [
        {"key": key, "versions": month_map[key]}
        for key in sorted(month_map.keys(), reverse=True)
    ]

    def render(template: str, out: Path, **context: Any) -> None:
        page = env.get_template(template)
        content = page.render(
            versions=versions,
            days=days,
            glossary=glossary,
            stats=stats,
            latest=latest,
            home_days=days[:7],
            months=months,
            **context,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8", newline="\n")

    render(
        "index.html",
        dist / "index.html",
        page_title=SITE_NAME,
        canonical=f"{site_url}/",
        page_description=SITE_DESCRIPTION,
    )
    for version in versions:
        render(
            "version.html",
            dist / "v" / version["version"] / "index.html",
            page_title=f"Claude Code {version['version']} 更新日志（中文翻译）",
            canonical=f"{site_url}/v/{version['version']}/",
            page_description=(version.get("summary") or {}).get("tldr")
            or f"Claude Code {version['version']} 更新日志中文翻译",
            version=version,
        )
    render(
        "archive.html",
        dist / "archive" / "index.html",
        page_title=f"归档 - {SITE_NAME}",
        canonical=f"{site_url}/archive/",
        page_description="按月份浏览全部 Claude Code 版本更新。",
    )
    render(
        "glossary.html",
        dist / "glossary" / "index.html",
        page_title=f"术语表 - {SITE_NAME}",
        canonical=f"{site_url}/glossary/",
        page_description="本站统一使用的 Claude Code 术语译法。",
    )
    render(
        "about.html",
        dist / "about" / "index.html",
        page_title=f"关于 - {SITE_NAME}",
        canonical=f"{site_url}/about/",
        page_description="本站的数据来源、翻译方法、更新频率和非官方声明。",
    )
    render(
        "404.html",
        dist / "404.html",
        page_title=f"页面不存在 - {SITE_NAME}",
        canonical=f"{site_url}/404.html",
        page_description="页面不存在。",
    )

    _write_search(dist, _search_rows(versions))
    _rss(dist, days, site_url)
    _sitemap(dist, versions, site_url)
    write_text(
        dist / "robots.txt",
        "User-agent: *\nAllow: /\n" + f"Sitemap: {site_url}/sitemap.xml\n",
    )

    return {
        "versions": len(versions),
        "days": len(days),
        "items": total_items,
        "dist": str(dist),
        "site_base": site_base,
        "site_url": site_url,
    }
