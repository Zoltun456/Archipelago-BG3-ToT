from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification
from Options import OptionError

if TYPE_CHECKING:
    from .world import BG3World

from .equipment import EQUIPMENT
from .trials_data import (
    SHOP_FRAGMENT_ITEM_NAME,
    build_shop_layout,
    UNLOCK_CATALOG,
    UNLOCK_CLASSIFICATION_BY_ID,
    UNLOCK_NAME_BY_ID,
)


DUPLICATE_ITEM_FILLERS = [
    #["Potion of Healing", "d47006e9-8a51-453d-b200-9e0d42e9bbab"],
    #["Supply Pack", "a24a2ca2-a213-424c-833d-47c79934c0ce"],
    #["Lockpick", "e32a200c-5b63-414d-ae57-00e7b38f125b"],
]

CUSTOM_FILLERS = [
    ["Currency +25", "ToTFiller:Currency:25"],
    ["Currency +50", "ToTFiller:Currency:50"],
    ["Currency +100", "ToTFiller:Currency:100"],
    #["RogueScore +5", "ToTFiller:RogueScore:5"],
    #["RogueScore +10", "ToTFiller:RogueScore:10"],
    #["RogueScore +25", "ToTFiller:RogueScore:25"],
    ["XP +1000", "ToTFiller:Experience:1000"],
    ["XP +3000", "ToTFiller:Experience:3000"],
]

TRAP_OPTIONS = [
    ["Monster Spawn Trap", "Trap-Monster"],
    ["Bleeding Trap", "Trap-Bleeding"],
    ["Stunned Trap", "Trap-Stun"],
    ["Confusion Trap", "Trap-Confusion"],
    ["Sussur Trap", "Trap-Sussur"],
    ["Clown Trap", "Trap-Clown"],
    ["Overburdened Trap", "Trap-Overburdened"],
    ["Bane Trap", "Trap-Bane"],
    ["Blindness Trap", "Trap-Blindness"],
    ["Slow Trap", "Trap-Slow"],
    ["Poisoned Trap", "Trap-Poisoned"],
    ["Faerie Fire Trap", "Trap-FaerieFire"],
    ["Ensnared Trap", "Trap-Ensnared"],
    ["Frightened Trap", "Trap-Frightened"],
    ["Burning Trap", "Trap-Burning"],
    ["Hold Person Trap", "Trap-HoldPerson"],
    ["Cheesed Trap", "Trap-Cheesed"],
    ["Silence Trap", "Trap-Silence"],
    ["Grease Trap", "Trap-Grease"],
]

# Keep the legacy trap items registered so older seeds can still deserialize them,
# but only the supported subset should be generated going forward.
TRAP_ITEM_NAME_BY_OPTION = {
    "Monster": "Monster Spawn Trap",
    "Bleeding": "Bleeding Trap",
    "Stun": "Stunned Trap",
    "Confusion": "Confusion Trap",
    "Bane": "Bane Trap",
    "Blindness": "Blindness Trap",
    "Slow": "Slow Trap",
    "Poisoned": "Poisoned Trap",
    "FaerieFire": "Faerie Fire Trap",
    "Ensnared": "Ensnared Trap",
    "Frightened": "Frightened Trap",
    "Burning": "Burning Trap",
    "HoldPerson": "Hold Person Trap",
    "Cheesed": "Cheesed Trap",
    "Silence": "Silence Trap",
    "Grease": "Grease Trap",
}

UNLOCK_ITEM_NAMES = {unlock["name"] for unlock in UNLOCK_CATALOG}
PROGRESSION_UNLOCK_ITEM_NAMES = {
    unlock["name"]
    for unlock in UNLOCK_CATALOG
    if unlock["classification"] == "progression"
}
USEFUL_UNLOCK_ITEM_NAMES = {
    unlock["name"]
    for unlock in UNLOCK_CATALOG
    if unlock["classification"] == "useful"
}
FILLER_UNLOCK_ITEM_NAMES = {
    unlock["name"]
    for unlock in UNLOCK_CATALOG
    if unlock["classification"] == "filler"
}
TRAP_ITEM_NAMES = {str(name) for name, _trap_id in TRAP_OPTIONS}


def _build_equipment_fillers() -> list[list[str]]:
    # Equipment still comes from the upstream BG3 world list. I only rename dupes here so the
    # AP item names stay unique when the same BG3 template appears more than once.
    name_counts: dict[str, int] = {}
    fillers: list[list[str]] = []
    for name, item_uuid, _tier in EQUIPMENT:
        count = name_counts.get(name, 0) + 1
        name_counts[name] = count
        display_name = name if count == 1 else f"{name} #{count}"
        fillers.append([display_name, item_uuid])
    return fillers


def _classification_for_unlock(unlock_id: str) -> ItemClassification:
    category = UNLOCK_CLASSIFICATION_BY_ID[unlock_id]
    if category == "progression":
        return ItemClassification.progression
    if category == "filler":
        return ItemClassification.filler
    return ItemClassification.useful


def _extend_item_tuples(
    target: list[list[str | int | ItemClassification]],
    rows: list[list[str]],
    start_code: int,
    classification: ItemClassification,
) -> None:
    for index, (name, bg3_id) in enumerate(rows, start=1):
        target.append([name, bg3_id, start_code + index, classification])


EQUIPMENT_FILLERS = _build_equipment_fillers()
BASE_FILLER_ITEM_NAMES = [item[0] for item in CUSTOM_FILLERS + DUPLICATE_ITEM_FILLERS]
EQUIPMENT_FILLER_ITEM_NAMES = [item[0] for item in EQUIPMENT_FILLERS]
FILLER_ITEM_NAMES = BASE_FILLER_ITEM_NAMES + EQUIPMENT_FILLER_ITEM_NAMES
ITEM_NAME_GROUPS = {
    "Unlocks": UNLOCK_ITEM_NAMES,
    "Progression Unlocks": PROGRESSION_UNLOCK_ITEM_NAMES,
    "Shop Progression": {SHOP_FRAGMENT_ITEM_NAME},
    "Useful Unlocks": USEFUL_UNLOCK_ITEM_NAMES,
    "Filler Unlocks": FILLER_UNLOCK_ITEM_NAMES,
    "Fillers": set(FILLER_ITEM_NAMES),
    "Traps": TRAP_ITEM_NAMES,
}

ITEM_TUPLES: list[list[str | int | ItemClassification]] = []
ITEM_TUPLES.append(
    [
        SHOP_FRAGMENT_ITEM_NAME,
        "ToTUnlock:ShopFragment",
        900,
        ItemClassification.progression,
    ]
)
for index, unlock in enumerate(UNLOCK_CATALOG, start=1):
    ITEM_TUPLES.append(
        [
            unlock["name"],
            f"ToTUnlock:{unlock['id']}",
            1000 + index,
            _classification_for_unlock(unlock["id"]),
        ]
    )

_extend_item_tuples(ITEM_TUPLES, CUSTOM_FILLERS, 5000, ItemClassification.filler)
_extend_item_tuples(ITEM_TUPLES, DUPLICATE_ITEM_FILLERS, 5100, ItemClassification.filler)
_extend_item_tuples(ITEM_TUPLES, EQUIPMENT_FILLERS, 6000, ItemClassification.filler)
_extend_item_tuples(ITEM_TUPLES, TRAP_OPTIONS, 7000, ItemClassification.trap)


ITEM_NAME_TO_ID = {str(item[0]): int(item[2]) for item in ITEM_TUPLES}
ID_TO_ITEM_NAME = {int(item[2]): str(item[0]) for item in ITEM_TUPLES}
AP_ITEM_TO_BG3_ID = {str(item[0]): str(item[1]) for item in ITEM_TUPLES}
DEFAULT_ITEM_CLASSIFICATIONS = {str(item[0]): item[3] for item in ITEM_TUPLES}
IS_DUPEABLE = {item[1]: True for item in DUPLICATE_ITEM_FILLERS + EQUIPMENT_FILLERS}
UNLOCK_ITEM_NAME_BY_ID = {unlock_id: name for unlock_id, name in UNLOCK_NAME_BY_ID.items()}


class BG3Item(Item):
    game = "Baldur's Gate 3 - ToT"


def get_enabled_filler_item_names(world: BG3World) -> list[str]:
    filler_item_names = list(BASE_FILLER_ITEM_NAMES)
    if bool(getattr(world.options, "include_equipment_fillers", True)):
        filler_item_names.extend(EQUIPMENT_FILLER_ITEM_NAMES)
    return filler_item_names


def get_random_filler_item_name(world: BG3World) -> str:
    if world.random.randint(0, 100) < world.options.traps_percentage:
        enabled = list(world.options.enabled_traps)
        if enabled:
            selected_trap = world.random.choice(enabled)
            trap_item_name = TRAP_ITEM_NAME_BY_OPTION.get(selected_trap)
            if trap_item_name:
                return trap_item_name

    return world.random.choice(get_enabled_filler_item_names(world))


def create_item_with_correct_classification(world: BG3World, name: str) -> BG3Item:
    return BG3Item(name, DEFAULT_ITEM_CLASSIFICATIONS[name], ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: BG3World) -> None:
    shop_layout = build_shop_layout(
        int(world.options.shop_check_count),
        randomize_pixie_blessing=not bool(world.options.vanilla_pixie_blessing_in_shop),
        option_values=world.options,
    )
    itempool = [
        world.create_item(UNLOCK_ITEM_NAME_BY_ID[unlock_id])
        for unlock_id in shop_layout["unlock_ids"]
    ]
    itempool.extend(
        world.create_item(SHOP_FRAGMENT_ITEM_NAME)
        for _index in range(int(shop_layout["fragment_count"]))
    )

    number_of_unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    if len(itempool) > number_of_unfilled_locations:
        raise OptionError(
            "This slot generates more local progression items than it has locations available. "
            "Reduce the Progressive Shop fragment count or add more non-shop checks."
        )
    needed_number_of_filler_items = max(0, number_of_unfilled_locations - len(itempool))
    itempool.extend(world.create_filler() for _ in range(needed_number_of_filler_items))

    world.multiworld.itempool += itempool
