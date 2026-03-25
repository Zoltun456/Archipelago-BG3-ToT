from __future__ import annotations

import json
from importlib import resources
from typing import Any


MAX_CLEAR_CHECKS = 40
MAX_KILL_CHECKS = 50
MAX_PERFECT_CHECKS = 20
MAX_ROGUESCORE_CHECKS = 30


def _normalized_copies(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _normalized_base_cost(value: Any) -> int:
    try:
        return max(10, int(value))
    except (TypeError, ValueError):
        return 100


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
                "base_cost": _normalized_base_cost(entry.get("base_cost", 100)),
            }
        )
    return normalized_catalog


UNLOCK_CATALOG = _load_unlock_catalog()
UNLOCK_SLOT_CATALOG: list[dict[str, Any]] = []
for entry in UNLOCK_CATALOG:
    for copy_index in range(1, entry["copies"] + 1):
        UNLOCK_SLOT_CATALOG.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "classification": entry["classification"],
                "copies": entry["copies"],
                "copy_index": copy_index,
                "base_cost": entry["base_cost"],
            }
        )

UNLOCK_ID_ORDER = [entry["id"] for entry in UNLOCK_SLOT_CATALOG]
UNLOCK_NAME_BY_ID = {entry["id"]: entry["name"] for entry in UNLOCK_CATALOG}
UNLOCK_CLASSIFICATION_BY_ID = {entry["id"]: entry["classification"] for entry in UNLOCK_CATALOG}
UNLOCK_BASE_COST_BY_ID = {entry["id"]: entry["base_cost"] for entry in UNLOCK_CATALOG}


def clear_location_name(index: int) -> str:
    return f"Trials: Clear Check {index}"


def kill_location_name(index: int) -> str:
    return f"Trials: Kill Check {index}"


def perfect_location_name(index: int) -> str:
    return f"Trials: Perfect Check {index}"


def roguescore_location_name(index: int) -> str:
    return f"Trials: RogueScore Check {index}"


def shop_slot_display_name(index: int) -> str:
    entry = UNLOCK_SLOT_CATALOG[index - 1]
    if entry["copies"] > 1:
        return f"{entry['name']} #{entry['copy_index']}"
    return entry["name"]


def shop_location_name(index: int) -> str:
    return f"Trials: Shop Check {index} ({shop_slot_display_name(index)})"


def build_location_name_to_id() -> dict[str, int]:
    mapping: dict[str, int] = {}

    for index in range(1, MAX_CLEAR_CHECKS + 1):
        mapping[clear_location_name(index)] = 20000 + index
    for index in range(1, MAX_KILL_CHECKS + 1):
        mapping[kill_location_name(index)] = 20100 + index
    for index in range(1, MAX_PERFECT_CHECKS + 1):
        mapping[perfect_location_name(index)] = 20200 + index
    for index in range(1, MAX_ROGUESCORE_CHECKS + 1):
        mapping[roguescore_location_name(index)] = 20300 + index
    for index in range(1, len(UNLOCK_SLOT_CATALOG) + 1):
        mapping[shop_location_name(index)] = 20400 + index

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


LOCATION_NAME_TO_ID = build_location_name_to_id()
BG3_LOCATION_TO_AP_LOCATIONS = build_bg3_location_to_ap_locations()
