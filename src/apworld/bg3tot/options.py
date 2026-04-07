from __future__ import annotations

from dataclasses import make_dataclass

from Options import Choice, DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .trials_data import (
    MAX_CLEAR_CHECKS,
    MAX_CONFIGURABLE_UNLOCK_COPIES,
    MAX_KILL_CHECKS,
    MAX_PERFECT_CHECKS,
    MAX_ROGUESCORE_CHECKS,
    MAX_SHOP_CHECKS,
    UNLOCK_CATALOG,
    unlock_copies_option_name,
)


DEFAULT_ENABLED_TRAPS = {
    "Bleeding",
    "Stun",
    "Confusion",
    "Bane",
    "Blindness",
    "Slow",
    "Poisoned",
    "FaerieFire",
    "Ensnared",
    "Frightened",
    "Burning",
    "HoldPerson",
    "Cheesed",
    "Silence",
    "Grease",
}


def _pascal_case_identifier(value: str) -> str:
    return "".join(part.capitalize() for part in str(value).split("_"))


def _build_unlock_pool_options() -> tuple[dict[str, type[Range]], list[type[Range]], dict[str, object]]:
    option_types: dict[str, type[Range]] = {}
    option_group: list[type[Range]] = []
    preset_defaults: dict[str, object] = {}

    for unlock in UNLOCK_CATALOG:
        unlock_id = str(unlock["id"])
        unlock_name = str(unlock["name"])
        copies = int(unlock["copies"])

        if copies <= 1:
            continue

        option_name = unlock_copies_option_name(unlock_id)
        option_class = type(
            _pascal_case_identifier(option_name),
            (Range,),
            {
                "__module__": __name__,
                "__doc__": (
                    f"How many copies of {unlock_name} are included in the randomized AP unlock pool.\n\n"
                    "Set this to 0 to remove that unlock from the multiworld."
                ),
                "display_name": unlock_name,
                "range_start": 0,
                "range_end": MAX_CONFIGURABLE_UNLOCK_COPIES,
                "default": copies,
            },
        )
        preset_defaults[option_name] = copies

        globals()[option_class.__name__] = option_class
        option_types[option_name] = option_class
        option_group.append(option_class)

    return option_types, option_group, preset_defaults


UNLOCK_POOL_OPTIONS, UNLOCK_POOL_OPTION_GROUP, UNLOCK_POOL_PRESET_DEFAULTS = _build_unlock_pool_options()


class IncludeEquipmentFillers(Toggle):
    """
    Whether one-off equipment filler items from the upstream BG3 equipment pool stay in the AP filler pool.

    Disable this to remove those equipment filler items from the multiworld entirely.
    """

    display_name = "Include Equipment Fillers"
    default = 1


class Goal(Choice):
    """
    Determines how this BG3 Trials slot wins.

    Buy NG+: Purchase the local Quick Start / NG+ unlock from the tav shop.
    Clear Stages: Complete the configured number of Trials clears.
    Reach RogueScore: Reach the configured RogueScore total.
    """

    display_name = "Goal"

    option_buy_ng_plus = 0
    option_clear_stages = 1
    option_reach_rogue_score = 2

    default = option_buy_ng_plus


class GoalClearTarget(Range):
    """
    How many successful Trials clears are required when the goal is Clear Stages.
    """

    display_name = "Goal Clear Target"
    range_start = 1
    range_end = 100
    default = 20


class GoalRogueScoreTarget(Range):
    """
    How much RogueScore is required when the goal is Reach RogueScore.
    """

    display_name = "Goal RogueScore Target"
    range_start = 25
    range_end = 1000
    default = 300


class ClearCheckCount(Range):
    """
    How many Archipelago checks can be earned from successful scenario clears.
    """

    display_name = "Clear Check Count"
    range_start = 0
    range_end = MAX_CLEAR_CHECKS
    default = 20


class ClearCheckInterval(Range):
    """
    Awards one clear-based check every N successful scenario clears until the count limit is reached.
    """

    display_name = "Clear Check Interval"
    range_start = 1
    range_end = 10
    default = 1


class KillCheckCount(Range):
    """
    How many Archipelago checks can be earned from total enemy kills in Trials.
    """

    display_name = "Kill Check Count"
    range_start = 0
    range_end = MAX_KILL_CHECKS
    default = 20


class KillCheckInterval(Range):
    """
    Awards one kill-based check every N total kills until the count limit is reached.
    """

    display_name = "Kill Check Interval"
    range_start = 1
    range_end = 50
    default = 5


class PerfectCheckCount(Range):
    """
    How many Archipelago checks can be earned from perfect clears.
    """

    display_name = "Perfect Check Count"
    range_start = 0
    range_end = MAX_PERFECT_CHECKS
    default = 5


class PerfectCheckInterval(Range):
    """
    Awards one perfect-clear check every N perfect clears until the count limit is reached.
    """

    display_name = "Perfect Check Interval"
    range_start = 1
    range_end = 5
    default = 1


class RogueScoreCheckCount(Range):
    """
    How many Archipelago checks can be earned from RogueScore milestones.
    """

    display_name = "RogueScore Check Count"
    range_start = 0
    range_end = MAX_ROGUESCORE_CHECKS
    default = 10


class RogueScoreCheckInterval(Range):
    """
    Awards one RogueScore-based check every N RogueScore until the count limit is reached.
    """

    display_name = "RogueScore Check Interval"
    range_start = 5
    range_end = 100
    default = 25


class ShopCheckCount(Range):
    """
    Targets at least N randomized AP shop checks from ``trials_unlock_catalog.json``.

    Buying one of these entries sends a location check instead of granting the reward immediately.
    The original reward becomes an AP item that must be received from the multiworld.

    The world will automatically expand above this value when needed so every configured
    non-filler unlock copy still appears somewhere in the randomized item pool.
    """

    display_name = "Shop Check Count"
    range_start = 0
    range_end = MAX_SHOP_CHECKS
    default = min(50, MAX_SHOP_CHECKS)


class ShopPriceMinimum(Range):
    """
    Minimum seeded random price for AP shop entries.

    Prices are rounded to multiples of 10, and NG+ keeps its vanilla local cost.
    """

    display_name = "Shop Price Minimum"
    range_start = 10
    range_end = 1000
    default = 30


class ShopPriceMaximum(Range):
    """
    Maximum seeded random price for AP shop entries.

    Prices are rounded to multiples of 10, and NG+ keeps its vanilla local cost.
    """

    display_name = "Shop Price Maximum"
    range_start = 10
    range_end = 1000
    default = 250


class PermanentBuffTarget(Choice):
    """
    Chooses who receives character-bound useful AP unlock rewards.

    User Character: Gives the reward to the receiving player's chosen character.
    Random Party Member: Gives the reward to one random active party member.
    All Party Members: Gives the reward to every active party member.

    Progression rewards ignore this setting and still keep their whole-party or global behavior.
    """

    display_name = "Permanent Buff Target"

    option_user_character = 0
    option_random_party_member = 1
    option_all_party_members = 2

    default = option_random_party_member


class VanillaPixieBlessingInShop(Toggle):
    """
    Restores Pixie Blessing as a normal local shop unlock instead of randomizing it into the AP pool.

    When enabled, Moonshield is removed from the randomized shop check pool and the vanilla 30-cost shop entry stays local.
    """

    display_name = "Vanilla Pixie Blessing In Shop"


class DeathLinkTrigger(Choice):
    """
    Chooses what local Trials death condition sends a DeathLink.

    Full Party Wipe: Sends when every active party member is dead or downed.
    Any Party Kill: Sends when any active party member fully dies.
    Any Party Downed: Sends when any active party member is downed.
    """

    display_name = "DeathLink Trigger"

    option_full_party_wipe = 0
    option_any_party_kill = 1
    option_any_party_downed = 2

    default = option_full_party_wipe


class TrapsPercentage(Range):
    """
    Percent chance that filler slots become traps instead of helpful filler rewards.
    """

    display_name = "Trap Chance"
    range_start = 0
    range_end = 100
    default = 20


class EnabledTraps(OptionSet):
    """
    Which trap types are allowed in the filler pool.

    Monster traps are still the least proven option and may need extra testing in Trials.
    """

    valid_keys = [
        "Bleeding",
        "Stun",
        "Confusion",
        "Bane",
        "Blindness",
        "Slow",
        "Poisoned",
        "FaerieFire",
        "Ensnared",
        "Frightened",
        "Burning",
        "HoldPerson",
        "Cheesed",
        "Silence",
        "Grease",
        "Monster",
    ]
    display_name = "Enabled Trap List"
    default = DEFAULT_ENABLED_TRAPS


bg3_option_groups = [
    OptionGroup("Game Options", [
        DeathLink,
        DeathLinkTrigger,
    ]),
    OptionGroup("Goals", [
        Goal,
        GoalClearTarget,
        GoalRogueScoreTarget,
    ]),
    OptionGroup("Check Thresholds", [
        ClearCheckCount,
        ClearCheckInterval,
        KillCheckCount,
        KillCheckInterval,
        PerfectCheckCount,
        PerfectCheckInterval,
        RogueScoreCheckCount,
        RogueScoreCheckInterval,
    ]),
    OptionGroup("Shop", [
        ShopCheckCount,
        ShopPriceMinimum,
        ShopPriceMaximum,
        VanillaPixieBlessingInShop,
        PermanentBuffTarget,
    ]),
    OptionGroup("Unlock Pool", [
        *UNLOCK_POOL_OPTION_GROUP,
        IncludeEquipmentFillers,
    ], True),
    OptionGroup("Client & Traps", [
        TrapsPercentage,
        EnabledTraps,
    ]),
]


def _preset_with_unlock_defaults(values: dict[str, object]) -> dict[str, object]:
    return {
        **UNLOCK_POOL_PRESET_DEFAULTS,
        "include_equipment_fillers": True,
        **values,
    }


BG3_OPTION_PRESETS = {
    "Release Defaults": _preset_with_unlock_defaults({
        "death_link": False,
        "death_link_trigger": DeathLinkTrigger.option_full_party_wipe,
        "goal": Goal.option_clear_stages,
        "goal_clear_target": 20,
        "goal_rogue_score_target": 300,
        "clear_check_count": 10,
        "clear_check_interval": 1,
        "kill_check_count": 10,
        "kill_check_interval": 10,
        "perfect_check_count": 5,
        "perfect_check_interval": 1,
        "roguescore_check_count": 10,
        "roguescore_check_interval": 25,
        "shop_check_count": 50,
        "shop_price_minimum": 50,
        "shop_price_maximum": 300,
        "vanilla_pixie_blessing_in_shop": False,
        "permanent_buff_target": PermanentBuffTarget.option_random_party_member,
        "traps_percentage": 15,
        "enabled_traps": sorted(DEFAULT_ENABLED_TRAPS),
    }),
    "Quick Trial": _preset_with_unlock_defaults({
        "death_link": False,
        "death_link_trigger": DeathLinkTrigger.option_full_party_wipe,
        "goal": Goal.option_clear_stages,
        "goal_clear_target": 10,
        "goal_rogue_score_target": 150,
        "clear_check_count": 6,
        "clear_check_interval": 1,
        "kill_check_count": 6,
        "kill_check_interval": 12,
        "perfect_check_count": 3,
        "perfect_check_interval": 1,
        "roguescore_check_count": 4,
        "roguescore_check_interval": 50,
        "shop_check_count": 25,
        "shop_price_minimum": 30,
        "shop_price_maximum": 150,
        "vanilla_pixie_blessing_in_shop": False,
        "permanent_buff_target": PermanentBuffTarget.option_random_party_member,
        "traps_percentage": 10,
        "enabled_traps": sorted(DEFAULT_ENABLED_TRAPS),
    }),
}


BG3_OPTION_FIELDS: dict[str, type] = {
    "death_link": DeathLink,
    "death_link_trigger": DeathLinkTrigger,
    "goal": Goal,
    "goal_clear_target": GoalClearTarget,
    "goal_rogue_score_target": GoalRogueScoreTarget,
    "clear_check_count": ClearCheckCount,
    "clear_check_interval": ClearCheckInterval,
    "kill_check_count": KillCheckCount,
    "kill_check_interval": KillCheckInterval,
    "perfect_check_count": PerfectCheckCount,
    "perfect_check_interval": PerfectCheckInterval,
    "roguescore_check_count": RogueScoreCheckCount,
    "roguescore_check_interval": RogueScoreCheckInterval,
    "shop_check_count": ShopCheckCount,
    "shop_price_minimum": ShopPriceMinimum,
    "shop_price_maximum": ShopPriceMaximum,
    "vanilla_pixie_blessing_in_shop": VanillaPixieBlessingInShop,
    "permanent_buff_target": PermanentBuffTarget,
    **UNLOCK_POOL_OPTIONS,
    "include_equipment_fillers": IncludeEquipmentFillers,
    "traps_percentage": TrapsPercentage,
    "enabled_traps": EnabledTraps,
}


BG3Options = make_dataclass(
    "BG3Options",
    [(name, option) for name, option in BG3_OPTION_FIELDS.items()],
    bases=(PerGameCommonOptions,),
    namespace={"__module__": __name__},
)
