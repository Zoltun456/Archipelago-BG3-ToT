from worlds.LauncherComponents import Component, Type, components, launch

from .world import BG3World as BG3World


def run_client(*args: str) -> None:
    from .bg3_client import launch_bg3_client

    launch(launch_bg3_client, name="Baldur's Gate 3 - ToT Client", args=args)


components.append(
    Component(
        "Baldur's Gate 3 - ToT Client",
        func=run_client,
        game_name="Baldur's Gate 3 - ToT",
        component_type=Type.CLIENT,
        supports_uri=True,
    )
)
