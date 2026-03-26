from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location

from . import items
from .trials_data import (
    LOCATION_NAME_TO_ID,
    clear_location_name,
    clear_location_id,
    kill_location_name,
    kill_location_id,
    perfect_location_name,
    perfect_location_id,
    roguescore_location_name,
    roguescore_location_id,
    shop_location_name,
    shop_location_id,
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

    location_name_to_id: dict[str, int] = {}
    location_name_to_id.update(
        {clear_location_name(index, clear_count): clear_location_id(index) for index in range(1, clear_count + 1)}
    )
    location_name_to_id.update(
        {kill_location_name(index, kill_count): kill_location_id(index) for index in range(1, kill_count + 1)}
    )
    location_name_to_id.update(
        {
            perfect_location_name(index, perfect_count): perfect_location_id(index)
            for index in range(1, perfect_count + 1)
        }
    )
    location_name_to_id.update(
        {
            roguescore_location_name(index, roguescore_count): roguescore_location_id(index)
            for index in range(1, roguescore_count + 1)
        }
    )
    location_name_to_id.update(
        {shop_location_name(index, shop_count): shop_location_id(index) for index in range(1, shop_count + 1)}
    )

    trials.add_locations(location_name_to_id, BG3Location)
    trials.add_event("Victory", "Victory", location_type=BG3Location, item_type=items.BG3Item)
