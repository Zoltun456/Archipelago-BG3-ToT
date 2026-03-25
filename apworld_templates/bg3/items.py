from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

if TYPE_CHECKING:
    from .world import BG3World

from .equipment import EQUIPMENT
from .trials_data import UNLOCK_CATALOG, UNLOCK_CLASSIFICATION_BY_ID, UNLOCK_ID_ORDER, UNLOCK_NAME_BY_ID


DUPLICATE_ITEM_FILLERS = [
    ["Potion of Healing", "d47006e9-8a51-453d-b200-9e0d42e9bbab"],
    ["Supply Pack", "a24a2ca2-a213-424c-833d-47c79934c0ce"],
    ["Lockpick", "e32a200c-5b63-414d-ae57-00e7b38f125b"],
]

CUSTOM_FILLERS = [
    ["Trials Currency +25", "ToTFiller:Currency:25"],
    ["Trials Currency +50", "ToTFiller:Currency:50"],
    ["Trials Currency +100", "ToTFiller:Currency:100"],
    ["Trials RogueScore +5", "ToTFiller:RogueScore:5"],
    ["Trials RogueScore +10", "ToTFiller:RogueScore:10"],
    ["Trials RogueScore +25", "ToTFiller:RogueScore:25"],
    ["Trials XP +1000", "ToTFiller:Experience:1000"],
    ["Trials XP +3000", "ToTFiller:Experience:3000"],
]

TRAP_OPTIONS = [
    ["Monster Spawn Trap", "Trap-Monster"],
    ["Bleeding Trap", "Trap-Bleeding"],
    ["Stunned Trap", "Trap-Stun"],
    ["Confusion Trap", "Trap-Confusion"],
    ["Sussur Trap", "Trap-Sussur"],
    ["Clown Trap", "Trap-Clown"],
    ["Overburdened Trap", "Trap-Overburdened"],
]


def _build_equipment_fillers() -> list[list[str]]:
    name_counts: dict[str, int] = {}
    fillers: list[list[str]] = []
    for name, item_uuid, _tier in EQUIPMENT:
        count = name_counts.get(name, 0) + 1
        name_counts[name] = count
        display_name = f"Trials Drop: {name}"
        if count > 1:
            display_name = f"{display_name} #{count}"
        fillers.append([display_name, item_uuid])
    return fillers


EQUIPMENT_FILLERS = _build_equipment_fillers()


def _classification_for_unlock(unlock_id: str) -> ItemClassification:
    category = UNLOCK_CLASSIFICATION_BY_ID[unlock_id]
    if category == "progression":
        return ItemClassification.progression
    if category == "filler":
        return ItemClassification.filler
    return ItemClassification.useful


ITEM_TUPLES = []

for index, unlock in enumerate(UNLOCK_CATALOG, start=1):
    ITEM_TUPLES.append(
        [
            f"Trials Reward: {unlock['name']}",
            f"ToTUnlock:{unlock['id']}",
            1000 + index,
            _classification_for_unlock(unlock["id"]),
        ]
    )

for index, filler in enumerate(CUSTOM_FILLERS, start=1):
    ITEM_TUPLES.append([filler[0], filler[1], 5000 + index, ItemClassification.filler])

for index, filler in enumerate(DUPLICATE_ITEM_FILLERS, start=1):
    ITEM_TUPLES.append([filler[0], filler[1], 5100 + index, ItemClassification.filler])

for index, filler in enumerate(EQUIPMENT_FILLERS, start=1):
    ITEM_TUPLES.append([filler[0], filler[1], 6000 + index, ItemClassification.filler])

for index, trap in enumerate(TRAP_OPTIONS, start=1):
    ITEM_TUPLES.append([trap[0], trap[1], 7000 + index, ItemClassification.trap])


ITEM_NAME_TO_ID = {item[0]: item[2] for item in ITEM_TUPLES}
ID_TO_ITEM_NAME = {item[2]: item[0] for item in ITEM_TUPLES}
AP_ITEM_TO_BG3_ID = {item[0]: item[1] for item in ITEM_TUPLES}
DEFAULT_ITEM_CLASSIFICATIONS = {item[0]: item[3] for item in ITEM_TUPLES}
IS_DUPEABLE = {item[1]: True for item in DUPLICATE_ITEM_FILLERS + EQUIPMENT_FILLERS}
UNLOCK_ITEM_NAME_BY_ID = {unlock_id: f"Trials Reward: {name}" for unlock_id, name in UNLOCK_NAME_BY_ID.items()}


class BG3Item(Item):
    game = "Baldur's Gate 3 - ToT"


def get_random_filler_item_name(world: BG3World) -> str:
    if world.random.randint(0, 100) < world.options.traps_percentage:
        enabled = list(world.options.enabled_traps)
        if enabled:
            trap_name = world.random.choice(enabled)
            if trap_name == "Monster":
                return TRAP_OPTIONS[0][0]
            if trap_name == "Bleeding":
                return TRAP_OPTIONS[1][0]
            if trap_name == "Stun":
                return TRAP_OPTIONS[2][0]
            if trap_name == "Confusion":
                return TRAP_OPTIONS[3][0]
            if trap_name == "Sussur":
                return TRAP_OPTIONS[4][0]
            if trap_name == "Clown":
                return TRAP_OPTIONS[5][0]
            if trap_name == "Overburdened":
                return TRAP_OPTIONS[6][0]

    filler_names = [item[0] for item in CUSTOM_FILLERS + DUPLICATE_ITEM_FILLERS + EQUIPMENT_FILLERS]
    return world.random.choice(filler_names)


def create_item_with_correct_classification(world: BG3World, name: str) -> BG3Item:
    return BG3Item(name, DEFAULT_ITEM_CLASSIFICATIONS[name], ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: BG3World) -> None:
    itempool: list[Item] = []

    selected_unlock_ids = UNLOCK_ID_ORDER[: int(world.options.shop_check_count)]
    for unlock_id in selected_unlock_ids:
        itempool.append(world.create_item(UNLOCK_ITEM_NAME_BY_ID[unlock_id]))

    number_of_items = len(itempool)
    number_of_unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    needed_number_of_filler_items = max(0, number_of_unfilled_locations - number_of_items)
    itempool += [world.create_filler() for _ in range(needed_number_of_filler_items)]

    world.multiworld.itempool += itempool
