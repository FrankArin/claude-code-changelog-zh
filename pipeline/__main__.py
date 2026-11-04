from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .build import build_site
from .cache import TranslationCache, write_version
from .fetch import FetchError, fetch_sources
from .parse import merge_versions, parse_docs, parse_raw, version_item_count
from .summarize import (
    day_summary_hash,
    summarize_day,
    summarize_version,
    summary_model,
)
from .translate import PROMPT_VERSION, LLMClient, LLMError, resolve_config, translate_items
from .util import item_hash, read_json, semver_key, utc_now_iso, write_json
from .validate import validate_summary

DOCS_PAGE = "https://code.claude.com/docs/en/changelog"
DEFAULT_MAX_NEW = 20
DEFAULT_BUDGET = 600


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_glossary(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def flatten_items(version_data: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": item["id"], "en": item["en"]}
        for group in version_data.get("groups", [])
        for item in group.get("items", [])
    ]


def load_existing(data_dir: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted((Path(data_dir) / "versions").glob("*.json")):
        data = read_json(path)
        if data and data.get("version"):
            result[data["version"]] = data
    return result


def newest_existing(existing: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not existing:
        return None
    return max(
        existing.values(),
        key=lambda entry: (
            entry.get("date") or "",
            semver_key(entry.get("version") or "0.0.0"),
        ),
    )


def select_candidates(
    merged: list[dict[str, Any]],
    existing: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if getattr(args, "force", False) and not args.all and not args.since:
        candidates = list(merged)
    elif args.all:
        candidates = list(merged)
    elif args.since:
        candidates = [
            entry
            for entry in merged
            if entry.get("date") and entry["date"] >= args.since
        ]
    else:
        newest = newest_existing(existing)
        if newest is None:
            candidates = list(merged)
        else:
            newest_version = semver_key(newest["version"])
            candidates = [
                entry
                for entry in merged
                if semver_key(entry["version"]) > newest_version
                or (
                    newest.get("date")
                    and entry.get("date")
                    and entry["date"] >= newest["date"]
                )
            ]
            changed = [
                entry
                for entry in merged[:50]
                if entry["version"] in existing
                and existing[entry["version"]].get("source_hash") != entry.get("source_hash")
            ]
            seen = {entry["version"] for entry in candidates}
            candidates.extend(entry for entry in changed if entry["version"] not in seen)

    candidates.sort(
        key=lambda entry: (
            entry.get("date") or "",
            semver_key(entry["version"]),
        ),
        reverse=True,
    )
    return candidates[: max(0, args.max_new)]


def process_version(
    entry: dict[str, Any],
    existing: dict[str, Any] | None,
    glossary: dict[str, Any],
    cache: TranslationCache,
    client: LLMClient | None,
    provider: str,
    model: str,
    polish: bool,
    with_summary: bool,
    force: bool = False,
) -> tuple[dict[str, Any], int, list[str]]:
    if (
        not force
        and existing
        and existing.get("source_hash") == entry.get("source_hash")
        and existing.get("summary")
    ):
        return existing, 0, []

    items = flatten_items(entry)
    uncached = sum(
        1
        for item in items
        if not cache.get(item["en"], PROMPT_VERSION, provider, model)
    )

    translated: dict[str, str] = {}
    statuses: dict[str, str] = {}
    errors: list[str] = []
    if uncached:
        if client is None:
            raise LLMError("LLM_API_KEY is required to translate new items")
        translated, statuses, errors = translate_items(
            items,
            glossary,
            client,
            cache,
            provider=provider,
            model=model,
            polish=polish,
        )
    else:
        for item in items:
            translated[item["id"]] = cache.get(
                item["en"], PROMPT_VERSION, provider, model
            ) or ""
            statuses[item["id"]] = "translated" if translated[item["id"]] else "fallback"

    groups = []
    for group in entry.get("groups", []):
        output_items = []
        for item in group.get("items", []):
            item_id = item["id"]
            zh = translated.get(item_id) or ""
            status = statuses.get(item_id, "fallback")
            if not zh:
                status = "fallback"
            output_items.append(
                {
                    "id": item_id,
                    "en": item["en"],
                    "zh": zh,
                    "hash": item.get("hash") or item_hash(item["en"]),
                    "status": status,
                }
            )
        if output_items:
            groups.append(
                {
                    "kind": group.get("kind", "other"),
                    "heading_en": group.get("heading_en", ""),
                    "heading_zh": group.get("heading_zh", ""),
                    "items": output_items,
                }
            )

    data = {
        "schema_version": 1,
        "version": entry["version"],
        "date": entry.get("date"),
        "source_url": DOCS_PAGE,
        "source_hash": entry.get("source_hash"),
        "translation": {
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "glossary_version": (glossary.get("version") or "unversioned"),
            "translated_at": utc_now_iso(),
        },
        "groups": groups,
        "summary": None,
    }

    if with_summary:
        if client is None:
            raise LLMError("LLM_API_KEY is required to generate summaries")
        data["summary"] = summarize_version(data, client, model=summary_model(model))
    elif existing and existing.get("summary"):
        data["summary"] = existing["summary"]

    return data, uncached, errors


def update_digests(
    data_dir: Path,
    versions: list[dict[str, Any]],
    client: LLMClient | None,
) -> tuple[int, list[str]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in versions:
        if entry.get("date"):
            by_date[entry["date"]].append(entry)

    existing: dict[str, dict[str, Any]] = {}
    for path in sorted((Path(data_dir) / "digests").glob("*.json")):
        data = read_json(path)
        if data and data.get("date"):
            existing[data["date"]] = data

    written = 0
    errors: list[str] = []
    for date, entries in sorted(by_date.items(), reverse=True):
        digest_hash = day_summary_hash(entries)
        if (
            date in existing
            and existing[date].get("summary_hash") == digest_hash
            and existing[date].get("highlights")
        ):
            continue

        if client is None:
            errors.append(f"{date}: LLM client is required to build daily digest")
            continue

        summary = summarize_day(date, entries, client)
        digest = {
            "schema_version": 1,
            "date": date,
            "versions": [entry["version"] for entry in entries],
            "tldr": summary.get("tldr") or "",
            "highlights": summary.get("highlights") or [],
            "breaking": bool(summary.get("breaking")),
            "summary_hash": digest_hash,
        }
        write_json(Path(data_dir) / "digests" / f"{date}.json", digest)
        written += 1
    return written, errors


def merge_usage(state: dict[str, Any], client: LLMClient | None) -> None:
    if client is None:
        return
    usage = state.setdefault("usage", {})
    today = utc_now_iso()[:10]
    bucket = usage.setdefault(
        today, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    for key, value in client.usage.items():
        bucket[key] = int(bucket.get(key) or 0) + int(value or 0)
    cutoff = sorted(usage.keys())[-90:]
    state["usage"] = {key: usage[key] for key in cutoff}


def cmd_update(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    glossary = load_glossary(Path(args.glossary))
    state_path = data_dir / "state.json"
    state = read_json(state_path, default={}) or {}
    existing = load_existing(data_dir)

    try:
        sources = fetch_sources(previous_etag=state.get("last_source_etag"))
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    if sources.get("unchanged"):
        print("upstream unchanged; rebuilding from local data")
        result = build_site(
            data_dir,
            Path(args.templates),
            Path(args.assets),
            Path(args.dist),
            Path(args.glossary),
            site_base=os.environ.get("SITE_BASE", ""),
            site_url=os.environ.get("SITE_URL", "http://localhost:8000"),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    try:
        primary = parse_docs(sources["docs_md"], glossary)
        fallback = (
            parse_raw(sources["raw_md"], sources.get("npm_dates") or {}, glossary)
            if sources.get("raw_md")
            else []
        )
    except Exception as exc:  # noqa: BLE001 - report parser failures as exit 1
        print(f"parse failed: {exc}", file=sys.stderr)
        return 1

    merged = merge_versions(primary, fallback)
    if not merged:
        print("parse failed: no versions found", file=sys.stderr)
        return 1

    candidates = select_candidates(merged, existing, args)
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    api_key = os.environ.get("LLM_API_KEY", "")
    provider = base_url.split("://", 1)[-1].split("/", 1)[0] or "openai-compatible"
    cache = TranslationCache(
        Path(args.cache_dir),
        data_dir / "overrides" / "zh-CN.json",
        glossary.get("version") or "unversioned",
    )

    budget = int(os.environ.get("LLM_MAX_ITEMS_PER_RUN", DEFAULT_BUDGET))
    used = 0
    selected = []
    for entry in candidates:
        uncached = sum(
            1
            for item in flatten_items(entry)
            if not cache.get(item["en"], PROMPT_VERSION, provider, model)
        )
        if selected and used + uncached > budget:
            break
        selected.append(entry)
        used += uncached

    needs_llm = used > 0 or (
        not args.no_summary
        and (bool(selected) or args.force)
    )
    client = None
    if needs_llm and api_key:
        client = LLMClient(base_url, model, api_key)
    elif needs_llm and not api_key:
        print("LLM_API_KEY is required for translation or summaries", file=sys.stderr)
        return 3

    errors: list[str] = []
    written_versions = 0
    for entry in selected:
        try:
            data, uncached, version_errors = process_version(
                entry,
                existing.get(entry["version"]),
                glossary,
                cache,
                client,
                provider=provider,
                model=model,
                polish=args.polish,
                with_summary=not args.no_summary,
                force=args.force,
            )
        except LLMError as exc:
            print(f"{entry['version']}: {exc}", file=sys.stderr)
            return 3
        write_version(data_dir, data)
        existing[entry["version"]] = data
        written_versions += 1
        errors.extend(f"{entry['version']}: {message}" for message in version_errors)
        print(
            f"{entry['version']}: {version_item_count(entry)} items, "
            f"{uncached} translated"
        )

    digest_errors: list[str] = []
    if not args.no_summary:
        versions_for_digest = list(existing.values())
        _, digest_errors = update_digests(data_dir, versions_for_digest, client)
        errors.extend(digest_errors)

    if not args.skip_build:
        result = build_site(
            data_dir,
            Path(args.templates),
            Path(args.assets),
            Path(args.dist),
            Path(args.glossary),
            site_base=os.environ.get("SITE_BASE", ""),
            site_url=os.environ.get("SITE_URL", "http://localhost:8000"),
        )
        print(json.dumps(result, ensure_ascii=False))

    state.update(
        {
            "schema_version": 1,
            "last_fetch_at": utc_now_iso(),
            "last_source_etag": sources.get("etag"),
            "last_version": merged[0]["version"],
            "translated_versions": len(existing),
        }
    )
    merge_usage(state, client)
    write_json(state_path, state)

    print(
        f"done: {written_versions} versions written, {used} items sent to the model, "
        f"{len(errors)} warnings"
    )
    if errors:
        for message in errors[:20]:
            print(f"warning: {message}", file=sys.stderr)
        return 2
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    result = build_site(
        Path(args.data_dir),
        Path(args.templates),
        Path(args.assets),
        Path(args.dist),
        Path(args.glossary),
        site_base=os.environ.get("SITE_BASE", ""),
        site_url=os.environ.get("SITE_URL", "http://localhost:8000"),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    versions = load_existing(data_dir)
    errors: list[str] = []

    for version, data in versions.items():
        if data.get("version") != version:
            errors.append(f"{version}: version field mismatch")
        ids = set()
        for group in data.get("groups", []):
            for item in group.get("items", []):
                item_id = item.get("id")
                if item_id in ids:
                    errors.append(f"{version}: duplicate item id {item_id}")
                ids.add(item_id)
                if item.get("status") not in {"translated", "fallback", "needs_review"}:
                    errors.append(f"{version}/{item_id}: invalid status")
                if item.get("hash") != item_hash(item.get("en") or ""):
                    errors.append(f"{version}/{item_id}: hash mismatch")
        if data.get("summary"):
            errors.extend(
                f"{version}: {message}"
                for message in validate_summary(data["summary"], data)
            )

    for path in sorted((data_dir / "digests").glob("*.json")):
        digest = read_json(path)
        if not digest:
            continue
        for version in digest.get("versions", []):
            if version not in versions:
                errors.append(f"digest {digest.get('date')}: unknown version {version}")

    print(
        f"checked {len(versions)} versions, "
        f"{sum(len(group.get('items', [])) for data in versions.values() for group in data.get('groups', []))} items"
    )
    if errors:
        for message in errors[:50]:
            print(f"error: {message}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser("update", help="fetch, translate, summarize, and build")
    update.add_argument("--max-new", type=int, default=DEFAULT_MAX_NEW)
    update.add_argument("--since", help="process versions on or after this ISO date")
    update.add_argument("--all", action="store_true", help="process every missing version")
    update.add_argument("--force", action="store_true", help="reprocess selected versions even if unchanged")
    update.add_argument("--no-polish", action="store_true", dest="no_polish")
    update.add_argument("--no-summary", action="store_true", dest="no_summary")
    update.add_argument("--skip-build", action="store_true", dest="skip_build")
    update.add_argument("--data-dir", default="data")
    update.add_argument("--cache-dir", default="cache")
    update.add_argument("--glossary", default="glossary.yml")
    update.add_argument("--templates", default="templates")
    update.add_argument("--assets", default="assets")
    update.add_argument("--dist", default="dist")
    update.set_defaults(func=cmd_update, polish=True, no_summary=False, force=False)

    build = subparsers.add_parser("build", help="render the static site")
    build.add_argument("--data-dir", default="data")
    build.add_argument("--glossary", default="glossary.yml")
    build.add_argument("--templates", default="templates")
    build.add_argument("--assets", default="assets")
    build.add_argument("--dist", default="dist")
    build.set_defaults(func=cmd_build)

    verify = subparsers.add_parser("verify", help="check data integrity")
    verify.add_argument("--data-dir", default="data")
    verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "update" and getattr(args, "no_polish", False):
        args.polish = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
