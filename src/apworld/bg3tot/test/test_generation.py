from .bases import BG3TrialsTestBase
from ..options import BG3Options, PermanentBuffTarget
from ..trials_data import (
    PIXIE_BLESSING_UNLOCK_ID,
    UNLOCK_CATALOG,
    UNLOCK_CLASSIFICATION_BY_ID,
    UNLOCK_ID_ORDER,
    MAX_CONFIGURABLE_UNLOCK_COPIES,
    selected_shop_unlock_ids,
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
        shop_locations = [location for location in self.world.get_locations() if location.name.startswith("Shop Check")]

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
