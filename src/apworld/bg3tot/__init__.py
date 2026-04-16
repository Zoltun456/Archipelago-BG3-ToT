from worlds.LauncherComponents import Component, Type, components, icon_paths, launch

from .i18n import canonical_text, ui_text
from .world import BG3World as BG3World


def run_client(*args: str) -> None:
    from .bg3_client import launch_bg3_client

    launch(launch_bg3_client, name=ui_text("launcher.client_name"), args=args)


components.append(
    Component(
        ui_text("launcher.client_name"),
        func=run_client,
        game_name=canonical_text("world.game_name"),
        component_type=Type.CLIENT,
        supports_uri=True,
        icon="bg3tot",
        description=ui_text("launcher.client_description"),
    )
)
icon_paths["bg3tot"] = "ap:worlds.bg3tot/archipelago_assets/blue-icon.png"
