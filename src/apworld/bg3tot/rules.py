from __future__ import annotations

from typing import TYPE_CHECKING

from .trials_data import SHOP_FRAGMENT_ITEM_NAME, VICTORY_NAME, build_shop_layout, shop_location_name

if TYPE_CHECKING:
    from .world import BG3World


def set_all_rules(world: BG3World) -> None:
    world.multiworld.completion_condition[world.player] = lambda state: state.has(VICTORY_NAME, world.player)
    shop_layout = build_shop_layout(
        int(world.options.shop_check_count),
        randomize_pixie_blessing=not bool(world.options.vanilla_pixie_blessing_in_shop),
        option_values=world.options,
    )
    if int(shop_layout["fragment_count"]) <= 0:
        return

    for index, section_index in enumerate(shop_layout["section_indices"], start=1):
        if int(section_index) <= 0:
            continue
        location = world.multiworld.get_location(shop_location_name(index), world.player)
        location.access_rule = (
            lambda state,
            required_fragments=int(section_index),
            player=world.player: state.has(SHOP_FRAGMENT_ITEM_NAME, player, required_fragments)
        )
