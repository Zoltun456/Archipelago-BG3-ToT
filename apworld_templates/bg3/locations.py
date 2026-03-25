from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location

from . import items
from .trials_data import (
    BG3_LOCATION_TO_AP_LOCATIONS,
    LOCATION_NAME_TO_ID,
    clear_location_name,
    kill_location_name,
    perfect_location_name,
    roguescore_location_name,
    shop_location_name,
)

if TYPE_CHECKING:
    from .world import BG3World


class BG3Location(Location):
    game = "Baldur's Gate 3 - ToT"


def get_location_names_with_ids(location_names: list[str]) -> dict[str, int | None]:
    return {location_name: LOCATION_NAME_TO_ID[location_name] for location_name in location_names}


def create_all_locations(world: BG3World) -> None:
    trials = world.get_region("Trials of Tav")
    clear_count = int(world.options.clear_check_count)
    kill_count = int(world.options.kill_check_count)
    perfect_count = int(world.options.perfect_check_count)
    roguescore_count = int(world.options.roguescore_check_count)
    shop_count = int(world.options.shop_check_count)

    location_names: list[str] = []
    location_names.extend(
        clear_location_name(index) for index in range(1, clear_count + 1)
    )
    location_names.extend(
        kill_location_name(index) for index in range(1, kill_count + 1)
    )
    location_names.extend(
        perfect_location_name(index) for index in range(1, perfect_count + 1)
    )
    location_names.extend(
        roguescore_location_name(index) for index in range(1, roguescore_count + 1)
    )
    location_names.extend(
        shop_location_name(index) for index in range(1, shop_count + 1)
    )

    trials.add_locations(get_location_names_with_ids(location_names), BG3Location)
    trials.add_event("Victory", "Victory", location_type=BG3Location, item_type=items.BG3Item)
