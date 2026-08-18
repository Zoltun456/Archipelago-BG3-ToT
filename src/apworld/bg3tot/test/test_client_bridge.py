import asyncio
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from .. import bg3_client


class TestBridgeJsonIo(unittest.TestCase):
    def make_context(self, directory: str) -> bg3_client.BG3Context:
        context = object.__new__(bg3_client.BG3Context)
        context.se_bg3 = directory
        context._bridge_diagnostic_warning_times = {}
        return context

    def test_atomic_write_replaces_snapshot_and_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)

            context._write_json_atomic("status.json", {"heartbeat": 7})

            with open(os.path.join(directory, "status.json"), "r", encoding="utf-8") as file_handle:
                self.assertEqual(json.load(file_handle), {"heartbeat": 7})
            self.assertEqual(
                [name for name in os.listdir(directory) if name.endswith(".tmp")],
                [],
            )

    def test_failed_atomic_replace_preserves_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            status_path = os.path.join(directory, "status.json")
            with open(status_path, "w", encoding="utf-8") as file_handle:
                json.dump({"heartbeat": 1}, file_handle)

            with patch.object(bg3_client.os, "replace", side_effect=PermissionError("busy")):
                with self.assertRaises(PermissionError):
                    context._write_json_atomic("status.json", {"heartbeat": 2})

            with open(status_path, "r", encoding="utf-8") as file_handle:
                self.assertEqual(json.load(file_handle), {"heartbeat": 1})
            self.assertEqual(
                [name for name in os.listdir(directory) if name.endswith(".tmp")],
                [],
            )

    def test_malformed_json_uses_default_and_rate_limits_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            with open(os.path.join(directory, "status.json"), "w", encoding="utf-8") as file_handle:
                file_handle.write("")

            with patch.object(bg3_client.logger, "warning") as warning:
                self.assertEqual(context._load_json("status.json", {"fallback": True}), {"fallback": True})
                self.assertEqual(context._load_json("status.json", {"fallback": True}), {"fallback": True})

            warning.assert_called_once()

    def test_status_write_failure_does_not_escape_into_network_callbacks(self) -> None:
        context = self.make_context("")
        context.bridge_heartbeat = 0
        context.bridge_connection_state = "connected"
        context.bridge_status_text = "Connected."
        context.bridge_last_error = ""
        context.server_address = "example.invalid:38281"
        context.auth = "Player"
        context.username = "Player"
        context.slot_data_cache = {}
        context.items_received = []
        context.checked_locations = set()
        context.slot = 1
        context._write_json_atomic = Mock(side_effect=PermissionError("busy"))
        context._warn_bridge_diagnostic = Mock()

        context._write_bridge_status()

        self.assertEqual(context.bridge_heartbeat, 1)
        context._warn_bridge_diagnostic.assert_called_once()

    def test_options_file_is_published_as_an_atomic_snapshot(self) -> None:
        context = self.make_context("")
        context.slot_data_cache = {"shop_check_unlock_ids": []}
        context.seed_name = "Test Seed"
        context._build_shop_display_entries = Mock(return_value=[])
        context._write_json = Mock()
        context._write_json_atomic = Mock()

        context._write_options_file(active_connection=True)

        context._write_json_atomic.assert_called_once_with(
            context.sync_option,
            {
                "shop_check_unlock_ids": [],
                "shop_check_costs": [],
                "seed_name": "Test Seed",
                "active_connection": True,
                "shop_display": [],
            },
        )
        context._write_json.assert_not_called()

    def test_received_item_history_is_published_as_an_atomic_snapshot(self) -> None:
        context = self.make_context("")
        context._write_json_atomic = Mock()

        with patch.object(bg3_client, "_encode_received_items", return_value=["ToTUnlock:ShopFragment:0"]):
            context._write_received_items_file()

        context._write_json_atomic.assert_called_once_with(
            context.comm_file_sent_items,
            ["ToTUnlock:ShopFragment:0"],
        )

    def test_deactivation_marks_options_inactive_before_clearing_item_history(self) -> None:
        context = self.make_context("")
        context.bridge_mode = False
        context._write_json = Mock()
        atomic_writes: list[tuple[str, object]] = []
        context._write_json_atomic = Mock(
            side_effect=lambda file_name, payload: atomic_writes.append((file_name, payload))
        )

        context._deactivate_bridge_state(clear_files=True)

        self.assertEqual(
            atomic_writes[:2],
            [
                (context.sync_option, {"seed_name": "", "active_connection": False}),
                (context.comm_file_sent_items, []),
            ],
        )


class TestGameWatcherRecovery(unittest.TestCase):
    def test_exception_path_yields_before_retrying(self) -> None:
        exit_event = SimpleNamespace(done=False)
        exit_event.is_set = lambda: exit_event.done
        context = SimpleNamespace(
            exit_event=exit_event,
            syncing=False,
            comm_file_locations_checked="ap_out.json",
            _load_json=Mock(side_effect=RuntimeError("test failure")),
            _append_bridge_log=Mock(side_effect=OSError("log unavailable")),
            _write_bridge_status=Mock(),
        )
        sleep_delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_delays.append(delay)
            exit_event.done = True

        with (
            patch.object(bg3_client.asyncio, "sleep", new=fake_sleep),
            patch.object(bg3_client, "ui_text", return_value="communication error"),
        ):
            asyncio.run(bg3_client.game_watcher(context))

        self.assertEqual(sleep_delays, [bg3_client.GAME_WATCHER_POLL_INTERVAL_SECONDS])
