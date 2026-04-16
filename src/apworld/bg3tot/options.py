from __future__ import annotations

from dataclasses import make_dataclass

from Options import Choice, DeathLink, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .i18n import canonical_text
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


def _option_display_name(key: str) -> str:
    return canonical_text(f"options.{key}.display_name")


def _option_doc(key: str) -> str:
    return canonical_text(f"options.{key}.doc")


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
                "__doc__": canonical_text("options.unlock_copies.doc_template", unlock_name=unlock_name),
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


class BG3DeathLink(DeathLink):
    display_name = _option_display_name("death_link")


class IncludeEquipmentFillers(Toggle):
    __doc__ = _option_doc("include_equipment_fillers")
    display_name = _option_display_name("include_equipment_fillers")
    default = 1


class Goal(Choice):
    __doc__ = _option_doc("goal")
    display_name = _option_display_name("goal")

    option_buy_ng_plus = 0
    option_clear_stages = 1
    option_reach_rogue_score = 2

    default = option_buy_ng_plus

    @classmethod
    def get_option_name(cls, value: int) -> str:
        option_names = {
            cls.option_buy_ng_plus: canonical_text("options.goal.choice_names.buy_ng_plus"),
            cls.option_clear_stages: canonical_text("options.goal.choice_names.clear_stages"),
            cls.option_reach_rogue_score: canonical_text("options.goal.choice_names.reach_rogue_score"),
        }
        return option_names.get(int(value), super().get_option_name(value))


class GoalClearTarget(Range):
    __doc__ = _option_doc("goal_clear_target")
    display_name = _option_display_name("goal_clear_target")
    range_start = 1
    range_end = 100
    default = 20


class GoalRogueScoreTarget(Range):
    __doc__ = _option_doc("goal_rogue_score_target")
    display_name = _option_display_name("goal_rogue_score_target")
    range_start = 25
    range_end = 1000
    default = 300


class GoalNgPlusFragmentGatePercent(Choice):
    __doc__ = _option_doc("goal_ng_plus_fragment_gate_percent")
    display_name = _option_display_name("goal_ng_plus_fragment_gate_percent")

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
    __doc__ = _option_doc("goal_ng_plus_price")
    display_name = _option_display_name("goal_ng_plus_price")
    range_start = 1000
    range_end = 10000
    default = 3000


class ClearCheckCount(Range):
    __doc__ = _option_doc("clear_check_count")
    display_name = _option_display_name("clear_check_count")
    range_start = 0
    range_end = MAX_CLEAR_CHECKS
    default = 20


class ClearCheckInterval(Range):
    __doc__ = _option_doc("clear_check_interval")
    display_name = _option_display_name("clear_check_interval")
    range_start = 1
    range_end = 10
    default = 1


class KillCheckCount(Range):
    __doc__ = _option_doc("kill_check_count")
    display_name = _option_display_name("kill_check_count")
    range_start = 0
    range_end = MAX_KILL_CHECKS
    default = 20


class KillCheckInterval(Range):
    __doc__ = _option_doc("kill_check_interval")
    display_name = _option_display_name("kill_check_interval")
    range_start = 1
    range_end = 50
    default = 5


class PerfectCheckCount(Range):
    __doc__ = _option_doc("perfect_check_count")
    display_name = _option_display_name("perfect_check_count")
    range_start = 0
    range_end = MAX_PERFECT_CHECKS
    default = 5


class PerfectCheckInterval(Range):
    __doc__ = _option_doc("perfect_check_interval")
    display_name = _option_display_name("perfect_check_interval")
    range_start = 1
    range_end = 5
    default = 1


class RogueScoreCheckCount(Range):
    __doc__ = _option_doc("roguescore_check_count")
    display_name = _option_display_name("roguescore_check_count")
    range_start = 0
    range_end = MAX_ROGUESCORE_CHECKS
    default = 10


class RogueScoreCheckInterval(Range):
    __doc__ = _option_doc("roguescore_check_interval")
    display_name = _option_display_name("roguescore_check_interval")
    range_start = 5
    range_end = 100
    default = 25


class ShopCheckCount(Range):
    __doc__ = _option_doc("shop_check_count")
    display_name = _option_display_name("shop_check_count")
    range_start = 0
    range_end = MAX_SHOP_CHECKS
    default = min(50, MAX_SHOP_CHECKS)


class ProgressiveShop(Toggle):
    __doc__ = _option_doc("progressive_shop")
    display_name = _option_display_name("progressive_shop")
    default = 1


class ProgressiveShopUnlockRate(Choice):
    __doc__ = _option_doc("progressive_shop_unlock_rate")
    display_name = _option_display_name("progressive_shop_unlock_rate")

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
    __doc__ = _option_doc("shop_price_minimum")
    display_name = _option_display_name("shop_price_minimum")
    range_start = 10
    range_end = 1000
    default = 30


class ShopPriceMaximum(Range):
    __doc__ = _option_doc("shop_price_maximum")
    display_name = _option_display_name("shop_price_maximum")
    range_start = 10
    range_end = 1000
    default = 250


class PermanentBuffTarget(Choice):
    __doc__ = _option_doc("permanent_buff_target")
    display_name = _option_display_name("permanent_buff_target")

    option_user_character = 0
    option_random_party_member = 1
    option_all_party_members = 2

    default = option_random_party_member

    @classmethod
    def get_option_name(cls, value: int) -> str:
        option_names = {
            cls.option_user_character: canonical_text("options.permanent_buff_target.choice_names.user_character"),
            cls.option_random_party_member: canonical_text("options.permanent_buff_target.choice_names.random_party_member"),
            cls.option_all_party_members: canonical_text("options.permanent_buff_target.choice_names.all_party_members"),
        }
        return option_names.get(int(value), super().get_option_name(value))


class VanillaPixieBlessingInShop(Toggle):
    __doc__ = _option_doc("vanilla_pixie_blessing_in_shop")
    display_name = _option_display_name("vanilla_pixie_blessing_in_shop")


class DeathLinkTrigger(Choice):
    __doc__ = _option_doc("death_link_trigger")
    display_name = _option_display_name("death_link_trigger")

    option_full_party_wipe = 0
    option_any_party_kill = 1
    option_any_party_downed = 2

    default = option_full_party_wipe

    @classmethod
    def get_option_name(cls, value: int) -> str:
        option_names = {
            cls.option_full_party_wipe: canonical_text("options.death_link_trigger.choice_names.full_party_wipe"),
            cls.option_any_party_kill: canonical_text("options.death_link_trigger.choice_names.any_party_kill"),
            cls.option_any_party_downed: canonical_text("options.death_link_trigger.choice_names.any_party_downed"),
        }
        return option_names.get(int(value), super().get_option_name(value))


class DeathLinkPunishment(Choice):
    __doc__ = _option_doc("death_link_punishment")
    display_name = _option_display_name("death_link_punishment")

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
            cls.option_kill_all_party_members: canonical_text("options.death_link_punishment.choice_names.kill_all_party_members"),
            cls.option_down_random_party_member: canonical_text("options.death_link_punishment.choice_names.down_random_party_member"),
            cls.option_kill_random_party_member: canonical_text("options.death_link_punishment.choice_names.kill_random_party_member"),
            cls.option_remove_all_resources_all: canonical_text("options.death_link_punishment.choice_names.remove_all_resources_all"),
            cls.option_remove_all_resources_random: canonical_text("options.death_link_punishment.choice_names.remove_all_resources_random"),
            cls.option_remove_all_actions_all: canonical_text("options.death_link_punishment.choice_names.remove_all_actions_all"),
            cls.option_remove_all_actions_random: canonical_text("options.death_link_punishment.choice_names.remove_all_actions_random"),
            cls.option_nothing: canonical_text("options.death_link_punishment.choice_names.nothing"),
        }
        return option_names.get(int(value), super().get_option_name(value))


class TrapsPercentage(Range):
    __doc__ = _option_doc("traps_percentage")
    display_name = _option_display_name("traps_percentage")
    range_start = 0
    range_end = 100
    default = 20


class EnabledTraps(OptionSet):
    __doc__ = _option_doc("enabled_traps")

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
    display_name = _option_display_name("enabled_traps")
    default = DEFAULT_ENABLED_TRAPS

    @classmethod
    def get_option_name(cls, value: str) -> str:
        option_names = {
            "Monster": canonical_text("options.enabled_traps.choice_names.monster"),
            "Bleeding": canonical_text("options.enabled_traps.choice_names.bleeding"),
            "Stun": canonical_text("options.enabled_traps.choice_names.stun"),
            "Confusion": canonical_text("options.enabled_traps.choice_names.confusion"),
            "Bane": canonical_text("options.enabled_traps.choice_names.bane"),
            "Blindness": canonical_text("options.enabled_traps.choice_names.blindness"),
            "Slow": canonical_text("options.enabled_traps.choice_names.slow"),
            "Poisoned": canonical_text("options.enabled_traps.choice_names.poisoned"),
            "FaerieFire": canonical_text("options.enabled_traps.choice_names.faerie_fire"),
            "Ensnared": canonical_text("options.enabled_traps.choice_names.ensnared"),
            "Frightened": canonical_text("options.enabled_traps.choice_names.frightened"),
            "Burning": canonical_text("options.enabled_traps.choice_names.burning"),
            "HoldPerson": canonical_text("options.enabled_traps.choice_names.hold_person"),
            "Cheesed": canonical_text("options.enabled_traps.choice_names.cheesed"),
            "Silence": canonical_text("options.enabled_traps.choice_names.silence"),
            "Grease": canonical_text("options.enabled_traps.choice_names.grease"),
        }
        return option_names.get(str(value), super().get_option_name(value))


bg3_option_groups = [
    OptionGroup(canonical_text("option_groups.game_options"), [
        BG3DeathLink,
        DeathLinkTrigger,
        DeathLinkPunishment,
    ]),
    OptionGroup(canonical_text("option_groups.goals"), [
        Goal,
        GoalClearTarget,
        GoalRogueScoreTarget,
        GoalNgPlusFragmentGatePercent,
        GoalNgPlusPrice,
    ]),
    OptionGroup(canonical_text("option_groups.check_thresholds"), [
        ClearCheckCount,
        ClearCheckInterval,
        KillCheckCount,
        KillCheckInterval,
        PerfectCheckCount,
        PerfectCheckInterval,
        RogueScoreCheckCount,
        RogueScoreCheckInterval,
    ]),
    OptionGroup(canonical_text("option_groups.shop"), [
        ProgressiveShop,
        ProgressiveShopUnlockRate,
        ShopCheckCount,
        ShopPriceMinimum,
        ShopPriceMaximum,
        VanillaPixieBlessingInShop,
        PermanentBuffTarget,
    ]),
    OptionGroup(canonical_text("option_groups.unlock_pool"), [
        *UNLOCK_POOL_OPTION_GROUP,
        IncludeEquipmentFillers,
    ], True),
    OptionGroup(canonical_text("option_groups.client_and_traps"), [
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
    canonical_text("presets.release_defaults"): _preset_with_unlock_defaults({
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
    canonical_text("presets.quick_trial"): _preset_with_unlock_defaults({
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
    "death_link": BG3DeathLink,
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
