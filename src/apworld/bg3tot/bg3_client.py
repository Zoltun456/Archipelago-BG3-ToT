from __future__ import annotations

import copy
from itertools import count
import asyncio
import json
import logging
import os
import sys
import time
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

BRIDGE_COMMAND_FILE = "ap_client_commands.json"
BRIDGE_STATUS_FILE = "ap_client_status.json"
BRIDGE_LOG_FILE = "ap_client_log.json"
BRIDGE_LOG_LIMIT = 200
BRIDGE_POLL_INTERVAL_SECONDS = 1.0


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

    def __init__(self, server_address: str | None, password: str | None, *, bridge_mode: bool = False):
        super().__init__(server_address, password)
        self.bridge_mode = bridge_mode
        self.syncing = False
        self.slot_data_cache: dict[str, Any] = {}
        self.incoming_deathlink_counter = 0
        self.notification_counter = 0
        self.bridge_heartbeat = 0
        self.bridge_connection_state = "disconnected"
        self._preserve_connection_target_once = False
        self.bridge_status_text = (
            "Client runtime running. Use the in-game Archipelago tab to connect."
            if bridge_mode
            else "ToT Client open. Press Connect here or in the client window."
        )
        self.bridge_last_error = ""

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
        self._ensure_json_file(BRIDGE_COMMAND_FILE)
        self._ensure_json_file(BRIDGE_LOG_FILE)
        self._ensure_json_file(BRIDGE_STATUS_FILE, {})
        self._write_json(BRIDGE_COMMAND_FILE, [])
        self._clear_bridge_log()
        self._deactivate_bridge_state(clear_files=True)
        self._write_bridge_status()
        if self.bridge_mode:
            self._append_bridge_log("Client runtime running. Use the in-game Archipelago tab to connect.")
            self._append_bridge_log("Keep this runtime window open while you play BG3.")
        else:
            self._append_bridge_log("ToT Client open. Connect here or from the in-game Archipelago tab.")
            self._append_bridge_log("Closing this client window stops the Archipelago client.")

    def _file_path(self, file_name: str) -> str:
        return os.path.join(self.se_bg3, file_name)

    def _ensure_json_file(self, file_name: str, default_value: Any | None = None) -> None:
        if default_value is None:
            default_value = []
        path = self._file_path(file_name)
        if not os.path.isfile(path):
            with open(path, "w", encoding="utf-8") as file_handle:
                json.dump(default_value, file_handle)

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

    def _bridge_slot_name(self) -> str:
        return str(getattr(self, "auth", None) or getattr(self, "username", None) or "")

    def _write_bridge_status(self, *, bridge_running: bool = True) -> None:
        self.bridge_heartbeat += 1
        self._write_json(
            BRIDGE_STATUS_FILE,
            {
                "bridge_running": bridge_running,
                "heartbeat": self.bridge_heartbeat,
                "connection_state": self.bridge_connection_state,
                "status_text": self.bridge_status_text,
                "last_error": self.bridge_last_error,
                "server_address": getattr(self, "server_address", "") or "",
                "slot_name": self._bridge_slot_name(),
                "seed_name": getattr(self, "seed_name", "") or "",
                "death_link_enabled": self._death_link_enabled(),
                "items_received": len(getattr(self, "items_received", [])),
                "locations_checked": len(getattr(self, "checked_locations", [])),
                "connected": getattr(self, "slot", None) is not None,
            },
        )

    def _append_bridge_log(self, text: str, *, level: str = "info") -> None:
        message = str(text or "").strip()
        if not message:
            return

        existing = self._load_json(BRIDGE_LOG_FILE, [])
        if not isinstance(existing, list):
            existing = []

        existing.append(
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "level": str(level or "info"),
                "text": message,
            }
        )
        if len(existing) > BRIDGE_LOG_LIMIT:
            existing = existing[-BRIDGE_LOG_LIMIT:]
        self._write_json(BRIDGE_LOG_FILE, existing)

    def _clear_bridge_log(self) -> None:
        self._write_json(BRIDGE_LOG_FILE, [])

    def _clear_bridge_connection_target(self) -> None:
        self.server_address = None
        self.server = None
        self.password = None
        self.auth = None
        self.username = None

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
        self.bridge_connection_state = "disconnected"
        if self.bridge_mode:
            self.bridge_status_text = "Client runtime running. Use the in-game Archipelago tab to connect."
        else:
            self.bridge_status_text = "ToT Client open. Press Connect here or in the client window."
        self.bridge_last_error = ""

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

    def _checked_location_indices_by_location_id(self) -> tuple[dict[int, int], dict[int, int]]:
        checked_tokens = self._load_json(self.comm_file_locations_checked, [])
        if not isinstance(checked_tokens, list):
            return {}, {}

        counters = {
            CLEAR_LOCATION_BASE_ID: 0,
            KILL_LOCATION_BASE_ID: 0,
            PERFECT_LOCATION_BASE_ID: 0,
            ROGUESCORE_LOCATION_BASE_ID: 0,
            SHOP_LOCATION_BASE_ID: 0,
        }
        seen_locations: set[int] = set()
        sequence_indices: dict[int, int] = {}
        progress_indices: dict[int, int] = {}
        location_sequence = 0

        for token in checked_tokens:
            resolved_location = location_id_for_token(
                str(token or ""),
                clear_count=len(self.slot_data_cache.get("clear_thresholds", [])),
                kill_count=len(self.slot_data_cache.get("kill_thresholds", [])),
                perfect_count=len(self.slot_data_cache.get("perfect_thresholds", [])),
                roguescore_count=len(self.slot_data_cache.get("roguescore_thresholds", [])),
                shop_count=len(self.slot_data_cache.get("shop_check_unlock_ids", [])),
            )
            if not isinstance(resolved_location, int) or resolved_location in seen_locations:
                continue

            seen_locations.add(resolved_location)
            location_sequence += 1
            sequence_indices[resolved_location] = location_sequence
            for base_id in counters:
                if base_id < resolved_location < base_id + 100:
                    counters[base_id] += 1
                    progress_indices[resolved_location] = counters[base_id]
                    break

        return sequence_indices, progress_indices

    def _checked_location_progress_index_by_location_id(self) -> dict[int, int]:
        _sequence_indices, progress_indices = self._checked_location_indices_by_location_id()
        return progress_indices

    def _dynamic_location_name(self, location_id: int, player: int | None = None) -> str | None:
        if player is not None and self.slot is not None and player != self.slot:
            return None

        # AP's static lookup table knows the full theory ranges. For player-facing text,
        # rebuild the active "X/current_total" names from this slot's actual settings.
        # For notifications, prefer the order the checks were actually earned in local play.
        progress_indices = self._checked_location_progress_index_by_location_id()
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
                progress_index = progress_indices.get(int(location_id))
                if progress_index is not None:
                    return name_factory(progress_index, total)
                if base_id == SHOP_LOCATION_BASE_ID:
                    return name_factory(shop_display_indices.get(int(location_id), index), total)
                return name_factory(index, total)
        return None

    def _shop_display_sort_key(self, entry: dict[str, Any]) -> tuple[int, int, str, int, str, int]:
        display = entry.get("display", {})
        return (
            int(display.get("section_index", 0) or 0),
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
        section_indices = list(self.slot_data_cache.get("shop_section_indices", []))
        section_names = list(self.slot_data_cache.get("shop_section_names", []))

        # Keep the AP token order intact here. The Lua shop UI can sort the visible cards,
        # but the hidden token index still needs to line up with the seed's location ids.
        for token_index, location_id in enumerate(self._shop_location_ids(), start=1):
            info = self.locations_info.get(location_id)
            unlock_id = unlock_ids[token_index - 1] if token_index - 1 < len(unlock_ids) else ""
            cost = costs[token_index - 1] if token_index - 1 < len(costs) else 0
            section_index = section_indices[token_index - 1] if token_index - 1 < len(section_indices) else 0
            section_name = section_names[token_index - 1] if token_index - 1 < len(section_names) else ""
            if not info:
                display_entries.append(
                    {
                        "token_index": token_index,
                        "location_id": location_id,
                        "unlock_id": unlock_id,
                        "cost": cost,
                        "display": {
                            "token_index": token_index,
                            "section_index": int(section_index or 0),
                            "section_name": str(section_name or ""),
                        },
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
                        "section_index": int(section_index or 0),
                        "section_name": str(section_name or ""),
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
        self.notification_counter += 1
        payload["queue_order"] = self.notification_counter
        pending.append(payload)
        self._write_json(self.comm_file_notifications, pending)

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            if self.bridge_mode:
                self.bridge_connection_state = "error"
                self.bridge_status_text = "Archipelago room password required."
                self.bridge_last_error = "The room requires a password."
                self._append_bridge_log(self.bridge_last_error, level="error")
                self._write_bridge_status()
                return self.password
            await super().server_auth(password_requested)

        if self.bridge_mode and not (self.auth or self.username):
            self.bridge_connection_state = "error"
            self.bridge_status_text = "Archipelago slot name required."
            self.bridge_last_error = "A slot name is required before connecting."
            self._append_bridge_log(self.bridge_last_error, level="error")
            self._write_bridge_status()
            return self.password

        await self.get_username()
        await self.send_connect()
        return self.password

    async def connection_closed(self):
        unexpected_disconnect = not self.disconnected_intentionally
        had_active_connection = bool(self.server_address or self._bridge_slot_name() or getattr(self, "slot", None) is not None)
        self.disconnected_intentionally = True
        await super().connection_closed()
        self._write_options_file(active_connection=False)
        self._clear_bridge_connection_target()
        if self.bridge_connection_state != "error":
            self.bridge_connection_state = "disconnected"
            if unexpected_disconnect and had_active_connection:
                self.bridge_status_text = "Connection closed. The ToT client is still open; press Connect to try again."
                self.bridge_last_error = "Automatic reconnect is disabled. Press Connect to try again."
                self._append_bridge_log(
                    "Connection closed. Automatic reconnect is disabled; press Connect to try again.",
                    level="warning",
                )
            else:
                self.bridge_status_text = "ToT Client open. Press Connect here or in the client window."
                self.bridge_last_error = ""
        self._write_bridge_status()

    async def disconnect(self, allow_autoreconnect: bool = False):
        preserve_connection_target = self._preserve_connection_target_once
        self._preserve_connection_target_once = False
        await super().disconnect(False)
        self._write_options_file(active_connection=False)
        if not preserve_connection_target:
            self._clear_bridge_connection_target()
        if self.bridge_connection_state != "error":
            self.bridge_connection_state = "disconnected"
            self.bridge_status_text = "ToT Client open. Press Connect here or in the client window."
            self.bridge_last_error = ""
        self._write_bridge_status()

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
            self.bridge_connection_state = "connected"
            self.bridge_status_text = f"Connected to {self.server_address or 'Archipelago room'}."
            self.bridge_last_error = ""
            self._append_bridge_log(
                f"Connected to {self.server_address or 'Archipelago room'} as {self._bridge_slot_name() or 'unknown slot'}."
            )
            asyncio.create_task(
                self.update_death_link(self._death_link_enabled()),
                name="BG3DeathLinkConnected",
            )
            self._write_bridge_status()

        if cmd == "RoomInfo":
            self.seed_name = args["seed_name"]
            self._reset_for_new_seed_if_needed()
            self._write_options_file(active_connection=True)
            if self.bridge_connection_state != "connected":
                self.bridge_connection_state = "connecting"
                self.bridge_status_text = f"Connecting to {self.server_address or 'Archipelago room'}."
            self._write_bridge_status()

        if cmd == "ReceivedItems":
            self._write_json(self.comm_file_sent_items, _encode_received_items(self))
            self._write_bridge_status()

        if cmd == "LocationInfo":
            self._write_options_file(active_connection=True)
            self._write_bridge_status()

    def on_print_json(self, args: dict):
        raw_message_parts = copy.deepcopy(args.get("data", []))
        message_parts = _normalize_notification_parts(self, args, copy.deepcopy(raw_message_parts))
        normalized_args = dict(args)
        normalized_args["data"] = message_parts
        super().on_print_json(normalized_args)
        message = self.rawjsontotextparser(copy.deepcopy(message_parts)).strip()
        if message:
            self._append_bridge_log(message)

        if args.get("type") != "ItemSend" or self.slot is None:
            return
        if self.is_uninteresting_item_send(args):
            return

        if message:
            notification_payload = {
                "text": message,
                "segments": _encode_notification_segments(self, message_parts),
                "type": args.get("type", ""),
            }
            notification_payload.update(_notification_sort_metadata(self, args, raw_message_parts))
            self._append_notification(
                notification_payload
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
        self._append_bridge_log(
            f"Received DeathLink from {data.get('source', 'Archipelago')}: {data.get('cause', '') or text or 'Trials defeat.'}",
            level="warning",
        )
        self._write_bridge_status()

    async def shutdown(self):
        await self.update_death_link(False)
        self._write_bridge_status(bridge_running=False)
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


def _location_id_for_notification_part(ctx: BG3Context, part: dict[str, Any]) -> int | None:
    part_type = str(part.get("type", "") or "")
    raw_text = str(part.get("text", "") or "")

    try:
        if part_type == "location_id":
            return int(raw_text)
        if part_type == "location_name":
            return LOCATION_NAME_TO_ID.get(raw_text)
    except (TypeError, ValueError):
        return None

    return None


def _notification_sender_slot(ctx: BG3Context, args: dict[str, Any], parts: list[Any]) -> int | None:
    if ctx.slot is None:
        return None

    for key in ("sending", "source", "sender"):
        try:
            sender = int(args.get(key, 0) or 0)
        except (TypeError, ValueError):
            sender = 0
        if sender > 0:
            return sender

    own_name = str(ctx.player_names.get(ctx.slot, "") or "")
    first_player_name: str | None = None
    for raw_part in parts:
        if not isinstance(raw_part, dict):
            continue

        part_type = str(raw_part.get("type", "") or "")
        raw_text = str(raw_part.get("text", "") or "")
        if part_type == "player_id":
            try:
                return int(raw_text)
            except (TypeError, ValueError):
                return None
        if part_type == "player_name" and first_player_name is None:
            first_player_name = raw_text

    if own_name and first_player_name == own_name:
        return ctx.slot
    return None


def _location_matches_active_slot(ctx: BG3Context, location_id: int) -> bool:
    groups = (
        (CLEAR_LOCATION_BASE_ID, len(ctx.slot_data_cache.get("clear_thresholds", []))),
        (KILL_LOCATION_BASE_ID, len(ctx.slot_data_cache.get("kill_thresholds", []))),
        (PERFECT_LOCATION_BASE_ID, len(ctx.slot_data_cache.get("perfect_thresholds", []))),
        (ROGUESCORE_LOCATION_BASE_ID, len(ctx.slot_data_cache.get("roguescore_thresholds", []))),
        (SHOP_LOCATION_BASE_ID, len(ctx.slot_data_cache.get("shop_check_unlock_ids", []))),
    )
    for base_id, total in groups:
        index = int(location_id) - base_id
        if total > 0 and 1 <= index <= total:
            return True
    return False


def _local_location_id_for_notification(ctx: BG3Context, args: dict[str, Any], parts: list[Any]) -> int | None:
    if ctx.slot is None:
        return None
    if _notification_sender_slot(ctx, args, parts) != ctx.slot:
        return None

    for raw_part in parts:
        if not isinstance(raw_part, dict):
            continue

        location_id = _location_id_for_notification_part(ctx, raw_part)
        if location_id is None:
            continue
        if _location_matches_active_slot(ctx, location_id):
            return location_id

    return None


def _notification_sort_metadata(ctx: BG3Context, args: dict[str, Any], parts: list[Any]) -> dict[str, int]:
    if ctx.slot is None:
        return {}

    local_location_id = _local_location_id_for_notification(ctx, args, parts)
    if local_location_id is None:
        return {}

    sequence_indices, _progress_indices = ctx._checked_location_indices_by_location_id()
    local_sequence = sequence_indices.get(local_location_id)
    if local_sequence is not None:
        return {"queue_sort_sequence": local_sequence}

    return {}


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


def _normalize_notification_parts(ctx: BG3Context, args: dict[str, Any], parts: list[Any]) -> list[Any]:
    local_location_id = _local_location_id_for_notification(ctx, args, parts)
    local_location_name = None
    if local_location_id is not None:
        local_location_name = ctx._dynamic_location_name(local_location_id)

    normalized_parts: list[Any] = []
    for raw_part in parts:
        if not isinstance(raw_part, dict):
            normalized_parts.append(raw_part)
            continue

        part = dict(raw_part)
        part_type = str(part.get("type", "") or "")
        if part_type in {"location_name", "location_id"}:
            text = local_location_name or _text_for_notification_part(ctx, part)
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


async def _process_bridge_command(ctx: BG3Context, command: dict[str, Any]) -> None:
    command_type = str(command.get("type", "") or "").strip().lower()
    if not command_type:
        return

    if command_type == "connect":
        server_address = str(command.get("server_address", "") or "").strip()
        slot_name = str(command.get("slot_name", "") or "").strip()
        password = str(command.get("password", "") or "")
        if not server_address:
            ctx.bridge_connection_state = "error"
            ctx.bridge_status_text = "Archipelago room address required."
            ctx.bridge_last_error = "Cannot connect without a room address."
            ctx._append_bridge_log(ctx.bridge_last_error, level="error")
            ctx._write_bridge_status()
            return
        if not slot_name:
            ctx.bridge_connection_state = "error"
            ctx.bridge_status_text = "Archipelago slot name required."
            ctx.bridge_last_error = "Cannot connect without a slot name."
            ctx._append_bridge_log(ctx.bridge_last_error, level="error")
            ctx._write_bridge_status()
            return

        if getattr(ctx, "server", None) is not None or getattr(ctx, "slot", None) is not None:
            await ctx.disconnect()
        else:
            ctx._clear_bridge_connection_target()

        ctx.disconnected_intentionally = False
        ctx.server_address = server_address
        ctx.username = slot_name
        ctx.auth = slot_name
        ctx.password = password or None
        ctx.bridge_connection_state = "connecting"
        ctx.bridge_status_text = f"Connecting to {server_address} as {slot_name}."
        ctx.bridge_last_error = ""
        ctx._append_bridge_log(f"Connecting to {server_address} as {slot_name}.")
        ctx._write_bridge_status()
        try:
            ctx._preserve_connection_target_once = True
            await ctx.connect(server_address)
        except Exception as err:
            ctx.bridge_connection_state = "error"
            ctx.bridge_status_text = "Archipelago connection failed."
            ctx.bridge_last_error = str(err)
            ctx._append_bridge_log(f"Connection failed: {err}", level="error")
            ctx._clear_bridge_connection_target()
            ctx._write_bridge_status()
        finally:
            ctx._preserve_connection_target_once = False
        return

    if command_type == "disconnect":
        ctx._append_bridge_log("Disconnect requested from the in-game Archipelago tab.")
        await ctx.disconnect()
        return

    if command_type == "resync":
        if ctx.slot is None:
            ctx._append_bridge_log("Resync requested while disconnected.", level="warning")
        else:
            ctx._append_bridge_log("Manual resync requested from the in-game Archipelago tab.")
            ctx.syncing = True
        ctx._write_bridge_status()
        return

    if command_type == "clear_log":
        ctx._clear_bridge_log()
        return

    ctx._append_bridge_log(f"Unknown bridge command ignored: {command_type}", level="warning")


async def bridge_watcher(ctx: BG3Context):
    while not ctx.exit_event.is_set():
        try:
            pending_commands = ctx._load_json(BRIDGE_COMMAND_FILE, [])
            if not isinstance(pending_commands, list):
                pending_commands = []

            if pending_commands:
                ctx._write_json(BRIDGE_COMMAND_FILE, [])
                for command in pending_commands:
                    if not isinstance(command, dict):
                        continue
                    await _process_bridge_command(ctx, command)

            ctx._write_bridge_status()
            await asyncio.sleep(BRIDGE_POLL_INTERVAL_SECONDS)
        except Exception as err:
            logger.error("Exception in BG3 bridge watcher: %s", err)
            ctx.bridge_connection_state = "error"
            ctx.bridge_status_text = "Archipelago client command error."
            ctx.bridge_last_error = str(err)
            ctx._append_bridge_log(f"Client watcher error: {err}", level="error")
            ctx._write_bridge_status()
            await asyncio.sleep(BRIDGE_POLL_INTERVAL_SECONDS)


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
            ctx._append_bridge_log(f"Communication thread error: {err}", level="error")
            ctx._write_bridge_status()


def print_error_and_close(msg: str):
    logger.error("Error: " + msg)
    Utils.messagebox("Error", msg, error=True)
    sys.exit(1)


def launch_bg3_client(*launch_args: str):
    async def main():
        args = parser.parse_args(launch_args)
        ctx = BG3Context(args.connect, args.password, bridge_mode=args.bridge_mode)
        bridge_task = asyncio.create_task(bridge_watcher(ctx), name="BG3BridgeWatcher")
        if not args.bridge_mode or args.connect:
            ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if not args.bridge_mode:
            if gui_enabled:
                ctx.run_gui()
            ctx.run_cli()
        progression_watcher = asyncio.create_task(game_watcher(ctx), name="BG3ProgressionWatcher")

        await ctx.exit_event.wait()
        ctx.server_address = None

        await bridge_task
        await progression_watcher
        await ctx.shutdown()

    import colorama

    parser = get_base_parser(description="BG3 Trials client, for text interfacing.")
    parser.add_argument(
        "--bridge-mode",
        action="store_true",
        help="Run without the standalone UI and accept commands from the in-game Archipelago tab.",
    )

    colorama.just_fix_windows_console()
    asyncio.run(main())
    colorama.deinit()
