from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any


MAX_CLEAR_CHECKS = 40
MAX_KILL_CHECKS = 50
MAX_PERFECT_CHECKS = 20
MAX_ROGUESCORE_CHECKS = 30

CLEAR_LOCATION_BASE_ID = 20000
KILL_LOCATION_BASE_ID = 20100
PERFECT_LOCATION_BASE_ID = 20200
ROGUESCORE_LOCATION_BASE_ID = 20300
SHOP_LOCATION_BASE_ID = 20400
PIXIE_BLESSING_UNLOCK_ID = "Moonshield"


def _normalized_copies(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _load_unlock_catalog() -> list[dict[str, Any]]:
    catalog_text = resources.files(__package__).joinpath("trials_unlock_catalog.json").read_text(encoding="utf-8")
    raw_catalog = json.loads(catalog_text)
    normalized_catalog: list[dict[str, Any]] = []
    for entry in raw_catalog:
        normalized_catalog.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "classification": entry["classification"],
                "copies": _normalized_copies(entry.get("copies", 1)),
            }
        )
    return normalized_catalog


UNLOCK_CATALOG = _load_unlock_catalog()
CLASSIFICATION_PRIORITY = {
    "progression": 0,
    "useful": 1,
    "filler": 2,
}

UNLOCK_SLOT_CATALOG_UNSORTED: list[dict[str, Any]] = []
for source_order, entry in enumerate(UNLOCK_CATALOG):
    for copy_index in range(1, entry["copies"] + 1):
        UNLOCK_SLOT_CATALOG_UNSORTED.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "classification": entry["classification"],
                "copies": entry["copies"],
                "copy_index": copy_index,
                "source_order": source_order,
            }
        )

UNLOCK_SLOT_CATALOG = sorted(
    UNLOCK_SLOT_CATALOG_UNSORTED,
    key=lambda entry: (
        CLASSIFICATION_PRIORITY.get(entry["classification"], 99),
        entry["source_order"],
        entry["copy_index"],
    ),
)

UNLOCK_ID_ORDER = [entry["id"] for entry in UNLOCK_SLOT_CATALOG]
UNLOCK_NAME_BY_ID = {entry["id"]: entry["name"] for entry in UNLOCK_CATALOG}
UNLOCK_CLASSIFICATION_BY_ID = {entry["id"]: entry["classification"] for entry in UNLOCK_CATALOG}


def selected_shop_unlock_ids(
    shop_check_count: int,
    *,
    randomize_pixie_blessing: bool = True,
) -> list[str]:
    unlock_ids = UNLOCK_ID_ORDER
    if not randomize_pixie_blessing:
        unlock_ids = [unlock_id for unlock_id in unlock_ids if unlock_id != PIXIE_BLESSING_UNLOCK_ID]
    return unlock_ids[: max(0, int(shop_check_count))]


def clear_location_id(index: int) -> int:
    return CLEAR_LOCATION_BASE_ID + index


def kill_location_id(index: int) -> int:
    return KILL_LOCATION_BASE_ID + index


def perfect_location_id(index: int) -> int:
    return PERFECT_LOCATION_BASE_ID + index


def roguescore_location_id(index: int) -> int:
    return ROGUESCORE_LOCATION_BASE_ID + index


def shop_location_id(index: int) -> int:
    return SHOP_LOCATION_BASE_ID + index


def _counter_location_name(label: str, index: int, total: int | None = None) -> str:
    if total is not None:
        return f"{label} {index}/{total}"
    return f"{label} {index}"


def clear_location_name(index: int, total: int | None = None) -> str:
    return _counter_location_name("Clear Check", index, total)


def kill_location_name(index: int, total: int | None = None) -> str:
    return _counter_location_name("Kill Check", index, total)


def perfect_location_name(index: int, total: int | None = None) -> str:
    return _counter_location_name("Perfect Check", index, total)


def roguescore_location_name(index: int, total: int | None = None) -> str:
    return _counter_location_name("RogueScore Check", index, total)


def shop_slot_display_name(index: int) -> str:
    entry = UNLOCK_SLOT_CATALOG[index - 1]
    if entry["copies"] > 1:
        return f"{entry['name']} #{entry['copy_index']}"
    return entry["name"]


def shop_location_name(index: int, total: int | None = None) -> str:
    return _counter_location_name("Shop Check", index, total)


def build_location_name_to_id() -> dict[str, int]:
    mapping: dict[str, int] = {}

    for index in range(1, MAX_CLEAR_CHECKS + 1):
        mapping[clear_location_name(index)] = clear_location_id(index)
    for index in range(1, MAX_KILL_CHECKS + 1):
        mapping[kill_location_name(index)] = kill_location_id(index)
    for index in range(1, MAX_PERFECT_CHECKS + 1):
        mapping[perfect_location_name(index)] = perfect_location_id(index)
    for index in range(1, MAX_ROGUESCORE_CHECKS + 1):
        mapping[roguescore_location_name(index)] = roguescore_location_id(index)
    for index in range(1, len(UNLOCK_SLOT_CATALOG) + 1):
        mapping[shop_location_name(index)] = shop_location_id(index)

    return mapping


def build_bg3_location_to_ap_locations() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {"TOT-GOAL-001": ["Victory"]}

    for index in range(1, MAX_CLEAR_CHECKS + 1):
        mapping[f"TOT-CLEAR-{index:03d}"] = [clear_location_name(index)]
    for index in range(1, MAX_KILL_CHECKS + 1):
        mapping[f"TOT-KILLS-{index:03d}"] = [kill_location_name(index)]
    for index in range(1, MAX_PERFECT_CHECKS + 1):
        mapping[f"TOT-PERFECT-{index:03d}"] = [perfect_location_name(index)]
    for index in range(1, MAX_ROGUESCORE_CHECKS + 1):
        mapping[f"TOT-ROGUESCORE-{index:03d}"] = [roguescore_location_name(index)]
    for index in range(1, len(UNLOCK_SLOT_CATALOG) + 1):
        mapping[f"TOT-SHOP-{index:03d}"] = [shop_location_name(index)]

    return mapping


def location_id_for_token(
    token: str,
    *,
    clear_count: int,
    kill_count: int,
    perfect_count: int,
    roguescore_count: int,
    shop_count: int,
) -> int | str | None:
    if token == "TOT-GOAL-001":
        return "Victory"

    matchers = (
        (r"^TOT-CLEAR-(\d{3})$", clear_count, clear_location_id),
        (r"^TOT-KILLS-(\d{3})$", kill_count, kill_location_id),
        (r"^TOT-PERFECT-(\d{3})$", perfect_count, perfect_location_id),
        (r"^TOT-ROGUESCORE-(\d{3})$", roguescore_count, roguescore_location_id),
        (r"^TOT-SHOP-(\d{3})$", shop_count, shop_location_id),
    )

    for pattern, maximum_count, id_factory in matchers:
        match = re.match(pattern, token)
        if not match:
            continue
        index = int(match.group(1))
        if 1 <= index <= maximum_count:
            return id_factory(index)
        return None

    return None


LOCATION_NAME_TO_ID = build_location_name_to_id()
BG3_LOCATION_TO_AP_LOCATIONS = build_bg3_location_to_ap_locations()
