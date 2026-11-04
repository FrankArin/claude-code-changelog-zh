from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DOCS_URL = "https://code.claude.com/docs/en/changelog.md"
RAW_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
NPM_URL = "https://registry.npmjs.org/@anthropic-ai/claude-code"
USER_AGENT = (
    "claude-code-changelog-zh/0.1 "
    "(+https://github.com/FrankArin/claude-code-changelog-zh)"
)


class FetchError(RuntimeError):
    pass


def fetch_text(
    url: str, etag: str | None = None, timeout: int = 90
) -> tuple[str | None, str | None, int]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if etag:
        request.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace"), response.headers.get("ETag"), response.status
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, etag, 304
        raise FetchError(f"GET {url} failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"GET {url} failed: {exc.reason}") from exc


def fetch_npm_dates(timeout: int = 60) -> dict[str, str]:
    text, _, _ = fetch_text(NPM_URL, timeout=timeout)
    if not text:
        return {}
    data = json.loads(text)
    dates = {}
    for version, value in (data.get("time") or {}).items():
        if isinstance(value, str) and len(value) >= 10:
            dates[version] = value[:10]
    return dates


def fetch_sources(previous_etag: str | None = None) -> dict[str, Any]:
    docs_md, etag, status = fetch_text(DOCS_URL, etag=previous_etag)
    if status == 304:
        return {"unchanged": True, "docs_md": None, "etag": etag}

    raw_md = None
    try:
        raw_md, _, _ = fetch_text(RAW_URL)
    except FetchError:
        raw_md = None

    try:
        npm_dates = fetch_npm_dates()
    except (FetchError, json.JSONDecodeError):
        npm_dates = {}

    return {
        "unchanged": False,
        "docs_md": docs_md,
        "raw_md": raw_md,
        "npm_dates": npm_dates,
        "etag": etag,
    }
