from types import SimpleNamespace
import unittest

from .. import items


class _TrapRandom:
    def randint(self, _start: int, _end: int) -> int:
        return 0

    def choice(self, sequence):
        return list(sequence)[0]


class _TrapWorld:
    def __init__(self, enabled_traps: set[str]) -> None:
        self.random = _TrapRandom()
        self.options = SimpleNamespace(
            traps_percentage=100,
            enabled_traps=enabled_traps,
        )


class TestTrapGeneration(unittest.TestCase):
    def test_cheesed_trap_can_be_selected(self) -> None:
        world = _TrapWorld({"Cheesed"})

        self.assertEqual(items.get_random_filler_item_name(world), "Cheesed Trap")
