from .bases import BG3TrialsTestBase
from BaseClasses import LocationProgressType
from ..i18n import canonical_text
from ..options import BG3Options, PermanentBuffTarget
from ..trials_data import (
    PIXIE_BLESSING_UNLOCK_ID,
    SHOP_FRAGMENT_ITEM_NAME,
    UNLOCK_CATALOG,
    UNLOCK_CLASSIFICATION_BY_ID,
    UNLOCK_ID_ORDER,
    MAX_CONFIGURABLE_UNLOCK_COPIES,
    build_shop_layout,
    selected_shop_unlock_ids,
    shop_location_name,
    unlock_copies_option_name,
)


class TestDefaultGeneration(BG3TrialsTestBase):
    def test_slot_data_matches_configured_counts(self) -> None:
        slot_data = self.world.fill_slot_data()
        expected_shop_unlock_ids = selected_shop_unlock_ids(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
            option_values=self.world.options,
        )

        self.assertEqual(len(slot_data["clear_thresholds"]), int(self.world.options.clear_check_count))
        self.assertEqual(len(slot_data["kill_thresholds"]), int(self.world.options.kill_check_count))
        self.assertEqual(len(slot_data["perfect_thresholds"]), int(self.world.options.perfect_check_count))
        self.assertEqual(len(slot_data["roguescore_thresholds"]), int(self.world.options.roguescore_check_count))
        self.assertEqual(slot_data["shop_check_unlock_ids"], expected_shop_unlock_ids)
        self.assertEqual(len(slot_data["shop_check_costs"]), len(expected_shop_unlock_ids))
        self.assertTrue(slot_data["progressive_shop"])
        self.assertEqual(slot_data["death_link_punishment"], 0)
        self.assertEqual(slot_data["progressive_shop_unlock_rate"], 10)
        self.assertEqual(slot_data["shop_fragment_count"], 10)
        self.assertEqual(slot_data["goal_ng_plus_fragment_gate_percent"], 0)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_percent"], 0)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_fragments"], 0)
        self.assertEqual(slot_data["goal_unlock_cost"], 3000)
        self.assertEqual(len(slot_data["shop_section_indices"]), len(expected_shop_unlock_ids))
        self.assertEqual(slot_data["vanilla_pixie_blessing_in_shop"], bool(self.world.options.vanilla_pixie_blessing_in_shop))
        self.assertEqual(slot_data["permanent_buff_target"], int(self.world.options.permanent_buff_target))
        self.assertEqual(slot_data["unlock_classifications_by_id"], UNLOCK_CLASSIFICATION_BY_ID)


class TestAutomaticShopExpansion(BG3TrialsTestBase):
    options = {
        "goal": "clear_stages",
        "clear_check_count": 6,
        "clear_check_interval": 1,
        "kill_check_count": 6,
        "kill_check_interval": 10,
        "perfect_check_count": 2,
        "perfect_check_interval": 1,
        "roguescore_check_count": 4,
        "roguescore_check_interval": 25,
        "shop_check_count": 0,
    }

    def test_non_filler_unlocks_still_create_shop_checks_when_requested_count_is_zero(self) -> None:
        slot_data = self.world.fill_slot_data()
        expected_shop_unlock_ids = selected_shop_unlock_ids(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
            option_values=self.world.options,
        )
        expected_non_filler_count = sum(
            int(unlock["copies"])
            for unlock in UNLOCK_CATALOG
            if unlock["classification"] != "filler"
        )

        self.assertEqual(slot_data["shop_check_unlock_ids"], expected_shop_unlock_ids)
        self.assertEqual(len(slot_data["shop_check_unlock_ids"]), expected_non_filler_count)
        self.assertTrue(slot_data["shop_check_unlock_ids"])
        self.assertTrue(
            all(
                UNLOCK_CLASSIFICATION_BY_ID[unlock_id] != "filler"
                for unlock_id in slot_data["shop_check_unlock_ids"]
            )
        )
        self.assertEqual(len(slot_data["shop_check_costs"]), len(slot_data["shop_check_unlock_ids"]))


class TestPermanentBuffTargetGeneration(BG3TrialsTestBase):
    options = {
        "permanent_buff_target": "all_party_members",
    }

    def test_slot_data_keeps_selected_buff_target(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertEqual(
            slot_data["permanent_buff_target"],
            PermanentBuffTarget.option_all_party_members,
        )


class TestDeathLinkPunishmentGeneration(BG3TrialsTestBase):
    options = {
        "death_link": True,
        "death_link_punishment": "remove_all_resources_random",
    }

    def test_slot_data_keeps_selected_deathlink_punishment(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertTrue(slot_data["death_link"])
        self.assertEqual(slot_data["death_link_punishment"], 4)


class TestDeathLinkActionPunishmentGeneration(BG3TrialsTestBase):
    options = {
        "death_link": True,
        "death_link_punishment": "remove_all_actions_random",
    }

    def test_slot_data_keeps_selected_action_only_punishment(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertTrue(slot_data["death_link"])
        self.assertEqual(slot_data["death_link_punishment"], 7)


class TestDeathLinkPunishmentAliasGeneration(BG3TrialsTestBase):
    options = {
        "death_link": True,
        "death_link_punishment": "remove_all_resources_one_party_member",
    }

    def test_legacy_resource_drain_name_still_maps_to_random(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertTrue(slot_data["death_link"])
        self.assertEqual(slot_data["death_link_punishment"], 4)


class TestVanillaPixieBlessingInShopGeneration(BG3TrialsTestBase):
    options = {
        "shop_check_count": 4,
        "vanilla_pixie_blessing_in_shop": True,
    }

    def test_slot_data_excludes_pixie_blessing_from_randomized_shop_checks(self) -> None:
        slot_data = self.world.fill_slot_data()
        expected_shop_unlock_ids = selected_shop_unlock_ids(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
            option_values=self.world.options,
        )

        self.assertTrue(slot_data["vanilla_pixie_blessing_in_shop"])
        self.assertNotIn(PIXIE_BLESSING_UNLOCK_ID, slot_data["shop_check_unlock_ids"])
        self.assertEqual(slot_data["shop_check_unlock_ids"], expected_shop_unlock_ids)


class TestUnlockPoolGeneration(BG3TrialsTestBase):
    options = {
        "shop_check_count": len(UNLOCK_ID_ORDER),
        unlock_copies_option_name("Tadpole"): 3,
    }

    def test_slot_data_respects_unlock_pool_options(self) -> None:
        slot_data = self.world.fill_slot_data()
        expected_shop_unlock_ids = selected_shop_unlock_ids(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
            option_values=self.world.options,
        )
        shop_prefix = canonical_text("locations.shop_check")
        shop_locations = [location for location in self.world.get_locations() if location.name.startswith(shop_prefix)]

        self.assertIn("include_equipment_fillers", BG3Options.type_hints)
        self.assertNotIn("buy_ascension_enabled", BG3Options.type_hints)
        self.assertEqual(BG3Options.type_hints["tadpole_copies"].range_end, MAX_CONFIGURABLE_UNLOCK_COPIES)
        self.assertEqual(slot_data["shop_check_unlock_ids"], expected_shop_unlock_ids)
        self.assertEqual(slot_data["shop_check_unlock_ids"].count("Tadpole"), 3)
        self.assertIn("BuyAscension", slot_data["shop_check_unlock_ids"])
        self.assertEqual(len(shop_locations), len(expected_shop_unlock_ids))


class TestUsefulUnlockCopiesExpandShopChecks(BG3TrialsTestBase):
    options = {
        "shop_check_count": 1,
        unlock_copies_option_name("BuyLootRare"): 12,
    }

    def test_useful_unlock_copies_are_not_clipped_by_requested_shop_count(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertGreater(len(slot_data["shop_check_unlock_ids"]), int(self.world.options.shop_check_count))
        self.assertEqual(slot_data["shop_check_unlock_ids"].count("BuyLootRare"), 12)


class TestProgressiveShopGeneration(BG3TrialsTestBase):
    options = {
        "progressive_shop": True,
        "progressive_shop_unlock_rate": 20,
    }

    def test_shop_fragments_are_added_and_sections_cover_the_shop(self) -> None:
        slot_data = self.world.fill_slot_data()
        shop_layout = build_shop_layout(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
            option_values=self.world.options,
        )
        local_item_names = [item.name for item in self.multiworld.itempool if item.player == self.world.player]
        expected_priority_locations: set[str] = set()
        prioritized_per_section: dict[int, int] = {}
        for index, section_index in enumerate(slot_data["shop_section_indices"], start=1):
            section_index = int(section_index)
            if section_index <= 0:
                continue
            prioritized_count = prioritized_per_section.get(section_index, 0)
            if prioritized_count < 2:
                expected_priority_locations.add(shop_location_name(index))
                prioritized_per_section[section_index] = prioritized_count + 1

        self.assertEqual(slot_data["shop_fragment_count"], 5)
        self.assertEqual(slot_data["shop_fragment_count"], int(shop_layout["fragment_count"]))
        self.assertEqual(slot_data["shop_section_indices"], list(shop_layout["section_indices"]))
        self.assertEqual(local_item_names.count(SHOP_FRAGMENT_ITEM_NAME), 5)
        self.assertEqual(min(slot_data["shop_section_indices"]), 1)
        self.assertEqual(max(slot_data["shop_section_indices"]), 5)
        self.assertEqual(self.multiworld.local_early_items[self.world.player].get(SHOP_FRAGMENT_ITEM_NAME), 1)
        self.assertEqual(self.multiworld.early_items[self.world.player].get(SHOP_FRAGMENT_ITEM_NAME), 1)
        for location in self.world.get_locations():
            if location.name in expected_priority_locations:
                self.assertEqual(location.progress_type, LocationProgressType.PRIORITY)
            elif location.name.startswith(canonical_text("locations.shop_check")):
                self.assertEqual(location.progress_type, LocationProgressType.DEFAULT)


class TestNgPlusGateGeneration(BG3TrialsTestBase):
    options = {
        "progressive_shop": True,
        "progressive_shop_unlock_rate": 10,
        "goal_ng_plus_fragment_gate_percent": 50,
        "goal_ng_plus_price": 4500,
    }

    def test_ng_plus_gate_uses_effective_fragment_count_and_custom_price(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertEqual(slot_data["shop_fragment_count"], 10)
        self.assertEqual(slot_data["goal_ng_plus_fragment_gate_percent"], 50)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_percent"], 50)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_fragments"], 5)
        self.assertEqual(slot_data["goal_unlock_cost"], 4500)


class TestNgPlusGateDisablesWithoutProgressiveShop(BG3TrialsTestBase):
    options = {
        "progressive_shop": False,
        "goal_ng_plus_fragment_gate_percent": 100,
    }

    def test_ng_plus_gate_turns_off_when_progressive_shop_is_disabled(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertFalse(slot_data["progressive_shop"])
        self.assertEqual(slot_data["shop_fragment_count"], 0)
        self.assertEqual(slot_data["goal_ng_plus_fragment_gate_percent"], 100)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_percent"], 0)
        self.assertEqual(slot_data["effective_goal_ng_plus_fragment_gate_fragments"], 0)
