from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .trials_data import REGION_NAME

if TYPE_CHECKING:
    from .world import BG3World


def create_and_connect_regions(world: BG3World) -> None:
    world.multiworld.regions.append(Region(REGION_NAME, world.player, world.multiworld))
