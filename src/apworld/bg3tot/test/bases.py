from test.bases import WorldTestBase

from ..world import BG3World


class BG3TrialsTestBase(WorldTestBase):
    game = BG3World.game
    world: BG3World
