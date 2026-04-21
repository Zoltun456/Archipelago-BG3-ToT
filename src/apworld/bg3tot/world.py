from __future__ import annotations

from collections.abc import Mapping
import math
import random
from typing import Any, ClassVar

from BaseClasses import ItemClassification
from Options import OptionError
from worlds.AutoWorld import World

from . import items, locations, options, regions, rules, web_world
from .i18n import canonical_text
from .settings import BG3Settings
from .trials_data import (
    GAME_NAME,
    REGION_NAME,
    SHOP_FRAGMENT_ITEM_NAME,
    UNLOCK_CLASSIFICATION_BY_ID,
    build_shop_layout,
    progressive_shop_enabled,
    progressive_shop_section_name,
    shop_location_name,
)


SHOP_PRICE_STEP = 10


def _thresholds(count: int, interval: int) -> list[int]:
    # This is the AP-side mirror of the Lua token thresholds. Keeping it tiny here makes it
    # easier to see that the client and the BG3 runtime are building the same check ladder.
    return [index * interval for index in range(1, count + 1)]


def _floor_to_price_step(value: int) -> int:
    return max(SHOP_PRICE_STEP, (int(value) // SHOP_PRICE_STEP) * SHOP_PRICE_STEP)


def _ceil_to_price_step(value: int) -> int:
    normalized = int(value)
    return max(SHOP_PRICE_STEP, ((normalized + SHOP_PRICE_STEP - 1) // SHOP_PRICE_STEP) * SHOP_PRICE_STEP)


def _randomized_shop_costs(
    seed_basis: Any,
    player: int,
    shop_unlock_ids: list[str],
    price_minimum: int,
    price_maximum: int,
) -> list[int]:
    # Same seed + same player should always give the same shop prices so the client, the spoiler,
    # and the in-game unlock list all stay in agreement.
    price_rng = random.Random(f"BG3TrialsShopPrices:{seed_basis}:{player}")
    minimum_price = _floor_to_price_step(min(price_minimum, price_maximum))
    maximum_price = _ceil_to_price_step(max(price_minimum, price_maximum))
    step_count = ((maximum_price - minimum_price) // SHOP_PRICE_STEP) + 1
    costs: list[int] = []
    for _unlock_id in shop_unlock_ids:
        rolled_cost = minimum_price + (SHOP_PRICE_STEP * price_rng.randrange(step_count))
        costs.append(rolled_cost)
    return costs


def _zero_trap_shop_costs(world: "BG3World", costs: list[int]) -> list[int]:
    adjusted_costs = list(costs)
    for index in range(1, len(adjusted_costs) + 1):
        location = world.multiworld.get_location(shop_location_name(index), world.player)
        if location.item and location.item.classification & ItemClassification.trap:
            adjusted_costs[index - 1] = 0
    return adjusted_costs


def _suggested_early_shop_fragments(fragment_count: int) -> int:
    if fragment_count <= 0:
        return 0
    return min(fragment_count, max(1, math.ceil(fragment_count * 0.25)))


def _guaranteed_local_early_shop_fragments(fragment_count: int) -> int:
    if fragment_count <= 0:
        return 0
    return 1


class BG3World(World):
    game = GAME_NAME
    web = web_world.BG3WebWorld()

    options_dataclass = options.BG3Options
    options: options.BG3Options

    settings: ClassVar[BG3Settings]

    location_name_to_id = locations.LOCATION_NAME_TO_ID
    location_name_groups = locations.LOCATION_NAME_GROUPS
    item_name_to_id = items.ITEM_NAME_TO_ID
    item_name_groups = items.ITEM_NAME_GROUPS
    origin_region_name = REGION_NAME

    def create_regions(self) -> None:
        regions.create_and_connect_regions(self)
        locations.create_all_locations(self)

    def generate_early(self) -> None:
        shop_layout = build_shop_layout(
            int(self.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.options.vanilla_pixie_blessing_in_shop),
            option_values=self.options,
        )
        fragment_count = int(shop_layout["fragment_count"])
        if fragment_count <= 0:
            return

        non_shop_location_count = (
            int(self.options.clear_check_count)
            + int(self.options.kill_check_count)
            + int(self.options.perfect_check_count)
            + int(self.options.roguescore_check_count)
        )
        if fragment_count > non_shop_location_count:
            raise OptionError(
                canonical_text(
                    "errors.progressive_shop_overflow",
                    fragment_count=fragment_count,
                    shop_fragment_item_name=SHOP_FRAGMENT_ITEM_NAME,
                    non_shop_location_count=non_shop_location_count,
                )
            )

        local_early_items = getattr(self.multiworld, "local_early_items", None)
        guaranteed_local_count = _guaranteed_local_early_shop_fragments(fragment_count)
        if local_early_items is not None and guaranteed_local_count > 0:
            try:
                player_local_early_items = local_early_items[self.player]
                current_local_count = int(player_local_early_items.get(SHOP_FRAGMENT_ITEM_NAME, 0) or 0)
                player_local_early_items[SHOP_FRAGMENT_ITEM_NAME] = max(current_local_count, guaranteed_local_count)
            except Exception:
                pass

        early_items = getattr(self.multiworld, "early_items", None)
        suggested_count = _suggested_early_shop_fragments(fragment_count)
        additional_global_count = max(0, suggested_count - guaranteed_local_count)
        if early_items is not None and additional_global_count > 0:
            try:
                player_early_items = early_items[self.player]
                current_count = int(player_early_items.get(SHOP_FRAGMENT_ITEM_NAME, 0) or 0)
                player_early_items[SHOP_FRAGMENT_ITEM_NAME] = max(current_count, additional_global_count)
            except Exception:
                pass

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.BG3Item:
        return items.create_item_with_correct_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        shop_layout = build_shop_layout(
            int(self.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.options.vanilla_pixie_blessing_in_shop),
            option_values=self.options,
        )
        chosen_shop_unlock_ids = list(shop_layout["unlock_ids"])
        seed_basis = getattr(self.multiworld, "seed_name", None) or getattr(self.multiworld, "seed", None) or "BG3Trials"
        selected_shop_costs = _randomized_shop_costs(
            seed_basis,
            self.player,
            chosen_shop_unlock_ids,
            int(self.options.shop_price_minimum),
            int(self.options.shop_price_maximum),
        )
        selected_shop_costs = _zero_trap_shop_costs(self, selected_shop_costs)

        return {
            "death_link": bool(self.options.death_link),
            "death_link_trigger": int(self.options.death_link_trigger),
            "death_link_punishment": int(self.options.death_link_punishment),
            "goal": int(self.options.goal),
            "goal_clear_target": int(self.options.goal_clear_target),
            "goal_rogue_score_target": int(self.options.goal_rogue_score_target),
            "goal_ng_plus_fragment_gate_percent": int(shop_layout["goal_ng_plus_fragment_gate_percent"]),
            "effective_goal_ng_plus_fragment_gate_percent": int(
                shop_layout["effective_goal_ng_plus_fragment_gate_percent"]
            ),
            "effective_goal_ng_plus_fragment_gate_fragments": int(
                shop_layout["effective_goal_ng_plus_fragment_gate_fragments"]
            ),
            "clear_thresholds": _thresholds(
                int(self.options.clear_check_count),
                int(self.options.clear_check_interval),
            ),
            "kill_thresholds": _thresholds(
                int(self.options.kill_check_count),
                int(self.options.kill_check_interval),
            ),
            "perfect_thresholds": _thresholds(
                int(self.options.perfect_check_count),
                int(self.options.perfect_check_interval),
            ),
            "roguescore_thresholds": _thresholds(
                int(self.options.roguescore_check_count),
                int(self.options.roguescore_check_interval),
            ),
            "progressive_shop": progressive_shop_enabled(self.options),
            "progressive_shop_unlock_rate": int(shop_layout["progressive_shop_unlock_rate"]),
            "shop_fragment_count": int(shop_layout["fragment_count"]),
            "shop_check_unlock_ids": chosen_shop_unlock_ids,
            "shop_check_costs": selected_shop_costs,
            "shop_section_indices": list(shop_layout["section_indices"]),
            "shop_section_names": [
                progressive_shop_section_name(int(section_index), int(shop_layout["fragment_count"]))
                for section_index in shop_layout["section_indices"]
            ],
            "vanilla_pixie_blessing_in_shop": bool(self.options.vanilla_pixie_blessing_in_shop),
            "permanent_buff_target": int(self.options.permanent_buff_target),
            "unlock_classifications_by_id": dict(UNLOCK_CLASSIFICATION_BY_ID),
            "goal_unlock_id": "APGOAL::QUICKSTART",
            "goal_unlock_template_id": "QUICKSTART",
            "goal_unlock_cost": int(self.options.goal_ng_plus_price),
        }
