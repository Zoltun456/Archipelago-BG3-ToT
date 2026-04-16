from BaseClasses import Tutorial

from worlds.AutoWorld import WebWorld

from .i18n import canonical_text
from .options import BG3_OPTION_PRESETS, bg3_option_groups


class BG3WebWorld(WebWorld):
    game = canonical_text("world.game_name")
    theme = "grassFlowers"
    rich_text_options_doc = False
    bug_report_page = "https://github.com/Zoltun456/Archipelago-BG3-ToT/issues"
    game_info_languages = ["en"]
    options_presets = BG3_OPTION_PRESETS
    option_groups = bg3_option_groups

    setup_en = Tutorial(
        canonical_text("tutorial.setup.title"),
        canonical_text("tutorial.setup.description"),
        canonical_text("tutorial.setup.language"),
        "setup_en.md",
        "setup/en",
        ["Zoltun", "Broney"],
    )

    tutorials = [setup_en]
