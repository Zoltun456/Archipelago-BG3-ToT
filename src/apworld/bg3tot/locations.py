from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location

from . import items
from .trials_data import (
    LOCATION_NAME_TO_ID,
    MAX_SHOP_CHECKS,
    MAX_CLEAR_CHECKS,
    MAX_KILL_CHECKS,
    MAX_PERFECT_CHECKS,
    MAX_ROGUESCORE_CHECKS,
    clear_location_id,
    clear_location_name,
    kill_location_id,
    kill_location_name,
    perfect_location_id,
    perfect_location_name,
    roguescore_location_id,
    roguescore_location_name,
    build_shop_layout,
    shop_location_id,
    shop_location_name,
)

if TYPE_CHECKING:
    from .world import BG3World


class BG3Location(Location):
    game = "Baldur's Gate 3 - ToT"


LOCATION_NAME_GROUPS = {
    "Clears": {clear_location_name(index) for index in range(1, MAX_CLEAR_CHECKS + 1)},
    "Kills": {kill_location_name(index) for index in range(1, MAX_KILL_CHECKS + 1)},
    "Perfect Clears": {perfect_location_name(index) for index in range(1, MAX_PERFECT_CHECKS + 1)},
    "RogueScore": {roguescore_location_name(index) for index in range(1, MAX_ROGUESCORE_CHECKS + 1)},
    "Shop": {shop_location_name(index) for index in range(1, MAX_SHOP_CHECKS + 1)},
}


def get_location_names_with_ids(location_names: list[str]) -> dict[str, int | None]:
    return {location_name: LOCATION_NAME_TO_ID[location_name] for location_name in location_names}


def _build_location_group(
    count: int,
    name_factory,
    id_factory,
) -> dict[str, int]:
    return {
        name_factory(index): id_factory(index)
        for index in range(1, count + 1)
    }


def create_all_locations(world: BG3World) -> None:
    trials_region = world.get_region("Trials of Tav")
    location_name_to_id: dict[str, int] = {}

    # This mirrors the token families the Lua bridge emits in BG3:
    # clear, kill, perfect, RogueScore, then shop.
    location_name_to_id.update(
        _build_location_group(int(world.options.clear_check_count), clear_location_name, clear_location_id)
    )
    location_name_to_id.update(
        _build_location_group(int(world.options.kill_check_count), kill_location_name, kill_location_id)
    )
    location_name_to_id.update(
        _build_location_group(int(world.options.perfect_check_count), perfect_location_name, perfect_location_id)
    )
    location_name_to_id.update(
        _build_location_group(int(world.options.roguescore_check_count), roguescore_location_name, roguescore_location_id)
    )
    location_name_to_id.update(
        _build_location_group(
            len(
                build_shop_layout(
                    int(world.options.shop_check_count),
                    randomize_pixie_blessing=not bool(world.options.vanilla_pixie_blessing_in_shop),
                    option_values=world.options,
                )["unlock_ids"]
            ),
            shop_location_name,
            shop_location_id,
        )
    )

    trials_region.add_locations(location_name_to_id, BG3Location)
    trials_region.add_event("Victory", "Victory", location_type=BG3Location, item_type=items.BG3Item)
