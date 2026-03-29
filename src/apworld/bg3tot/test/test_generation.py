from .bases import BG3TrialsTestBase


class TestDefaultGeneration(BG3TrialsTestBase):
    def test_slot_data_matches_configured_counts(self) -> None:
        slot_data = self.world.fill_slot_data()

        self.assertEqual(len(slot_data["clear_thresholds"]), int(self.world.options.clear_check_count))
        self.assertEqual(len(slot_data["kill_thresholds"]), int(self.world.options.kill_check_count))
        self.assertEqual(len(slot_data["perfect_thresholds"]), int(self.world.options.perfect_check_count))
        self.assertEqual(len(slot_data["roguescore_thresholds"]), int(self.world.options.roguescore_check_count))
        self.assertEqual(len(slot_data["shop_check_unlock_ids"]), int(self.world.options.shop_check_count))
        self.assertEqual(len(slot_data["shop_check_costs"]), int(self.world.options.shop_check_count))


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
