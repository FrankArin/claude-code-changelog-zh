from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item_hash(en: str) -> str:
    return sha256_text(normalize_text(en))


def cache_key(
    en: str,
    prompt_version: str,
    glossary_version: str,
    provider: str,
    model: str,
) -> str:
    payload = "\n".join(
        [
            normalize_text(en),
            prompt_version,
            glossary_version,
            provider,
            model,
        ]
    )
    return sha256_text(payload)


def semver_key(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "item"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def extract_code_tokens(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text or "")
