from __future__ import annotations

from itertools import count
import asyncio
import json
import logging
import os
import sys
import typing

from typing import Any, Dict

from .items import AP_ITEM_TO_BG3_ID, IS_DUPEABLE
from .locations import BG3_LOCATION_TO_AP_LOCATIONS, LOCATION_NAME_TO_ID
from .trials_data import shop_location_name
from .world import BG3World

import ModuleUpdate

ModuleUpdate.update()

import Utils

if __name__ == "__main__":
    Utils.init_logging("BG3Client", exception_logger="Client")

from CommonClient import (
    CommonContext,
    ClientCommandProcessor,
    get_base_parser,
    gui_enabled,
    logger,
    server_loop,
)
from NetUtils import ClientStatus


class BG3ClientCommandProcessor(ClientCommandProcessor):
    def _cmd_resync(self):
        """Manually trigger a resync."""
        self.output("Syncing items.")
        self.ctx.syncing = True


class BG3Context(CommonContext):
    command_processor = BG3ClientCommandProcessor
    game = "Baldur's Gate 3 - ToT"
    items_handling = 0b111
    se_bg3 = ""
    comm_file_sent_items = "ap_in.json"
    comm_file_locations_checked = "ap_out.json"
    sync_option = "ap_options.json"
    shop_icon_blue = "ap_trials_icon_blue_001"
    shop_icon_color = "ap_trials_icon_color_001"

    def __init__(self, server_address: str | None, password: str | None):
        super().__init__(server_address, password)
        self.syncing = False
        self.slot_data_cache: dict[str, Any] = {}

        game_options = BG3World.settings
        if "localappdata" in os.environ:
            appdata_bg3 = os.path.join(os.environ["localappdata"], "Larian Studios", "Baldur's Gate 3")
        else:
            try:
                appdata_bg3 = game_options.root_directory
            except FileNotFoundError:
                print_error_and_close(
                    "BG3Client couldn't detect a path to the Baldur's Gate 3 folder.\n"
                    'Try setting the "root_directory" value in your local options file '
                    "to the folder BG3 is installed to."
                )

        self.se_bg3 = os.path.expandvars(os.path.join(appdata_bg3, "Script Extender"))
        if not os.path.isdir(self.se_bg3):
            print_error_and_close(
                "BG3Client couldn't find the Script Extender folder in your BG3 install.\n"
                "Please make sure Script Extender has been installed, and BG3 has been run at least once since."
            )

        self._ensure_json_file(self.comm_file_sent_items)
        self._ensure_json_file(self.comm_file_locations_checked)
        self._deactivate_bridge_state(clear_files=True)

    def _file_path(self, file_name: str) -> str:
        return os.path.join(self.se_bg3, file_name)

    def _ensure_json_file(self, file_name: str) -> None:
        path = self._file_path(file_name)
        if not os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as file_handle:
                file_handle.write("[]")

    def _shop_icon_key(self, is_local_item: bool) -> str:
        return self.shop_icon_blue if is_local_item else self.shop_icon_color

    def _load_json(self, file_name: str, default_value: Any) -> Any:
        path = self._file_path(file_name)
        if not os.path.isfile(path):
            return default_value
        try:
            with open(path, "r", encoding="utf-8") as file_handle:
                return json.load(file_handle)
        except (OSError, json.JSONDecodeError):
            return default_value

    def _write_json(self, file_name: str, payload: Any) -> None:
        path = self._file_path(file_name)
        with open(path, "w", encoding="utf-8") as file_handle:
            json.dump(payload, file_handle)

    def _deactivate_bridge_state(self, clear_files: bool = False) -> None:
        if clear_files:
            self._write_json(self.comm_file_sent_items, [])
            self._write_json(self.comm_file_locations_checked, [])

        self._write_json(
            self.sync_option,
            {
                "seed_name": "",
                "active_connection": False,
            },
        )

    def _reset_for_new_seed_if_needed(self) -> None:
        current_seed = self.seed_name or ""
        if not current_seed:
            return

        existing_options = self._load_json(self.sync_option, {})
        previous_seed = existing_options.get("seed_name", "")
        if previous_seed and previous_seed == current_seed:
            return

        self._write_json(self.comm_file_sent_items, [])
        self._write_json(self.comm_file_locations_checked, [])

    def _shop_location_ids(self) -> list[int]:
        location_ids: list[int] = []
        for index, _unlock_id in enumerate(self.slot_data_cache.get("shop_check_unlock_ids", []), start=1):
            location_name = shop_location_name(index)
            location_id = LOCATION_NAME_TO_ID.get(location_name)
            if location_id is not None:
                location_ids.append(location_id)
        return location_ids

    def _build_shop_display(self) -> list[dict[str, Any]]:
        display_entries: list[dict[str, Any]] = []
        for index, location_id in enumerate(self._shop_location_ids(), start=1):
            info = self.locations_info.get(location_id)
            if not info:
                display_entries.append({})
                continue

            item_name = self.item_names.lookup_in_slot(info.item, info.player)
            player_name = self.player_names.get(info.player, f"Player {info.player}")
            is_local_item = info.player == self.slot
            display_entries.append(
                {
                    "index": index,
                    "item_name": item_name,
                    "player_name": player_name,
                    "is_local_item": is_local_item,
                    "icon_key": self._shop_icon_key(is_local_item),
                    "bg3_item_id": AP_ITEM_TO_BG3_ID.get(item_name, ""),
                    "location_name": self.location_names.lookup_in_slot(location_id, self.slot),
                    "display_name": f"{item_name} -> {player_name}",
                }
            )
        return display_entries

    def _write_options_file(self, active_connection: bool = True) -> None:
        if not self.slot_data_cache and active_connection:
            return

        payload = dict(self.slot_data_cache)
        payload["seed_name"] = self.seed_name or ""
        payload["active_connection"] = active_connection
        payload["shop_display"] = self._build_shop_display()
        self._write_json(self.sync_option, payload)

    def _request_shop_scouts(self) -> None:
        location_ids = self._shop_location_ids()
        if not location_ids:
            return

        self.locations_scouted.update(location_ids)
        asyncio.create_task(
            self.send_msgs([{"cmd": "LocationScouts", "locations": location_ids}]),
            name="BG3ShopScouts",
        )

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    @property
    def endpoints(self):
        return [self.server] if self.server else []

    def run_gui(self):
        from kvui import GameManager

        class BG3Manager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago Baldur's Gate 3 - ToT Client"

        self.ui = BG3Manager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    def on_package(self, cmd: str, args: dict):
        if cmd == "Connected":
            self._reset_for_new_seed_if_needed()
            self.slot_data_cache = dict(args["slot_data"])
            self._write_options_file(active_connection=True)
            self._request_shop_scouts()
            self._write_json(self.comm_file_sent_items, _encode_received_items(self))

        if cmd == "RoomInfo":
            self.seed_name = args["seed_name"]
            self._reset_for_new_seed_if_needed()
            self._write_options_file(active_connection=True)

        if cmd == "ReceivedItems":
            self._write_json(self.comm_file_sent_items, _encode_received_items(self))

        if cmd == "LocationInfo":
            self._write_options_file(active_connection=True)

    async def shutdown(self):
        self._deactivate_bridge_state(clear_files=True)
        await super().shutdown()


def _encode_received_items(ctx: BG3Context) -> list[str]:
    encoded_items = [
        AP_ITEM_TO_BG3_ID[ctx.item_names.lookup_in_game(network_item.item)]
        for network_item in ctx.items_received
    ]

    level_counter = count()
    gold_counter = count()
    trap_counter = count()
    dupe_counter = count()
    unlock_counter = count()
    trials_counter = count()

    encoded_output: list[str] = []
    for item in encoded_items:
        if item == "LevelUp":
            encoded_output.append(f"LevelUp<{next(level_counter)}>")
        elif item.startswith("Gold-"):
            encoded_output.append(f"{item}-{next(gold_counter)}")
        elif item.startswith("Trap-Monster"):
            encoded_output.append(f"{item}-2e51b930-c9fd-41f2-8013-02c92e990de2-{next(trap_counter)}")
        elif item.startswith("Trap-"):
            encoded_output.append(f"{item}-{next(trap_counter)}")
        elif item.startswith("ToTUnlock:"):
            encoded_output.append(f"{item}:{next(unlock_counter)}")
        elif item.startswith("ToTFiller:"):
            encoded_output.append(f"{item}:{next(trials_counter)}")
        elif IS_DUPEABLE.get(item, False):
            encoded_output.append(f"Dupe-{next(dupe_counter):04}-{item}")
        else:
            encoded_output.append(item)

    return encoded_output


async def game_watcher(ctx: BG3Context):
    while not ctx.exit_event.is_set():
        try:
            if ctx.syncing:
                await ctx.send_msgs([{"cmd": "Sync"}])
                ctx.syncing = False

            sending = []
            victory = False
            checked_tokens = []

            path = ctx._file_path(ctx.comm_file_locations_checked)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as file_handle:
                    checked_tokens = json.load(file_handle)
            else:
                with open(path, "w", encoding="utf-8") as file_handle:
                    file_handle.write("[]")

            for token in checked_tokens:
                if token not in BG3_LOCATION_TO_AP_LOCATIONS:
                    continue

                for ap_location in BG3_LOCATION_TO_AP_LOCATIONS[token]:
                    if ap_location == "Victory":
                        victory = True
                        continue

                    location_id = LOCATION_NAME_TO_ID.get(ap_location)
                    if location_id is None:
                        continue
                    if location_id not in ctx.checked_locations:
                        sending.append(location_id)
                        ctx.checked_locations.add(location_id)

            if sending:
                await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sending}])

            if victory and not ctx.finished_game:
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                ctx.finished_game = True

            await asyncio.sleep(3)
        except Exception as err:
            logger.error("Exception in communication thread, a check may not have been sent: " + str(err))


def print_error_and_close(msg: str):
    logger.error("Error: " + msg)
    Utils.messagebox("Error", msg, error=True)
    sys.exit(1)


def launch_bg3_client(*launch_args: str):
    async def main():
        args = parser.parse_args(launch_args)
        ctx = BG3Context(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        progression_watcher = asyncio.create_task(game_watcher(ctx), name="BG3ProgressionWatcher")

        await ctx.exit_event.wait()
        ctx.server_address = None

        await progression_watcher
        await ctx.shutdown()

    import colorama

    parser = get_base_parser(description="BG3 Trials client, for text interfacing.")

    colorama.just_fix_windows_console()
    asyncio.run(main())
    colorama.deinit()
