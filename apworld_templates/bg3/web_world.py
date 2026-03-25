from BaseClasses import Tutorial

from worlds.AutoWorld import WebWorld

from .options import bg3_option_groups


class BG3WebWorld(WebWorld):
    game = "Baldur's Gate 3"
    theme = "grassFlowers"
    rich_text_options_doc = False
    option_groups = bg3_option_groups

    setup_en = Tutorial(
        "Baldur's Gate 3 Trials Setup Guide",
        "Install the Trials-first BG3 Archipelago build, configure the three BG3 mods, and start a seed.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Zoltun", "Broney"],
    )

    tutorials = [setup_en]
