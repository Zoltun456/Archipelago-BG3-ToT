from test.bases import WorldTestBase

from ..world import BG3World


class BG3TrialsTestBase(WorldTestBase):
    game = "Baldur's Gate 3 - ToT"
    world: BG3World
