from __future__ import annotations

from dataclasses import dataclass
import html
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
BG3_LOCALIZATION_ROOT = ROOT / "src" / "archipelago_tot_mod" / "source" / "Localization"
AP_LOCALIZATION_ROOT = ROOT / "src" / "apworld" / "bg3tot" / "localization"
ENGLISH_TOT_JSON = BG3_LOCALIZATION_ROOT / "English" / "ToT.json"
ENGLISH_TOT_SUMMONS_XML = BG3_LOCALIZATION_ROOT / "English" / "TotSummons.xml"
ENGLISH_AP_JSON = AP_LOCALIZATION_ROOT / "en.json"

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_TRANSLATE_URL = "https://api.mymemory.translated.net/get"
MAX_BATCH_CHARS = 4000
MAX_BATCH_ITEMS = 25
REQUEST_TIMEOUT_SECONDS = 60
REQUEST_RETRY_DELAYS_SECONDS = (5.0, 10.0, 20.0, 40.0)
MIN_REQUEST_INTERVAL_SECONDS = 0.5
TRANSLATION_PROVIDER = os.environ.get("BG3TOT_TRANSLATION_PROVIDER", "mymemory").strip().lower()
TRANSLATION_CACHE_PATH = Path(tempfile.gettempdir()) / "bg3tot_translation_cache.json"

PRINTF_PATTERN = re.compile(
    r"%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[A-Za-z%]"
)
BRACE_PATTERN = re.compile(r"\{[^{}]+\}")
BACKTICK_PATTERN = re.compile(r"`[^`]+`")
NEWLINE_PATTERN = re.compile(r"\n")
GLOSSARY_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"Baldur's Gate 3 - ToT",
        r"Baldur's Gate 3",
        r"Trials of Tav",
        r"Script Extender",
        r"\bArchipelago\b",
        r"\bDeathLink\b",
        r"\bRogueScore\b",
        r"\bBG3\b",
        r"\bToT\b",
        r"\bAP\b",
        r"NG\+",
    )
)


@dataclass(frozen=True)
class LanguageTarget:
    bg3_folder: str
    google_code: str
    ap_bundle: str
    tutorial_language: str


TARGETS = (
    LanguageTarget("French", "fr", "fr", "Francais"),
    LanguageTarget("German", "de", "de", "Deutsch"),
    LanguageTarget("Spanish", "es", "es", "Espanol"),
    LanguageTarget("Polish", "pl", "pl", "Polski"),
    LanguageTarget("Russian", "ru", "ru", "Russkiy"),
    LanguageTarget("Chinese", "zh-CN", "zh-cn", "JianTi ZhongWen"),
    LanguageTarget("Turkish", "tr", "tr", "Turkce"),
    LanguageTarget("BrazilianPortuguese", "pt-BR", "pt-br", "Portugues do Brasil"),
    LanguageTarget("Italian", "it", "it", "Italiano"),
    LanguageTarget("LatinSpanish", "es-419", "es-419", "Espanol (Latinoamerica)"),
    LanguageTarget("ChineseTraditional", "zh-TW", "zh-tw", "FanTi ZhongWen"),
    LanguageTarget("Ukrainian", "uk", "uk", "Ukrayinska"),
    LanguageTarget("Korean", "ko", "ko", "Hangugeo"),
    LanguageTarget("Japanese", "ja", "ja", "Nihongo"),
)
LAST_REQUEST_AT = 0.0


def load_translation_cache() -> dict[str, dict[str, str]]:
    if not TRANSLATION_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, dict):
            normalized[key] = {str(inner_key): str(inner_value) for inner_key, inner_value in value.items()}
    return normalized


def save_translation_cache(cache: dict[str, dict[str, str]]) -> None:
    TRANSLATION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = TRANSLATION_CACHE_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(TRANSLATION_CACHE_PATH)


TRANSLATION_CACHE = load_translation_cache()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, newline: str) -> None:
    serialized = json.dumps(payload, indent=4, ensure_ascii=False)
    serialized = serialized.replace("\n", newline) + newline
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(serialized)


def collect_string_values(value: Any, sink: list[str]) -> None:
    if isinstance(value, str):
        sink.append(value)
        return
    if isinstance(value, dict):
        for child in value.values():
            collect_string_values(child, sink)
        return
    if isinstance(value, list):
        for child in value:
            collect_string_values(child, sink)


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def reserve_token(replacements: dict[str, str], value: str) -> str:
    token = f"[[[TOTPH_{len(replacements):04d}]]]"
    replacements[token] = value
    return token


def protect_text(text: str) -> tuple[str, dict[str, str]]:
    protected = text
    replacements: dict[str, str] = {}

    def replace_match(match: re.Match[str]) -> str:
        return reserve_token(replacements, match.group(0))

    for pattern in GLOSSARY_PATTERNS:
        protected = pattern.sub(replace_match, protected)
    for pattern in (PRINTF_PATTERN, BRACE_PATTERN, BACKTICK_PATTERN, NEWLINE_PATTERN):
        protected = pattern.sub(replace_match, protected)

    return protected, replacements


def restore_text(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, original in replacements.items():
        restored = restored.replace(token, original)
    return restored


def rate_limit_request() -> None:
    global LAST_REQUEST_AT
    now = time.monotonic()
    remaining_delay = MIN_REQUEST_INTERVAL_SECONDS - (now - LAST_REQUEST_AT)
    if remaining_delay > 0:
        time.sleep(remaining_delay)
    LAST_REQUEST_AT = time.monotonic()


def request_translation_google(text: str, target_code: str) -> str:
    rate_limit_request()

    payload = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": target_code,
            "dt": "t",
            "q": text,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        GOOGLE_TRANSLATE_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in data[0])


def request_translation_mymemory(text: str, target_code: str) -> str:
    rate_limit_request()

    payload = urllib.parse.urlencode(
        {
            "q": text,
            "langpair": f"en|{target_code}",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        MYMEMORY_TRANSLATE_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    return html.unescape(str(data["responseData"]["translatedText"]))


def request_translation(text: str, target_code: str) -> str:
    if TRANSLATION_PROVIDER == "google":
        return request_translation_google(text, target_code)
    if TRANSLATION_PROVIDER == "mymemory":
        return request_translation_mymemory(text, target_code)
    raise ValueError(f"Unsupported translation provider: {TRANSLATION_PROVIDER}")


def request_translation_with_retries(text: str, target_code: str) -> str:
    delays = (0.0,) + REQUEST_RETRY_DELAYS_SECONDS
    last_error: Exception | None = None
    for attempt, delay in enumerate(delays, start=1):
        if delay > 0:
            time.sleep(delay)
        try:
            return request_translation(text, target_code)
        except urllib.error.HTTPError as error:  # pragma: no cover - network failures depend on environment
            last_error = error
            retry_after = error.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                except ValueError:
                    pass
            print(f"    Request attempt {attempt} failed for {target_code}: {error}")
        except Exception as error:  # pragma: no cover - network failures depend on environment
            last_error = error
            print(f"    Request attempt {attempt} failed for {target_code}: {error}")
    raise RuntimeError(f"Could not translate batch for {target_code}") from last_error


def translate_many(texts: list[str], target: LanguageTarget) -> dict[str, str]:
    cache_key = f"{TRANSLATION_PROVIDER}:{target.google_code}"
    cache_bucket = TRANSLATION_CACHE.setdefault(cache_key, {})
    translated_by_source: dict[str, str] = {
        text: cache_bucket[text]
        for text in texts
        if text in cache_bucket
    }
    pending_texts = [text for text in texts if text not in translated_by_source]
    protected_records = [(text, *protect_text(text)) for text in pending_texts]
    batch: list[tuple[str, str, dict[str, str]]] = []
    batch_length = 0
    effective_max_batch_chars = 450 if TRANSLATION_PROVIDER == "mymemory" else MAX_BATCH_CHARS
    effective_max_batch_items = 8 if TRANSLATION_PROVIDER == "mymemory" else MAX_BATCH_ITEMS
    total_pending = len(protected_records)
    completed_pending = 0

    if translated_by_source:
        print(f"    Reused {len(translated_by_source)} cached translations.")

    def flush_batch() -> None:
        nonlocal batch
        nonlocal batch_length
        nonlocal completed_pending
        if not batch:
            return

        payload = "".join(
            f"<t{index:04d}>{record[1]}</t{index:04d}>"
            for index, record in enumerate(batch)
        )
        translated_payload = request_translation_with_retries(payload, target.google_code)
        for index, (source_text, _protected, replacements) in enumerate(batch):
            normalized_index = str(index)
            pattern = re.compile(
                rf"<t0*{normalized_index}>(.*?)</t0*{normalized_index}>",
                re.DOTALL,
            )
            match = pattern.search(translated_payload)
            if match is None:
                raise RuntimeError(
                    f"Missing wrapped translation for index {index} while translating {target.bg3_folder}"
                )
            translated_text = match.group(1)
            restored_text = restore_text(translated_text, replacements)
            translated_by_source[source_text] = restored_text
            cache_bucket[source_text] = restored_text

        completed_pending += len(batch)
        save_translation_cache(TRANSLATION_CACHE)
        print(f"    Cached {completed_pending}/{total_pending} new translations.")

        batch = []
        batch_length = 0

    for record in protected_records:
        protected_text = record[1]
        record_length = len(protected_text)
        record_overhead = 20
        if batch and (
            len(batch) >= effective_max_batch_items
            or batch_length + record_overhead + record_length > effective_max_batch_chars
        ):
            flush_batch()
        batch.append(record)
        batch_length += record_overhead + record_length

    flush_batch()
    return translated_by_source


def translate_tree(value: Any, translated_by_source: dict[str, str]) -> Any:
    if isinstance(value, str):
        return translated_by_source.get(value, value)
    if isinstance(value, dict):
        return {key: translate_tree(child, translated_by_source) for key, child in value.items()}
    if isinstance(value, list):
        return [translate_tree(child, translated_by_source) for child in value]
    return value


def build_tot_xml(tot_entries: dict[str, dict[str, Any]], translated_by_source: dict[str, str]) -> str:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<contentList>"]
    for entry in tot_entries.values():
        lines.append(
            f'    <content contentuid="{entry["Handle"]}" version="{entry["Version"]}">'
            f'{escape(translated_by_source[entry["Text"]])}</content>'
        )
    lines.append("</contentList>")
    return "\n".join(lines) + "\n"


def build_summons_xml(
    summons_entries: list[dict[str, str]],
    translated_by_source: dict[str, str],
) -> str:
    lines = [
        '<?xml version="1.0"?>',
        '<contentList xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
    ]
    for entry in summons_entries:
        lines.append(
            f'    <content contentuid="{entry["contentuid"]}" version="{entry["version"]}">'
            f'{escape(translated_by_source[entry["text"]])}</content>'
        )
    lines.append("</contentList>")
    return "\n".join(lines) + "\n"


def write_text(path: Path, contents: str, *, newline: str) -> None:
    normalized = contents.replace("\r\n", "\n").replace("\n", newline)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(normalized)


def main() -> None:
    tot_entries = read_json(ENGLISH_TOT_JSON)
    ap_bundle = read_json(ENGLISH_AP_JSON)

    summons_root = ET.fromstring(ENGLISH_TOT_SUMMONS_XML.read_text(encoding="utf-8"))
    summons_entries = [
        {
            "contentuid": str(node.attrib["contentuid"]),
            "version": str(node.attrib.get("version", "1")),
            "text": node.text or "",
        }
        for node in summons_root.findall("content")
    ]

    source_strings: list[str] = []
    source_strings.extend(entry["Text"] for entry in tot_entries.values())
    source_strings.extend(entry["text"] for entry in summons_entries)
    collect_string_values(ap_bundle["ui"], source_strings)
    unique_strings = unique_preserving_order(source_strings)

    print(f"Translating {len(unique_strings)} unique strings into {len(TARGETS)} languages.")

    for target in TARGETS:
        print(f"  {target.bg3_folder} ({target.google_code})")
        translated_by_source = translate_many(unique_strings, target)

        translated_tot_entries = {
            key: {
                **value,
                "Text": translated_by_source[value["Text"]],
            }
            for key, value in tot_entries.items()
        }
        translated_ap_bundle = {
            **ap_bundle,
            "ui": translate_tree(ap_bundle["ui"], translated_by_source),
        }
        translated_ap_bundle["canonical"] = dict(ap_bundle["canonical"])
        translated_ap_bundle["canonical"]["tutorial"] = dict(ap_bundle["canonical"]["tutorial"])
        translated_ap_bundle["canonical"]["tutorial"]["setup"] = dict(
            ap_bundle["canonical"]["tutorial"]["setup"]
        )
        translated_ap_bundle["canonical"]["tutorial"]["setup"]["language"] = target.tutorial_language

        bg3_dir = BG3_LOCALIZATION_ROOT / target.bg3_folder
        bg3_dir.mkdir(parents=True, exist_ok=True)
        write_json(bg3_dir / "ToT.json", translated_tot_entries, newline="\r\n")
        write_text(
            bg3_dir / "ToT.xml",
            build_tot_xml(tot_entries, translated_by_source),
            newline="\r\n",
        )
        write_text(
            bg3_dir / "TotSummons.xml",
            build_summons_xml(summons_entries, translated_by_source),
            newline="\r\n",
        )

        write_json(
            AP_LOCALIZATION_ROOT / f"{target.ap_bundle}.json",
            translated_ap_bundle,
            newline="\n",
        )

    print("Localization bundle generation complete.")


if __name__ == "__main__":
    main()
