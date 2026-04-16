from __future__ import annotations

from functools import lru_cache
from importlib import resources
import json
import locale
import os
from typing import Any


DEFAULT_LANGUAGE = "en"
LANGUAGE_ENV_VARS = (
    "BG3TOT_LANGUAGE",
    "AP_LANGUAGE",
    "LANGUAGE",
    "LC_ALL",
    "LC_MESSAGES",
    "LANG",
)
LANGUAGE_ALIASES = {
    "english": "en",
    "english-united-states": "en-us",
    "french": "fr",
    "french-france": "fr-fr",
    "german": "de",
    "german-germany": "de-de",
    "italian": "it",
    "italian-italy": "it-it",
    "japanese": "ja",
    "japanese-japan": "ja-jp",
    "korean": "ko",
    "korean-korea": "ko-kr",
    "polish": "pl",
    "polish-poland": "pl-pl",
    "russian": "ru",
    "russian-russia": "ru-ru",
    "spanish": "es",
    "spanish-spain": "es-es",
    "latinspanish": "es-419",
    "spanish-latinamerica": "es-419",
    "spanish-latin-america": "es-419",
    "turkish": "tr",
    "turkish-turkey": "tr-tr",
    "ukrainian": "uk",
    "ukrainian-ukraine": "uk-ua",
    "brazilianportuguese": "pt-br",
    "brazilian-portuguese": "pt-br",
    "portuguese-brazil": "pt-br",
    "portuguese-brazilian": "pt-br",
    "portuguese-brasil": "pt-br",
    "chinese": "zh-cn",
    "chinese-prc": "zh-cn",
    "chinese-simplified": "zh-cn",
    "chinesesimplified": "zh-cn",
    "zh-hans": "zh-cn",
    "chinesetraditional": "zh-tw",
    "chinese-traditional": "zh-tw",
    "traditional-chinese": "zh-tw",
    "chinese-taiwan": "zh-tw",
    "zh-hant": "zh-tw",
}


def _normalize_language(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).strip().replace("_", "-").replace(" ", "-")
    normalized = normalized.split(".", 1)[0].split("@", 1)[0]
    normalized = normalized.lower()
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return LANGUAGE_ALIASES.get(normalized, normalized)


def selected_ui_language() -> str:
    for env_name in LANGUAGE_ENV_VARS:
        candidate = _normalize_language(os.environ.get(env_name))
        if candidate:
            return candidate

    locale_candidate: str | None = None
    try:
        locale_candidate = locale.getlocale()[0]
    except Exception:
        locale_candidate = None

    normalized = _normalize_language(locale_candidate)
    return normalized or DEFAULT_LANGUAGE


def _language_candidates(language: str | None) -> list[str]:
    normalized = _normalize_language(language) or DEFAULT_LANGUAGE
    candidates = [normalized]
    if "-" in normalized:
        candidates.append(normalized.split("-", 1)[0])
    if DEFAULT_LANGUAGE not in candidates:
        candidates.append(DEFAULT_LANGUAGE)
    return candidates


@lru_cache(maxsize=None)
def _load_bundle(language: str) -> dict[str, Any]:
    bundle_path = resources.files(__package__).joinpath("localization", f"{language}.json")
    return json.loads(bundle_path.read_text(encoding="utf-8"))


def _lookup(bundle: dict[str, Any], section: str, key: str) -> str:
    value: Any = bundle[section]
    for part in key.split("."):
        value = value[part]
    if not isinstance(value, str):
        raise TypeError(f"Localization value for {section}.{key} must be a string.")
    return value


def _resolve(section: str, key: str, language: str | None) -> str:
    last_error: Exception | None = None
    for candidate in _language_candidates(language):
        try:
            return _lookup(_load_bundle(candidate), section, key)
        except (FileNotFoundError, KeyError, TypeError) as error:
            last_error = error
    raise KeyError(f"Missing localization key {section}.{key}") from last_error


def _format(template: str, **kwargs: Any) -> str:
    return template.format(**kwargs) if kwargs else template


def canonical_text(key: str, **kwargs: Any) -> str:
    return _format(_resolve("canonical", key, DEFAULT_LANGUAGE), **kwargs)


def ui_text(key: str, *, language: str | None = None, **kwargs: Any) -> str:
    return _format(_resolve("ui", key, language or selected_ui_language()), **kwargs)
