from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import BG3World


def set_all_rules(world: BG3World) -> None:
    world.multiworld.completion_condition[world.player] = lambda state: state.has("Victory", world.player)
