from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Iterable

from .cache import TranslationCache
from .util import utc_now_iso
from .validate import validate_translation

PROMPT_VERSION = "v1"
MAX_BATCH_ITEMS = 20
MAX_BATCH_CHARS = 7000


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> Any:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise LLMError("model did not return valid JSON")


class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def chat(self, messages: list[dict[str, str]], json_mode: bool = True) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(3):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                usage = data.get("usage") or {}
                for key in self.usage:
                    self.usage[key] += int(usage.get(key) or 0)
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                if not content:
                    raise LLMError("model returned empty content")
                return content
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {body[:300]}"
                if exc.code == 400 and json_mode:
                    json_mode = False
                    payload.pop("response_format", None)
                    continue
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    continue
                raise LLMError(last_error) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = str(exc.reason if hasattr(exc, "reason") else exc)
                time.sleep(2 * (attempt + 1))

        raise LLMError(f"LLM request failed after retries: {last_error}")


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc)
    return "HTTP 401" in message or "HTTP 403" in message


def _glossary_block(glossary: dict[str, Any]) -> str:
    keep = ", ".join(glossary.get("keep_en", []) or [])
    translate = glossary.get("translate", {}) or {}
    mapping = "\n".join(f"- {source} => {target}" for source, target in translate.items())
    style = "\n".join(f"- {line}" for line in glossary.get("style", []) or [])
    return f"""Keep these terms in English exactly as written:
{keep}

Use these translations consistently:
{mapping}

Style:
{style}"""


def _system_prompt(glossary: dict[str, Any], polish: bool = False) -> str:
    base = f"""You are a senior technical translator. Translate Claude Code release notes from English into Simplified Chinese.

Rules:
- Be faithful and complete: do not omit, add, merge, split, or reorder items.
- Keep Markdown structure, bullet count, and inline code intact.
- Never translate text inside backticks, commands, flags, paths, env vars, URLs, issue numbers, or product names.
- Only terms in the keep-English list stay English. Translate every other word into natural Chinese; do not leave whole English phrases untranslated.
- Use concise, natural technical Chinese. Avoid translationese and filler such as "值得注意的是" or "总的来说".
- Output valid JSON only, no Markdown fences.

{_glossary_block(glossary)}
"""
    if polish:
        base += """
You are reviewing a draft Chinese translation. Fix only:
1. mistranslations and missing meaning,
2. awkward or literal phrasing,
3. inconsistent terminology,
4. modified inline code or commands.
Do not expand, summarize, or add information. Keep the same ids and item count.
"""
    return base


def _translate_prompt(items: list[dict[str, str]], glossary: dict[str, Any]) -> str:
    return (
        "Translate every item below. Return JSON in this shape:\n"
        '{"translations":[{"id":"<same id>","zh":"<Chinese translation>"}]}\n\n'
        + json.dumps({"items": items}, ensure_ascii=False)
    )


def _polish_prompt(items: list[dict[str, str]]) -> str:
    return (
        "Polish every translation below. Return JSON in this shape:\n"
        '{"translations":[{"id":"<same id>","zh":"<polished Chinese>"}]}\n\n'
        + json.dumps({"items": items}, ensure_ascii=False)
    )


def _parse_translations(content: str) -> dict[str, str]:
    data = _extract_json(content)
    if isinstance(data, dict):
        rows = data.get("translations") or data.get("items") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        zh = row.get("zh") or row.get("translation")
        if item_id and isinstance(zh, str):
            result[str(item_id)] = zh.strip()
    return result


def _batches(items: list[dict[str, str]]) -> Iterable[list[dict[str, str]]]:
    batch: list[dict[str, str]] = []
    size = 0
    for item in items:
        length = len(item.get("en") or "")
        if batch and (len(batch) >= MAX_BATCH_ITEMS or size + length > MAX_BATCH_CHARS):
            yield batch
            batch = []
            size = 0
        batch.append(item)
        size += length
    if batch:
        yield batch


def _call_translate(
    client: LLMClient, items: list[dict[str, str]], glossary: dict[str, Any]
) -> dict[str, str]:
    content = client.chat(
        [
            {"role": "system", "content": _system_prompt(glossary)},
            {"role": "user", "content": _translate_prompt(items, glossary)},
        ]
    )
    return _parse_translations(content)


def _call_polish(
    client: LLMClient, items: list[dict[str, str]], glossary: dict[str, Any]
) -> dict[str, str]:
    content = client.chat(
        [
            {"role": "system", "content": _system_prompt(glossary, polish=True)},
            {"role": "user", "content": _polish_prompt(items)},
        ]
    )
    return _parse_translations(content)


def translate_items(
    items: list[dict[str, str]],
    glossary: dict[str, Any],
    client: LLMClient,
    cache: TranslationCache,
    provider: str,
    model: str,
    polish: bool = True,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Return (translations, statuses, errors).

    Items are dicts with at least id and en. Status is translated / fallback /
    needs_review. Cached entries are returned without calling the model.
    """
    translations: dict[str, str] = {}
    statuses: dict[str, str] = {}
    errors: list[str] = []
    pending: list[dict[str, str]] = []

    for item in items:
        cached = cache.get(item["en"], PROMPT_VERSION, provider, model)
        if cached:
            translations[item["id"]] = cached
            statuses[item["id"]] = "translated"
        else:
            pending.append(item)

    for batch in _batches(pending):
        try:
            result = _call_translate(client, batch, glossary)
        except LLMError as exc:
            if _is_auth_error(exc):
                raise
            errors.append(f"translate batch failed: {exc}")
            for item in batch:
                statuses[item["id"]] = "fallback"
            continue

        good: list[dict[str, str]] = []
        for item in batch:
            zh = result.get(item["id"], "")
            item_errors = validate_translation(item["en"], zh)
            if item_errors:
                errors.append(f"{item['id']}: {'; '.join(item_errors)}")
                good.append(item)
            else:
                translations[item["id"]] = zh
                statuses[item["id"]] = "translated"

        if good:
            try:
                retry = _call_translate(client, good, glossary)
            except LLMError as exc:
                if _is_auth_error(exc):
                    raise
                retry = {}
            for item in good:
                zh = retry.get(item["id"], "")
                item_errors = validate_translation(item["en"], zh)
                if item_errors:
                    errors.append(f"{item['id']} retry: {'; '.join(item_errors)}")
                    statuses[item["id"]] = "needs_review"
                else:
                    translations[item["id"]] = zh
                    statuses[item["id"]] = "translated"

    if polish:
        polish_items = [
            {"id": item["id"], "en": item["en"], "zh": translations[item["id"]]}
            for item in pending
            if item["id"] in translations
        ]
        for batch in _batches(polish_items):
            try:
                polished = _call_polish(client, batch, glossary)
            except LLMError as exc:
                if _is_auth_error(exc):
                    raise
                errors.append(f"polish batch failed: {exc}")
                continue
            for item in batch:
                zh = polished.get(item["id"], "")
                if zh and not validate_translation(item["en"], zh):
                    translations[item["id"]] = zh

    for item in pending:
        if item["id"] not in translations:
            translations[item["id"]] = ""
            statuses.setdefault(item["id"], "fallback")
            continue
        cache.put(
            item["en"],
            translations[item["id"]],
            PROMPT_VERSION,
            provider,
            model,
        )

    return translations, statuses, errors


def resolve_config() -> tuple[str, str, str]:
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise LLMError("LLM_API_KEY is not set")
    return base_url, model, api_key


def usage_snapshot(client: LLMClient) -> dict[str, Any]:
    return {"usage": dict(client.usage), "at": utc_now_iso()}
