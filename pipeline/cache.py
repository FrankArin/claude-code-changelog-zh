from __future__ import annotations

from pathlib import Path
from typing import Any

from .util import cache_key, item_hash, read_json, utc_now_iso, write_json


class TranslationCache:
    def __init__(self, root: Path, overrides_path: Path, glossary_version: str):
        self.root = Path(root) / "translations"
        self.root.mkdir(parents=True, exist_ok=True)
        self.overrides_path = Path(overrides_path)
        self.overrides = read_json(self.overrides_path, default={}) or {}
        self.glossary_version = glossary_version

    def _override(self, en: str) -> str | None:
        items = (self.overrides.get("items") or {}) if isinstance(self.overrides, dict) else {}
        return items.get(item_hash(en))

    def key(self, en: str, prompt_version: str, provider: str, model: str) -> str:
        return cache_key(
            en,
            prompt_version=prompt_version,
            glossary_version=self.glossary_version,
            provider=provider,
            model=model,
        )

    def get(self, en: str, prompt_version: str, provider: str, model: str) -> str | None:
        override = self._override(en)
        if override:
            return override
        key = self.key(en, prompt_version, provider, model)
        path = self.root / f"{key}.json"
        data = read_json(path)
        if not data:
            return None
        return data.get("zh")

    def put(
        self,
        en: str,
        zh: str,
        prompt_version: str,
        provider: str,
        model: str,
    ) -> None:
        key = self.key(en, prompt_version, provider, model)
        write_json(
            self.root / f"{key}.json",
            {
                "schema_version": 1,
                "en": en,
                "zh": zh,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "glossary_version": self.glossary_version,
                "created_at": utc_now_iso(),
            },
        )

    def stats(self) -> dict[str, int]:
        return {"cached_items": len(list(self.root.glob("*.json")))}


def write_version(data_dir: Path, version_data: dict[str, Any]) -> Path:
    path = Path(data_dir) / "versions" / f"{version_data['version']}.json"
    write_json(path, version_data)
    return path
