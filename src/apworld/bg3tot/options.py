from __future__ import annotations

from dataclasses import make_dataclass

from Options import Choice, DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .trials_data import (
    DEFAULT_PROGRESSIVE_SHOP_UNLOCK_RATE,
    GOAL_NG_PLUS_FRAGMENT_GATE_PERCENTS,
    MAX_CLEAR_CHECKS,
    MAX_CONFIGURABLE_UNLOCK_COPIES,
    MAX_KILL_CHECKS,
    MAX_PERFECT_CHECKS,
    MAX_ROGUESCORE_CHECKS,
    MAX_SHOP_CHECKS,
    PROGRESSIVE_SHOP_UNLOCK_RATES,
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


class GoalNgPlusFragmentGatePercent(Choice):
    """
    How much of the Progressive Shop must be unlocked before `NG+` appears in the shop.

    If Progressive Shop is disabled, this gate is ignored and `NG+` appears normally.
    """

    display_name = "NG+ Fragment Gate"

    option_percent_0 = 0
    option_percent_25 = 25
    option_percent_50 = 50
    option_percent_75 = 75
    option_percent_100 = 100

    default = 0

    @classmethod
    def get_option_name(cls, value: int) -> str:
        if int(value) in GOAL_NG_PLUS_FRAGMENT_GATE_PERCENTS:
            return f"{int(value)}%"
        return super().get_option_name(value)


class GoalNgPlusPrice(Range):
    """
    Local shop price for `NG+`.
    """

    display_name = "NG+ Price"
    range_start = 1000
    range_end = 10000
    default = 3000


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


class ProgressiveShop(Toggle):
    """
    Locks randomized AP shop checks behind progressive ``Shop Fragment`` items.

    Each received Shop Fragment unlocks the next visible section of the tav shop until the
    whole randomized shop is available.
    """

    display_name = "Progressive Shop"
    default = 1


class ProgressiveShopUnlockRate(Choice):
    """
    How much of the randomized AP shop each received Shop Fragment unlocks.

    Lower values create more Shop Fragments and finer-grained shop progression.
    This option only affects generation when Progressive Shop is enabled.
    """

    display_name = "Progressive Shop Unlock Rate"

    option_percent_5 = 5
    option_percent_10 = 10
    option_percent_20 = 20
    option_percent_25 = 25
    option_percent_50 = 50
    option_percent_100 = 100

    default = DEFAULT_PROGRESSIVE_SHOP_UNLOCK_RATE

    @classmethod
    def get_option_name(cls, value: int) -> str:
        if int(value) in PROGRESSIVE_SHOP_UNLOCK_RATES:
            return f"{int(value)}%"
        return super().get_option_name(value)


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


class DeathLinkPunishment(Choice):
    """
    Chooses what happens locally when this slot receives a DeathLink.

    Kill All Party Members: Wipes the active party, companions, and summons to force a reload.
    Down Random Party Member: Downs one random active party member or companion.
    Kill Random Party Member: Fully kills one random active party member or companion.
    Remove All Resources - All: Drains every tracked resource from the whole active party and companions,
    including spell slots, actions, bonus actions, movement, rage charges, Channel Divinity, sorcery points,
    and similar class resources.
    Remove All Resources - Random: Drains every tracked resource from one random active party member or companion,
    including spell slots, actions, bonus actions, movement, rage charges, Channel Divinity, sorcery points,
    and similar class resources.
    Remove All Actions - All: Removes only actions, bonus actions, and movement from the whole active party and companions.
    Remove All Actions - Random: Removes only actions, bonus actions, and movement from one random active
    party member or companion.
    Nothing: Receives the DeathLink notification but applies no local punishment.
    """

    display_name = "DeathLink Punishment"

    option_kill_all_party_members = 0
    option_down_random_party_member = 1
    option_kill_random_party_member = 2
    option_remove_all_resources_all = 3
    option_remove_all_resources_random = 4
    option_remove_all_actions_all = 6
    option_remove_all_actions_random = 7
    option_nothing = 5

    alias_remove_all_resources_all_party_members = option_remove_all_resources_all
    alias_remove_all_resources_one_party_member = option_remove_all_resources_random

    default = option_kill_all_party_members

    @classmethod
    def get_option_name(cls, value: int) -> str:
        option_names = {
            cls.option_kill_all_party_members: "Kill All Party Members",
            cls.option_down_random_party_member: "Down Random Party Member",
            cls.option_kill_random_party_member: "Kill Random Party Member",
            cls.option_remove_all_resources_all: "Remove All Resources - All",
            cls.option_remove_all_resources_random: "Remove All Resources - Random",
            cls.option_remove_all_actions_all: "Remove All Actions - All",
            cls.option_remove_all_actions_random: "Remove All Actions - Random",
            cls.option_nothing: "Nothing",
        }
        return option_names.get(int(value), super().get_option_name(value))


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
        DeathLinkPunishment,
    ]),
    OptionGroup("Goals", [
        Goal,
        GoalClearTarget,
        GoalRogueScoreTarget,
        GoalNgPlusFragmentGatePercent,
        GoalNgPlusPrice,
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
        ProgressiveShop,
        ProgressiveShopUnlockRate,
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
        "death_link_punishment": DeathLinkPunishment.option_kill_all_party_members,
        "goal": Goal.option_clear_stages,
        "goal_clear_target": 20,
        "goal_rogue_score_target": 300,
        "goal_ng_plus_fragment_gate_percent": 0,
        "goal_ng_plus_price": 3000,
        "clear_check_count": 10,
        "clear_check_interval": 1,
        "kill_check_count": 10,
        "kill_check_interval": 10,
        "perfect_check_count": 5,
        "perfect_check_interval": 1,
        "roguescore_check_count": 10,
        "roguescore_check_interval": 25,
        "progressive_shop": True,
        "progressive_shop_unlock_rate": DEFAULT_PROGRESSIVE_SHOP_UNLOCK_RATE,
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
        "death_link_punishment": DeathLinkPunishment.option_kill_all_party_members,
        "goal": Goal.option_clear_stages,
        "goal_clear_target": 10,
        "goal_rogue_score_target": 150,
        "goal_ng_plus_fragment_gate_percent": 0,
        "goal_ng_plus_price": 3000,
        "clear_check_count": 6,
        "clear_check_interval": 1,
        "kill_check_count": 6,
        "kill_check_interval": 12,
        "perfect_check_count": 3,
        "perfect_check_interval": 1,
        "roguescore_check_count": 4,
        "roguescore_check_interval": 50,
        "progressive_shop": True,
        "progressive_shop_unlock_rate": DEFAULT_PROGRESSIVE_SHOP_UNLOCK_RATE,
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
    "death_link_punishment": DeathLinkPunishment,
    "goal": Goal,
    "goal_clear_target": GoalClearTarget,
    "goal_rogue_score_target": GoalRogueScoreTarget,
    "goal_ng_plus_fragment_gate_percent": GoalNgPlusFragmentGatePercent,
    "goal_ng_plus_price": GoalNgPlusPrice,
    "clear_check_count": ClearCheckCount,
    "clear_check_interval": ClearCheckInterval,
    "kill_check_count": KillCheckCount,
    "kill_check_interval": KillCheckInterval,
    "perfect_check_count": PerfectCheckCount,
    "perfect_check_interval": PerfectCheckInterval,
    "roguescore_check_count": RogueScoreCheckCount,
    "roguescore_check_interval": RogueScoreCheckInterval,
    "progressive_shop": ProgressiveShop,
    "progressive_shop_unlock_rate": ProgressiveShopUnlockRate,
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
