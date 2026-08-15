from types import SimpleNamespace
import unittest

from .. import items


class _TrapRandom:
    def randint(self, _start: int, _end: int) -> int:
        return 0

    def choice(self, sequence):
        return list(sequence)[0]


class _TrapWorld:
    def __init__(self, enabled_traps: set[str], *, include_equipment_fillers: bool = True) -> None:
        self.random = _TrapRandom()
        self.options = SimpleNamespace(
            traps_percentage=100,
            enabled_traps=enabled_traps,
            include_equipment_fillers=include_equipment_fillers,
        )


class _FillerRandom:
    def randint(self, _start: int, _end: int) -> int:
        return 100

    def choice(self, sequence):
        return list(sequence)[-1]


class _FillerWorld:
    def __init__(self, *, include_equipment_fillers: bool) -> None:
        self.random = _FillerRandom()
        self.options = SimpleNamespace(
            traps_percentage=0,
            enabled_traps=set(),
            include_equipment_fillers=include_equipment_fillers,
        )


class TestTrapGeneration(unittest.TestCase):
    def test_cheesed_trap_can_be_selected(self) -> None:
        world = _TrapWorld({"Cheesed"})

        self.assertEqual(items.get_random_filler_item_name(world), "Cheesed Trap")

    def test_equipment_fillers_can_be_removed_from_filler_pool(self) -> None:
        world_with_equipment = _FillerWorld(include_equipment_fillers=True)
        world_without_equipment = _FillerWorld(include_equipment_fillers=False)

        self.assertEqual(
            items.get_random_filler_item_name(world_with_equipment),
            items.EQUIPMENT_FILLER_ITEM_NAMES[-1],
        )
        self.assertEqual(
            items.get_random_filler_item_name(world_without_equipment),
            items.BASE_FILLER_ITEM_NAMES[-1],
        )

    def test_retired_duplicate_fillers_remain_receive_compatible(self) -> None:
        expected_legacy_items = {
            "Potion of Healing": "d47006e9-8a51-453d-b200-9e0d42e9bbab",
            "Supply Pack": "a24a2ca2-a213-424c-833d-47c79934c0ce",
            "Lockpick": "e32a200c-5b63-414d-ae57-00e7b38f125b",
        }

        for item_name, bg3_id in expected_legacy_items.items():
            self.assertEqual(items.AP_ITEM_TO_BG3_ID[item_name], bg3_id)
            self.assertTrue(items.IS_DUPEABLE[bg3_id])
            self.assertNotIn(item_name, items.FILLER_ITEM_NAMES)
