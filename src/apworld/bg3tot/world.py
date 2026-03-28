from __future__ import annotations

from collections.abc import Mapping
import random
from typing import Any, ClassVar

from worlds.AutoWorld import World

from . import items, locations, options, regions, rules, settings, web_world
from .trials_data import UNLOCK_ID_ORDER


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


class BG3World(World):
    game = "Baldur's Gate 3 - ToT"
    web = web_world.BG3WebWorld()

    options_dataclass = options.BG3Options
    options: options.BG3Options

    settings: ClassVar[settings.BG3Settings]

    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_to_id = items.ITEM_NAME_TO_ID
    origin_region_name = "Trials of Tav"

    def create_regions(self) -> None:
        regions.create_and_connect_regions(self)
        locations.create_all_locations(self)

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.BG3Item:
        return items.create_item_with_correct_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        selected_shop_unlock_ids = UNLOCK_ID_ORDER[: int(self.options.shop_check_count)]
        seed_basis = getattr(self.multiworld, "seed_name", None) or getattr(self.multiworld, "seed", None) or "BG3Trials"
        selected_shop_costs = _randomized_shop_costs(
            seed_basis,
            self.player,
            selected_shop_unlock_ids,
            int(self.options.shop_price_minimum),
            int(self.options.shop_price_maximum),
        )

        return {
            "death_link": bool(self.options.death_link),
            "death_link_trigger": int(self.options.death_link_trigger),
            "goal": int(self.options.goal),
            "goal_clear_target": int(self.options.goal_clear_target),
            "goal_rogue_score_target": int(self.options.goal_rogue_score_target),
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
            "shop_check_unlock_ids": selected_shop_unlock_ids,
            "shop_check_costs": selected_shop_costs,
            "goal_unlock_id": "APGOAL::QUICKSTART",
            "goal_unlock_template_id": "QUICKSTART",
            "goal_unlock_cost": 2000,
        }
