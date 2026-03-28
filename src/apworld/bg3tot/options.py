from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range

from .trials_data import (
    MAX_CLEAR_CHECKS,
    MAX_KILL_CHECKS,
    MAX_PERFECT_CHECKS,
    MAX_ROGUESCORE_CHECKS,
    UNLOCK_ID_ORDER,
)


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
    Converts the first N unlock entries from ``trials_unlock_catalog.json`` into AP shop checks.

    Buying one of these entries sends a location check instead of granting the reward immediately.
    The original reward becomes an AP item that must be received from the multiworld.
    """

    display_name = "Shop Check Count"
    range_start = 0
    range_end = len(UNLOCK_ID_ORDER)
    default = min(50, len(UNLOCK_ID_ORDER))


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
        "Silence",
        "Grease",
        "Monster",
    ]
    display_name = "Enabled Trap List"
    default = {
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
        "Silence",
        "Grease",
    }


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
    ]),
    OptionGroup("Client & Traps", [
        TrapsPercentage,
        EnabledTraps,
    ]),
]


@dataclass
class BG3Options(PerGameCommonOptions):
    death_link: DeathLink
    death_link_trigger: DeathLinkTrigger
    goal: Goal
    goal_clear_target: GoalClearTarget
    goal_rogue_score_target: GoalRogueScoreTarget
    clear_check_count: ClearCheckCount
    clear_check_interval: ClearCheckInterval
    kill_check_count: KillCheckCount
    kill_check_interval: KillCheckInterval
    perfect_check_count: PerfectCheckCount
    perfect_check_interval: PerfectCheckInterval
    roguescore_check_count: RogueScoreCheckCount
    roguescore_check_interval: RogueScoreCheckInterval
    shop_check_count: ShopCheckCount
    shop_price_minimum: ShopPriceMinimum
    shop_price_maximum: ShopPriceMaximum
    traps_percentage: TrapsPercentage
    enabled_traps: EnabledTraps
