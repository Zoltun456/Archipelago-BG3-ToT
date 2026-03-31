from .bases import BG3TrialsTestBase
from ..options import PermanentBuffTarget
from ..trials_data import PIXIE_BLESSING_UNLOCK_ID, UNLOCK_CLASSIFICATION_BY_ID, selected_shop_unlock_ids


class TestDefaultGeneration(BG3TrialsTestBase):
    def test_slot_data_matches_configured_counts(self) -> None:
        slot_data = self.world.fill_slot_data()
        expected_shop_unlock_ids = selected_shop_unlock_ids(
            int(self.world.options.shop_check_count),
            randomize_pixie_blessing=not bool(self.world.options.vanilla_pixie_blessing_in_shop),
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


class TestShoplessGeneration(BG3TrialsTestBase):
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

    def test_slot_data_allows_zero_shop_checks(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertEqual(slot_data["shop_check_unlock_ids"], [])
        self.assertEqual(slot_data["shop_check_costs"], [])


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

        self.assertTrue(slot_data["vanilla_pixie_blessing_in_shop"])
        self.assertNotIn(PIXIE_BLESSING_UNLOCK_ID, slot_data["shop_check_unlock_ids"])
        self.assertEqual(len(slot_data["shop_check_unlock_ids"]), 4)
