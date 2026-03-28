from __future__ import annotations

import copy
from itertools import count
import asyncio
import json
import logging
import os
import sys
import typing

from typing import Any, Dict

from .items import AP_ITEM_TO_BG3_ID, IS_DUPEABLE
from .trials_data import (
    CLEAR_LOCATION_BASE_ID,
    KILL_LOCATION_BASE_ID,
    LOCATION_NAME_TO_ID,
    PERFECT_LOCATION_BASE_ID,
    ROGUESCORE_LOCATION_BASE_ID,
    SHOP_LOCATION_BASE_ID,
    clear_location_name,
    kill_location_name,
    location_id_for_token,
    perfect_location_name,
    roguescore_location_name,
    shop_location_id,
    shop_location_name,
)
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
    comm_file_notifications = "ap_notifications.json"
    comm_file_deathlink_in = "ap_deathlink_in.json"
    comm_file_deathlink_out = "ap_deathlink_out.json"
    sync_option = "ap_options.json"
    shop_icon_blue = "ap_trials_icon_blue_001"
    shop_icon_color = "ap_trials_icon_color_001"

    def __init__(self, server_address: str | None, password: str | None):
        super().__init__(server_address, password)
        self.syncing = False
        self.slot_data_cache: dict[str, Any] = {}
        self.incoming_deathlink_counter = 0

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
        self._ensure_json_file(self.comm_file_notifications)
        self._ensure_json_file(self.comm_file_deathlink_in)
        self._ensure_json_file(self.comm_file_deathlink_out)
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

    def _death_link_enabled(self) -> bool:
        return bool(self.slot_data_cache.get("death_link", False))

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
            self._write_json(self.comm_file_notifications, [])
            self._write_json(self.comm_file_deathlink_in, [])
            self._write_json(self.comm_file_deathlink_out, [])

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
        self._write_json(self.comm_file_notifications, [])
        self._write_json(self.comm_file_deathlink_in, [])
        self._write_json(self.comm_file_deathlink_out, [])

    def _shop_location_ids(self) -> list[int]:
        return [
            shop_location_id(index)
            for index, _unlock_id in enumerate(self.slot_data_cache.get("shop_check_unlock_ids", []), start=1)
        ]

    def _dynamic_location_name(self, location_id: int, player: int | None = None) -> str | None:
        if player is not None and self.slot is not None and player != self.slot:
            return None

        # AP's static lookup table knows the full theory ranges. For player-facing text,
        # rebuild the active "X/current_total" names from this slot's actual settings.
        shop_display_indices = self._shop_display_index_by_location_id()
        groups = (
            (CLEAR_LOCATION_BASE_ID, len(self.slot_data_cache.get("clear_thresholds", [])), clear_location_name),
            (KILL_LOCATION_BASE_ID, len(self.slot_data_cache.get("kill_thresholds", [])), kill_location_name),
            (PERFECT_LOCATION_BASE_ID, len(self.slot_data_cache.get("perfect_thresholds", [])), perfect_location_name),
            (ROGUESCORE_LOCATION_BASE_ID, len(self.slot_data_cache.get("roguescore_thresholds", [])), roguescore_location_name),
            (SHOP_LOCATION_BASE_ID, len(self.slot_data_cache.get("shop_check_unlock_ids", [])), shop_location_name),
        )
        for base_id, total, name_factory in groups:
            index = int(location_id) - base_id
            if total > 0 and 1 <= index <= total:
                if base_id == SHOP_LOCATION_BASE_ID:
                    return name_factory(shop_display_indices.get(int(location_id), index), total)
                return name_factory(index, total)
        return None

    def _shop_display_sort_key(self, entry: dict[str, Any]) -> tuple[int, str, int, str, int]:
        display = entry.get("display", {})
        return (
            0 if entry.get("has_info") else 1,
            str(display.get("player_name", "")).lower(),
            int(entry.get("cost", 0) or 0),
            str(display.get("item_name", display.get("display_name", ""))),
            int(entry.get("token_index", 0) or 0),
        )

    def _shop_display_index_by_location_id(self) -> dict[int, int]:
        display_entries = self._build_shop_display_entries(include_location_names=False)
        sorted_entries = sorted(display_entries, key=self._shop_display_sort_key)
        return {
            int(entry["location_id"]): display_index
            for display_index, entry in enumerate(sorted_entries, start=1)
        }

    def _build_shop_display_entries(self, *, include_location_names: bool = True) -> list[dict[str, Any]]:
        display_entries: list[dict[str, Any]] = []
        unlock_ids = list(self.slot_data_cache.get("shop_check_unlock_ids", []))
        costs = list(self.slot_data_cache.get("shop_check_costs", []))

        # Keep the AP token order intact here. The Lua shop UI can sort the visible cards,
        # but the hidden token index still needs to line up with the seed's location ids.
        for token_index, location_id in enumerate(self._shop_location_ids(), start=1):
            info = self.locations_info.get(location_id)
            unlock_id = unlock_ids[token_index - 1] if token_index - 1 < len(unlock_ids) else ""
            cost = costs[token_index - 1] if token_index - 1 < len(costs) else 0
            if not info:
                display_entries.append(
                    {
                        "token_index": token_index,
                        "location_id": location_id,
                        "unlock_id": unlock_id,
                        "cost": cost,
                        "display": {},
                        "has_info": False,
                    }
                )
                continue

            try:
                info_flags = int(getattr(info, "flags", 0) or 0)
            except (TypeError, ValueError):
                info_flags = 0
            if info_flags & 0b100:
                cost = 0

            item_name = self.item_names.lookup_in_slot(info.item, info.player)
            player_name = self.player_names.get(info.player, f"Player {info.player}")
            is_local_item = info.player == self.slot
            display_entries.append(
                {
                    "token_index": token_index,
                    "location_id": location_id,
                    "unlock_id": unlock_id,
                    "cost": cost,
                    "has_info": True,
                    "display": {
                        "token_index": token_index,
                        "item_name": item_name,
                        "player_name": player_name,
                        "is_local_item": is_local_item,
                        "icon_key": self._shop_icon_key(is_local_item),
                        "bg3_item_id": AP_ITEM_TO_BG3_ID.get(item_name, ""),
                        "display_name": f"{item_name} -> {player_name}",
                    },
                }
            )

        if include_location_names and display_entries:
            total_entries = len(display_entries)
            for visual_index, entry in enumerate(sorted(display_entries, key=self._shop_display_sort_key), start=1):
                entry["display"]["location_name"] = shop_location_name(visual_index, total_entries)

        return display_entries

    def _write_options_file(self, active_connection: bool = True) -> None:
        if not self.slot_data_cache and active_connection:
            return

        payload = dict(self.slot_data_cache)
        shop_display_entries = self._build_shop_display_entries()
        payload["shop_check_unlock_ids"] = list(self.slot_data_cache.get("shop_check_unlock_ids", []))
        payload["shop_check_costs"] = [int(entry["cost"]) for entry in shop_display_entries]
        payload["seed_name"] = self.seed_name or ""
        payload["active_connection"] = active_connection
        payload["shop_display"] = [entry["display"] for entry in shop_display_entries]
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

    def _append_notification(self, payload: dict[str, Any]) -> None:
        pending = self._load_json(self.comm_file_notifications, [])
        if not isinstance(pending, list):
            pending = []
        pending.append(payload)
        self._write_json(self.comm_file_notifications, pending)

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
            asyncio.create_task(
                self.update_death_link(self._death_link_enabled()),
                name="BG3DeathLinkConnected",
            )

        if cmd == "RoomInfo":
            self.seed_name = args["seed_name"]
            self._reset_for_new_seed_if_needed()
            self._write_options_file(active_connection=True)

        if cmd == "ReceivedItems":
            self._write_json(self.comm_file_sent_items, _encode_received_items(self))

        if cmd == "LocationInfo":
            self._write_options_file(active_connection=True)

    def on_print_json(self, args: dict):
        message_parts = _normalize_notification_parts(self, copy.deepcopy(args.get("data", [])))
        normalized_args = dict(args)
        normalized_args["data"] = message_parts
        super().on_print_json(normalized_args)

        if args.get("type") != "ItemSend" or self.slot is None:
            return
        if self.is_uninteresting_item_send(args):
            return

        message = self.rawjsontotextparser(copy.deepcopy(message_parts)).strip()
        if message:
            self._append_notification(
                {
                    "text": message,
                    "segments": _encode_notification_segments(self, message_parts),
                    "type": args.get("type", ""),
                }
            )

    def on_deathlink(self, data: dict, text: str = "") -> None:
        try:
            super().on_deathlink(data, text=text)
        except TypeError:
            super().on_deathlink(data)
        self.incoming_deathlink_counter += 1

        pending = self._load_json(self.comm_file_deathlink_in, [])
        if not isinstance(pending, list):
            pending = []

        pending.append(
            {
                "id": self.incoming_deathlink_counter,
                "time": data.get("time"),
                "source": data.get("source", ""),
                "cause": data.get("cause", "") or text,
            }
        )
        self._write_json(self.comm_file_deathlink_in, pending)

    async def shutdown(self):
        await self.update_death_link(False)
        self._deactivate_bridge_state(clear_files=True)
        await super().shutdown()


def _color_for_item_flags(flags: int) -> str:
    if flags == 0:
        return "cyan"
    if flags & 0b001:
        return "plum"
    if flags & 0b010:
        return "slateblue"
    if flags & 0b100:
        return "salmon"
    return "cyan"


def _color_for_notification_part(ctx: BG3Context, part: dict[str, Any]) -> str:
    part_type = str(part.get("type", "") or "")
    if part_type == "color":
        return str(part.get("color", "") or "")
    if part_type == "player_id":
        try:
            player = int(part.get("text", 0))
        except (TypeError, ValueError):
            return "yellow"
        return "magenta" if ctx.slot_concerns_self(player) else "yellow"
    if part_type == "player_name":
        return "yellow"
    if part_type in {"item_name", "item_id"}:
        try:
            flags = int(part.get("flags", 0) or 0)
        except (TypeError, ValueError):
            flags = 0
        return _color_for_item_flags(flags)
    if part_type in {"location_name", "location_id"}:
        return "green"
    if part_type == "entrance_name":
        return "blue"
    return str(part.get("color", "") or "")


def _text_for_notification_part(ctx: BG3Context, part: dict[str, Any]) -> str:
    part_type = str(part.get("type", "") or "")
    raw_text = str(part.get("text", "") or "")

    try:
        if part_type == "player_id":
            return ctx.player_names.get(int(raw_text), raw_text)
        if part_type == "item_id":
            return ctx.item_names.lookup_in_slot(int(raw_text), int(part.get("player", 0) or 0))
        if part_type == "location_name":
            player = int(part.get("player", 0) or 0)
            location_id = LOCATION_NAME_TO_ID.get(raw_text)
            if location_id is not None:
                return ctx._dynamic_location_name(location_id, player) or raw_text
        if part_type == "location_id":
            location_id = int(raw_text)
            player = int(part.get("player", 0) or 0)
            return ctx._dynamic_location_name(location_id, player) or ctx.location_names.lookup_in_slot(location_id, player)
    except (TypeError, ValueError, KeyError):
        return raw_text

    return raw_text


def _encode_notification_segments(ctx: BG3Context, parts: list[Any]) -> list[dict[str, str]]:
    encoded_segments: list[dict[str, str]] = []
    for raw_part in parts:
        if not isinstance(raw_part, dict):
            continue

        text = _text_for_notification_part(ctx, raw_part)
        if not text:
            continue

        segment = {"text": text}
        color = _color_for_notification_part(ctx, raw_part)
        if color:
            segment["color"] = color
        encoded_segments.append(segment)

    return encoded_segments


def _normalize_notification_parts(ctx: BG3Context, parts: list[Any]) -> list[Any]:
    normalized_parts: list[Any] = []
    for raw_part in parts:
        if not isinstance(raw_part, dict):
            normalized_parts.append(raw_part)
            continue

        part = dict(raw_part)
        part_type = str(part.get("type", "") or "")
        if part_type in {"location_name", "location_id"}:
            text = _text_for_notification_part(ctx, part)
            if text:
                part["text"] = text
                part["type"] = "location_name"
        normalized_parts.append(part)

    return normalized_parts


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
                resolved_location = location_id_for_token(
                    token,
                    clear_count=len(ctx.slot_data_cache.get("clear_thresholds", [])),
                    kill_count=len(ctx.slot_data_cache.get("kill_thresholds", [])),
                    perfect_count=len(ctx.slot_data_cache.get("perfect_thresholds", [])),
                    roguescore_count=len(ctx.slot_data_cache.get("roguescore_thresholds", [])),
                    shop_count=len(ctx.slot_data_cache.get("shop_check_unlock_ids", [])),
                )
                if resolved_location == "Victory":
                    victory = True
                    continue
                if resolved_location is None:
                    continue
                if resolved_location not in ctx.checked_locations:
                    sending.append(resolved_location)
                    ctx.checked_locations.add(resolved_location)

            if sending:
                await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sending}])

            deathlink_events = ctx._load_json(ctx.comm_file_deathlink_out, [])
            if not isinstance(deathlink_events, list):
                deathlink_events = []

            remaining_deathlink_events: list[dict[str, Any]] = []
            if deathlink_events and ctx._death_link_enabled():
                for deathlink_event in deathlink_events:
                    if not isinstance(deathlink_event, dict):
                        continue

                    death_text = str(deathlink_event.get("text", "") or "suffered a Trials defeat.")
                    try:
                        await ctx.send_death(death_text)
                    except Exception as err:
                        logger.error("Exception while sending DeathLink: %s", err)
                        remaining_deathlink_events.append(deathlink_event)

            if deathlink_events:
                ctx._write_json(ctx.comm_file_deathlink_out, remaining_deathlink_events)

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
