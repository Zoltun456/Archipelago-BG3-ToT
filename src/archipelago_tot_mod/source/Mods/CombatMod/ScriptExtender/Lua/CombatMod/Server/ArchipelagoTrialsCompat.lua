-- This started as a mashup of the old standalone ArchipelagoTrials bridge and the later CombatMod patch.
-- Everything BG3-side for the merged ToT build lives here now.

local AP_OUT_FILE = "ap_out.json"
local AP_IN_FILE = "ap_in.json"
local AP_NOTIFICATION_FILE = "ap_notifications.json"
local AP_OPTIONS_FILE = "ap_options.json"
local AP_DEATHLINK_IN_FILE = "ap_deathlink_in.json"
local AP_DEATHLINK_OUT_FILE = "ap_deathlink_out.json"
local AP_PENDING_RECEIVED_FILE = "ap_pending_received.json"
local AP_PENDING_SHOP_UNLOCKS_FILE = "ap_pending_shop_unlocks.json"
local AP_DEBUG_SHOP_SERVER_FILE = "ap_debug_shop_server.json"
local AP_CLIENT_COMMAND_FILE = "ap_client_commands.json"
local AP_CLIENT_STATUS_FILE = "ap_client_status.json"
local AP_CLIENT_LOG_FILE = "ap_client_log.json"
local AP_CLIENT_LOG_MAX_LINES = 120
local AP_CLIENT_STALE_TIMEOUT_MS = 5000

local GOAL_BUY_NG_PLUS = 0
local GOAL_CLEAR_STAGES = 1
local GOAL_REACH_ROGUESCORE = 2
local DEATHLINK_TRIGGER_FULL_PARTY_WIPE = 0
local DEATHLINK_TRIGGER_ANY_PARTY_KILL = 1
local DEATHLINK_TRIGGER_ANY_PARTY_DOWNED = 2
local DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS = 0
local DEATHLINK_PUNISHMENT_DOWN_RANDOM_PARTY_MEMBER = 1
local DEATHLINK_PUNISHMENT_KILL_RANDOM_PARTY_MEMBER = 2
local DEATHLINK_PUNISHMENT_REMOVE_ALL_RESOURCES_ALL = 3
local DEATHLINK_PUNISHMENT_REMOVE_ALL_RESOURCES_RANDOM = 4
local DEATHLINK_PUNISHMENT_NOTHING = 5
local DEATHLINK_PUNISHMENT_REMOVE_ALL_ACTIONS_ALL = 6
local DEATHLINK_PUNISHMENT_REMOVE_ALL_ACTIONS_RANDOM = 7
local PERMANENT_BUFF_TARGET_USER_CHARACTER = 0
local PERMANENT_BUFF_TARGET_RANDOM_PARTY_MEMBER = 1
local PERMANENT_BUFF_TARGET_ALL_PARTY_MEMBERS = 2
local AP_GOAL_UNLOCK_ID = "APGOAL::QUICKSTART"
local DEFAULT_GOAL_UNLOCK_TEMPLATE_ID = "QUICKSTART"
local DEFAULT_GOAL_UNLOCK_COST = 3000
local AP_NOTIFICATION_DURATION = 6
local AP_NOTIFICATION_REORDER_GRACE_MS = 2500
local AP_PIXIE_BLESSING_UNLOCK_ID = "APLOCAL::PIXIE_BLESSING"
local AP_SHOP_SECTION_UNLOCK_PREFIX = "APSHOP::SECTION::"
local AP_LOCAL_SHOP_SECTION_NAME_HANDLE = "h315fa45ag640ag4f10gb026gc9769204eb54"
local PIXIE_BLESSING_UNLOCK_ID = "Moonshield"

Mod.PersistentVarsTemplate.ArchipelagoTrialsCompat = Mod.PersistentVarsTemplate.ArchipelagoTrialsCompat or {
    scenario_clears = 0,
    perfect_clears = 0,
    kills = 0,
    received_items = {},
    granted_unlocks = {},
    shop_unlocks = {},
    shop_fragments_received = 0,
    progressive_tadpole_unlock_entry = "",
    goal_completed = false,
    deathlink_out_counter = 0,
    deathlink_suppress_local = false,
    seed_name = "",
}

local runtime = {
    patch_registered = false,
    poll_started = false,
    event_subscriptions_ready = false,
    score_subscription_ready = false,
    connection_signature = "",
    refresh_signature = "",
    original_templates_captured = false,
    original_templates_by_id = {},
    granted_unlock_session_init = {},
    deathlink_events_ready = false,
    deathlink_party_wipe_active = false,
    pending_received_replay = {},
    pending_shop_unlock_replay = {},
    notification_next_sort_sequence = nil,
    logged_unhandled_received = {},
    archipelago_client_ui_state = nil,
    archipelago_client_signature = "",
    archipelago_client_last_heartbeat = nil,
    archipelago_client_last_seen_ms = 0,
    archipelago_client_command_counter = 0,
    archipelago_backend_prompted = false,
}

local emit_threshold_tokens
local maybe_emit_goal_token

_G.ArchipelagoTrialsCompatNotificationsOwner = true

local function load_compat_module(path, global_name)
    local loaded = rawget(_G, global_name)
    if type(loaded) == "table" then
        return loaded
    end

    local require_fn = rawget(_G, "Require")
    if type(require_fn) ~= "function" and Ext then
        require_fn = Ext.Require
    end
    if type(require_fn) ~= "function" then
        print("[ArchipelagoTrialsCompat] Unable to load module " .. tostring(path) .. ": no Require function available.")
        return nil
    end

    local ok, result = pcall(require_fn, path)
    if ok and type(result) == "table" then
        return result
    end

    loaded = rawget(_G, global_name)
    if type(loaded) == "table" then
        return loaded
    end

    if not ok then
        print("[ArchipelagoTrialsCompat] Failed to load module " .. tostring(path) .. ": " .. tostring(result))
    end

    return nil
end

local trap_rewards = load_compat_module(
    "CombatMod/Server/ArchipelagoTrialsCompat/TrapRewards",
    "ArchipelagoTrialsCompatTrapRewards"
)


local function shallow_copy(source)
    local clone = {}
    for key, value in pairs(source or {}) do
        clone[key] = value
    end
    return clone
end


local function table_get(source, key, default_value)
    if source == nil then
        return default_value
    end
    local value = source[key]
    if value == nil then
        return default_value
    end
    return value
end


local function load_json_array(path)
    local raw = Ext.IO.LoadFile(path)
    if not raw or raw == "" then
        return {}
    end

    local ok, parsed = pcall(Ext.Json.Parse, raw)
    if not ok or type(parsed) ~= "table" then
        return {}
    end

    return parsed
end


local function load_json_object(path)
    local raw = Ext.IO.LoadFile(path)
    if not raw or raw == "" then
        return {}
    end

    local ok, parsed = pcall(Ext.Json.Parse, raw)
    if not ok or type(parsed) ~= "table" then
        return {}
    end

    return parsed
end


local function save_json_array(path, data)
    Ext.IO.SaveFile(path, Ext.Json.Stringify(data))
end


local function save_json_object(path, data)
    Ext.IO.SaveFile(path, Ext.Json.Stringify(data))
end


local function unlock_id_list(unlocks)
    local ids = {}
    for _, unlock in ipairs(unlocks or {}) do
        table.insert(ids, tostring(table_get(unlock, "Id", "") or ""))
    end
    return ids
end


local function unlock_list_has_id(unlocks, unlock_id)
    unlock_id = tostring(unlock_id or "")
    for _, unlock in ipairs(unlocks or {}) do
        if tostring(table_get(unlock, "Id", "") or "") == unlock_id then
            return true
        end
    end
    return false
end


local function write_shop_debug_snapshot(stage, transformed)
    local options = load_json_object(AP_OPTIONS_FILE)
    local current_unlocks = PersistentVars.Unlocks or {}
    save_json_object(AP_DEBUG_SHOP_SERVER_FILE, {
        stage = tostring(stage or ""),
        generated_at = Ext.Utils.MonotonicTime(),
        active_connection = options.active_connection == true,
        seed_name = tostring(options.seed_name or ""),
        vanilla_pixie_blessing_in_shop = options.vanilla_pixie_blessing_in_shop == true,
        transformed_count = #((transformed or {})),
        transformed_ids = unlock_id_list(transformed or {}),
        current_unlock_count = #current_unlocks,
        current_unlock_ids = unlock_id_list(current_unlocks),
        has_goal_unlock = unlock_list_has_id(transformed or {}, AP_GOAL_UNLOCK_ID)
            or unlock_list_has_id(current_unlocks, AP_GOAL_UNLOCK_ID),
        has_pixie_unlock = unlock_list_has_id(transformed or {}, AP_PIXIE_BLESSING_UNLOCK_ID)
            or unlock_list_has_id(current_unlocks, AP_PIXIE_BLESSING_UNLOCK_ID),
        has_moonshield_unlock = unlock_list_has_id(transformed or {}, PIXIE_BLESSING_UNLOCK_ID)
            or unlock_list_has_id(current_unlocks, PIXIE_BLESSING_UNLOCK_ID),
    })
end


local function build_lookup(values)
    local lookup = {}
    for _, value in ipairs(values or {}) do
        value = tostring(value or "")
        if value ~= "" then
            lookup[value] = true
        end
    end
    return lookup
end


local function archipelago_client_default_state()
    return {
        bridge_running = false,
        bridge_stale = true,
        connection_state = "offline",
        status_text = TL("h48ec300ag1db9g4655gb7bdgf033959fd211"),
        server_address = "",
        slot_name = "",
        seed_name = "",
        death_link_enabled = false,
        items_received = 0,
        locations_checked = 0,
        last_error = "",
        log_lines = {},
    }
end


local function archipelago_backend_launch_message()
    return TL("h53bed4acg06ebg481fg9608gde79f42afc5b")
end


local function archipelago_backend_relaunch_message()
    return TL("hf6bb50e7ga3eeg405bgac58g863d4e7aa41f")
end


local function maybe_prompt_archipelago_backend(force)
    local apState = runtime.archipelago_client_ui_state or archipelago_client_default_state()
    local backend_ready = apState.bridge_running == true and apState.bridge_stale ~= true
    if backend_ready then
        runtime.archipelago_backend_prompted = false
        return
    end

    if not force and runtime.archipelago_backend_prompted then
        return
    end

    runtime.archipelago_backend_prompted = true
    local message = archipelago_backend_launch_message()
    if apState.bridge_running == true and apState.bridge_stale == true then
        message = archipelago_backend_relaunch_message()
    end

    if Player and Player.Notify then
        Player.Notify(message, true)
        return
    end

    print("[ArchipelagoTrialsCompat] " .. tostring(message))
end


local function archipelago_client_copy_state(source)
    local copy = archipelago_client_default_state()
    for key, value in pairs(source or {}) do
        if key == "log_lines" and type(value) == "table" then
            copy.log_lines = {}
            for _, entry in ipairs(value) do
                if type(entry) == "table" then
                    table.insert(copy.log_lines, {
                        text = tostring(table_get(entry, "text", "") or ""),
                        timestamp = tostring(table_get(entry, "timestamp", "") or ""),
                    })
                elseif entry ~= nil then
                    table.insert(copy.log_lines, {
                        text = tostring(entry or ""),
                        timestamp = "",
                    })
                end
            end
        else
            copy[key] = value
        end
    end
    return copy
end


local function archipelago_client_status_text(connection_state)
    if connection_state == "connected" then
        return TL("h25addd7ag70f8g4882gb169geee4934bccc6")
    end
    if connection_state == "connecting" then
        return TL("hc6ecfd20g93b9g4a87g9f5dgfce13d7fdec3")
    end
    if connection_state == "error" then
        return TL("h2d864a1eg78d3g41f4gb1ebg5792d3c975b0")
    end
    return TL("h7c017c98g2954g429cg94f3g24fab6d106d8")
end


local function sanitize_archipelago_client_log_lines(raw_lines)
    local sanitized = {}
    if type(raw_lines) ~= "table" then
        return sanitized
    end

    local start_index = math.max(1, #raw_lines - AP_CLIENT_LOG_MAX_LINES + 1)
    for index = start_index, #raw_lines do
        local entry = raw_lines[index]
        if type(entry) == "table" then
            local text = tostring(table_get(entry, "text", table_get(entry, "message", "")) or "")
            if text ~= "" then
                table.insert(sanitized, {
                    text = text,
                    timestamp = tostring(table_get(entry, "timestamp", "") or ""),
                })
            end
        elseif entry ~= nil then
            local text = tostring(entry or "")
            if text ~= "" then
                table.insert(sanitized, {
                    text = text,
                    timestamp = "",
                })
            end
        end
    end

    return sanitized
end


local function archipelago_client_public_state()
    return archipelago_client_copy_state(runtime.archipelago_client_ui_state or archipelago_client_default_state())
end


_G.ArchipelagoTrialsCompatGetClientUiState = archipelago_client_public_state


local function trim_archipelago_client_text(value, max_length)
    local text = tostring(value or "")
    if max_length and max_length > 0 and string.len(text) > max_length then
        text = string.sub(text, 1, max_length)
    end
    return text
end


local function refresh_archipelago_client_ui(force)
    local status = load_json_object(AP_CLIENT_STATUS_FILE)
    local heartbeat = tonumber(table_get(status, "heartbeat", nil))
    local bridge_running = table_get(status, "bridge_running", false) == true
    local now = Ext.Utils.MonotonicTime()

    if heartbeat ~= nil and heartbeat ~= runtime.archipelago_client_last_heartbeat then
        runtime.archipelago_client_last_heartbeat = heartbeat
        runtime.archipelago_client_last_seen_ms = now
    end

    local bridge_stale = true
    if bridge_running and runtime.archipelago_client_last_seen_ms > 0 then
        bridge_stale = (now - runtime.archipelago_client_last_seen_ms) > AP_CLIENT_STALE_TIMEOUT_MS
    end

    local connection_state = tostring(table_get(status, "connection_state", "disconnected") or "disconnected")
    local status_text = tostring(table_get(status, "status_text", "") or "")
    if not bridge_running then
        connection_state = "offline"
        status_text = archipelago_backend_launch_message()
    elseif bridge_stale then
        connection_state = "offline"
        status_text = archipelago_backend_relaunch_message()
    elseif status_text == "" then
        status_text = archipelago_client_status_text(connection_state)
    end

    local server_address = tostring(table_get(status, "server_address", "") or "")
    local slot_name = tostring(table_get(status, "slot_name", "") or "")
    local seed_name = tostring(table_get(status, "seed_name", "") or "")
    local death_link_enabled = table_get(status, "death_link_enabled", false) == true
    local items_received = tonumber(table_get(status, "items_received", 0) or 0) or 0
    local locations_checked = tonumber(table_get(status, "locations_checked", 0) or 0) or 0
    local log_lines = sanitize_archipelago_client_log_lines(load_json_array(AP_CLIENT_LOG_FILE))
    local retain_connection_identity = connection_state == "connecting" or connection_state == "connected"
    if not bridge_running or bridge_stale or not retain_connection_identity then
        server_address = ""
        slot_name = ""
    end
    if not bridge_running or bridge_stale or connection_state ~= "connected" then
        seed_name = ""
        death_link_enabled = false
        items_received = 0
        locations_checked = 0
    end
    if not bridge_running or bridge_stale then
        log_lines = {}
    end

    local next_state = {
        bridge_running = bridge_running,
        bridge_stale = bridge_stale,
        connection_state = connection_state,
        status_text = status_text,
        server_address = server_address,
        slot_name = slot_name,
        seed_name = seed_name,
        death_link_enabled = death_link_enabled,
        items_received = items_received,
        locations_checked = locations_checked,
        last_error = tostring(table_get(status, "last_error", "") or ""),
        log_lines = log_lines,
    }

    local signature = Ext.Json.Stringify(next_state)
    if force or runtime.archipelago_client_signature ~= signature then
        runtime.archipelago_client_signature = signature
        runtime.archipelago_client_ui_state = next_state
        Event.Trigger("ArchipelagoClientUiStateChanged")
        return
    end

    if runtime.archipelago_client_ui_state == nil then
        runtime.archipelago_client_ui_state = next_state
    end
end


local function enqueue_archipelago_client_command(command_type, payload)
    local commands = load_json_array(AP_CLIENT_COMMAND_FILE)
    if type(commands) ~= "table" then
        commands = {}
    end

    runtime.archipelago_client_command_counter = runtime.archipelago_client_command_counter + 1
    local command = shallow_copy(payload or {})
    command.id = runtime.archipelago_client_command_counter
    command.type = tostring(command_type or "")
    table.insert(commands, command)
    save_json_array(AP_CLIENT_COMMAND_FILE, commands)
    return command.id
end


local function clear_pending_received()
    runtime.pending_received_replay = {}
    save_json_array(AP_PENDING_RECEIVED_FILE, {})
end


local function copy_shop_unlock_record(record)
    return {
        Bought = tonumber(table_get(record, "Bought", 0) or 0) or 0,
        BoughtBy = shallow_copy(table_get(record, "BoughtBy", {}) or {}),
    }
end


local function clear_pending_shop_unlocks()
    runtime.pending_shop_unlock_replay = {}
    save_json_object(AP_PENDING_SHOP_UNLOCKS_FILE, {})
end


local function load_pending_received_replay()
    runtime.pending_received_replay = build_lookup(load_json_array(AP_PENDING_RECEIVED_FILE))
end


local function load_pending_shop_unlock_replay()
    runtime.pending_shop_unlock_replay = {}

    local pending = load_json_object(AP_PENDING_SHOP_UNLOCKS_FILE)
    for unlock_id, record in pairs(pending or {}) do
        unlock_id = tostring(unlock_id or "")
        if unlock_id ~= "" and type(record) == "table" then
            runtime.pending_shop_unlock_replay[unlock_id] = copy_shop_unlock_record(record)
        end
    end
end


local function remember_pending_received(entry)
    entry = tostring(entry or "")
    if entry == "" then
        return
    end

    local pending = load_json_array(AP_PENDING_RECEIVED_FILE)
    for _, existing in ipairs(pending) do
        if existing == entry then
            return
        end
    end

    table.insert(pending, entry)
    save_json_array(AP_PENDING_RECEIVED_FILE, pending)
end


local function remember_pending_shop_unlock(unlock_id, record)
    unlock_id = tostring(unlock_id or "")
    if unlock_id == "" then
        return
    end

    local pending = load_json_object(AP_PENDING_SHOP_UNLOCKS_FILE)
    pending[unlock_id] = copy_shop_unlock_record(record)
    save_json_object(AP_PENDING_SHOP_UNLOCKS_FILE, pending)
    runtime.pending_shop_unlock_replay[unlock_id] = copy_shop_unlock_record(record)
end


local function unlock_requires_regrant_on_replay(unlock_id)
    return unlock_id == "BuyLoot"
        or unlock_id == "BuyLootRare"
        or unlock_id == "BuyLootEpic"
        or unlock_id == "BuyLootLegendary"
end


local function notify_player(notification)
    local message = notification
    local segments = {}
    if type(notification) == "table" then
        message = notification.text or notification.message or ""
        segments = notification.segments or {}
    end

    message = tostring(message or "")
    if message == "" then
        return
    end

    if Net and Net.Send then
        Net.Send("PlayerNotify", { message })
        Net.Send("ArchipelagoTrialsNotification", {
            text = message,
            segments = segments,
            duration = AP_NOTIFICATION_DURATION,
        })
        return
    end

    if Player and Player.Notify then
        Player.Notify(message)
        return
    end

    print("[ArchipelagoTrialsCompat] " .. message)
end


local function notification_queue_order(entry, fallback_order)
    if type(entry) == "table" then
        local queue_order = tonumber(entry.queue_order)
        if queue_order ~= nil then
            return queue_order
        end
    end
    return tonumber(fallback_order or 0) or 0
end


local function notification_queue_sort_sequence(entry)
    if type(entry) ~= "table" then
        return nil
    end
    return tonumber(entry.queue_sort_sequence)
end


local function sort_notification_queue(queue)
    for index, entry in ipairs(queue or {}) do
        if type(entry) == "table" and tonumber(entry.queue_order) == nil then
            entry.queue_order = index
        end
    end

    table.sort(queue, function(a, b)
        local a_sequence = notification_queue_sort_sequence(a)
        local b_sequence = notification_queue_sort_sequence(b)
        if a_sequence ~= nil and b_sequence ~= nil and a_sequence ~= b_sequence then
            return a_sequence < b_sequence
        end

        return notification_queue_order(a, 0) < notification_queue_order(b, 0)
    end)
end


local function notification_queue_seen_at(entry, default_value)
    if type(entry) ~= "table" then
        return tonumber(default_value or 0) or 0
    end

    local seen_at = tonumber(entry.queue_seen_at)
    if seen_at ~= nil then
        return seen_at
    end

    seen_at = tonumber(default_value or 0) or 0
    entry.queue_seen_at = seen_at
    return seen_at
end


local function process_ap_notifications()
    local queue = load_json_array(AP_NOTIFICATION_FILE)
    if #queue == 0 then
        return
    end

    sort_notification_queue(queue)

    local now = Ext.Utils.MonotonicTime()
    local next_sequence = tonumber(runtime.notification_next_sort_sequence)
    if next_sequence == nil then
        for _, entry in ipairs(queue) do
            local sequence = notification_queue_sort_sequence(entry)
            if sequence ~= nil then
                next_sequence = sequence
                break
            end
        end
    end

    local ready = {}
    local remaining = {}
    for _, entry in ipairs(queue) do
        local sequence = notification_queue_sort_sequence(entry)
        if sequence == nil or next_sequence == nil then
            table.insert(ready, entry)
        elseif sequence < next_sequence then
            table.insert(ready, entry)
        elseif sequence == next_sequence then
            table.insert(ready, entry)
            next_sequence = next_sequence + 1
        else
            local seen_at = notification_queue_seen_at(entry, now)
            if now - seen_at >= AP_NOTIFICATION_REORDER_GRACE_MS then
                table.insert(ready, entry)
                next_sequence = sequence + 1
            else
                table.insert(remaining, entry)
            end
        end
    end

    runtime.notification_next_sort_sequence = next_sequence

    for _, entry in ipairs(ready) do
        notify_player(entry)
    end

    save_json_array(AP_NOTIFICATION_FILE, remaining)
end


local function get_state()
    local state = PersistentVars.ArchipelagoTrialsCompat or {}
    PersistentVars.ArchipelagoTrialsCompat = state
    state.received_items = state.received_items or {}
    state.granted_unlocks = state.granted_unlocks or {}
    state.shop_unlocks = state.shop_unlocks or {}
    state.progressive_tadpole_unlock_entry = tostring(state.progressive_tadpole_unlock_entry or "")
    if state.goal_completed == nil then
        state.goal_completed = false
    end
    if state.deathlink_suppress_local == nil then
        state.deathlink_suppress_local = false
    end
    state.scenario_clears = tonumber(state.scenario_clears or 0)
    state.perfect_clears = tonumber(state.perfect_clears or 0)
    state.kills = tonumber(state.kills or 0)
    state.deathlink_out_counter = tonumber(state.deathlink_out_counter or 0)
    state.deathlink_suppress_local = state.deathlink_suppress_local == true
    state.shop_fragments_received = tonumber(state.shop_fragments_received or 0) or 0
    state.seed_name = tostring(state.seed_name or "")
    return state
end


local function get_options()
    local options = load_json_object(AP_OPTIONS_FILE)
    options.clear_thresholds = options.clear_thresholds or {}
    options.kill_thresholds = options.kill_thresholds or {}
    options.perfect_thresholds = options.perfect_thresholds or {}
    options.roguescore_thresholds = options.roguescore_thresholds or {}
    options.shop_check_unlock_ids = options.shop_check_unlock_ids or {}
    options.shop_check_costs = options.shop_check_costs or {}
    options.shop_display = options.shop_display or {}
    options.shop_section_indices = options.shop_section_indices or {}
    options.shop_section_names = options.shop_section_names or {}
    options.active_connection = options.active_connection == true
    options.progressive_shop = options.progressive_shop == true or tonumber(options.progressive_shop or 0) == 1
    options.progressive_shop_unlock_rate = tonumber(options.progressive_shop_unlock_rate or 0) or 0
    options.shop_fragment_count = tonumber(options.shop_fragment_count or 0) or 0
    options.death_link = options.death_link == true or tonumber(options.death_link or 0) == 1
    options.death_link_trigger = tonumber(options.death_link_trigger or DEATHLINK_TRIGGER_FULL_PARTY_WIPE)
    options.death_link_punishment =
        tonumber(options.death_link_punishment or DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS)
            or DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS
    options.goal = tonumber(options.goal or GOAL_BUY_NG_PLUS)
    options.goal_clear_target = tonumber(options.goal_clear_target or 0)
    options.goal_rogue_score_target = tonumber(options.goal_rogue_score_target or 0)
    options.goal_ng_plus_fragment_gate_percent = tonumber(options.goal_ng_plus_fragment_gate_percent or 0) or 0
    options.effective_goal_ng_plus_fragment_gate_percent =
        tonumber(options.effective_goal_ng_plus_fragment_gate_percent or 0) or 0
    options.effective_goal_ng_plus_fragment_gate_fragments =
        tonumber(options.effective_goal_ng_plus_fragment_gate_fragments or 0) or 0
    options.vanilla_pixie_blessing_in_shop = options.vanilla_pixie_blessing_in_shop == true
        or tonumber(options.vanilla_pixie_blessing_in_shop or 0) == 1
    options.permanent_buff_target = tonumber(options.permanent_buff_target or PERMANENT_BUFF_TARGET_RANDOM_PARTY_MEMBER)
    options.unlock_classifications_by_id = options.unlock_classifications_by_id or {}
    options.goal_unlock_template_id = tostring(
        options.goal_unlock_template_id or DEFAULT_GOAL_UNLOCK_TEMPLATE_ID
    )
    options.goal_unlock_cost = tonumber(options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST)
        or DEFAULT_GOAL_UNLOCK_COST
    local configured_goal_unlock_id = tostring(options.goal_unlock_id or "")
    if configured_goal_unlock_id == ""
        or configured_goal_unlock_id == options.goal_unlock_template_id
    then
        options.goal_unlock_id = AP_GOAL_UNLOCK_ID
    else
        options.goal_unlock_id = configured_goal_unlock_id
    end
    return options
end


local function is_ap_runtime_unlock_id(unlock_id)
    unlock_id = tostring(unlock_id or "")
    return unlock_id == AP_GOAL_UNLOCK_ID
        or unlock_id == AP_PIXIE_BLESSING_UNLOCK_ID
        or string.match(unlock_id, "^APSHOP::SECTION::") ~= nil
        or string.match(unlock_id, "^APCHECK::") ~= nil
end


local function reset_ap_runtime_unlock_state()
    for _, unlock in ipairs(PersistentVars.Unlocks or {}) do
        if is_ap_runtime_unlock_id(unlock.Id) then
            unlock.Bought = 0
            unlock.BoughtBy = {}
            unlock.Unlocked = false
        end
    end
end


-- The slot data the AP client writes is our entire source of truth for a run.
-- When the seed changes we wipe the AP-only runtime state so old check tokens do not bleed into the new seed.
local function refresh_seed_state()
    local options = get_options()
    if not options.active_connection then
        return false
    end
    local seed_name = tostring(options.seed_name or "")
    if seed_name == "" then
        return false
    end

    local state = get_state()
    if state.seed_name == seed_name then
        return false
    end

    state.seed_name = seed_name
    state.scenario_clears = 0
    state.perfect_clears = 0
    state.kills = 0
    state.received_items = {}
    state.granted_unlocks = {}
    state.shop_unlocks = {}
    state.shop_fragments_received = 0
    state.progressive_tadpole_unlock_entry = ""
    state.goal_completed = false
    state.deathlink_out_counter = 0
    state.deathlink_suppress_local = false
    runtime.granted_unlock_session_init = {}
    runtime.deathlink_party_wipe_active = false
    runtime.logged_unhandled_received = {}
    reset_ap_runtime_unlock_state()
    save_json_array(AP_OUT_FILE, {})
    save_json_array(AP_DEATHLINK_IN_FILE, {})
    save_json_array(AP_DEATHLINK_OUT_FILE, {})
    clear_pending_received()
    clear_pending_shop_unlocks()
    runtime.notification_next_sort_sequence = nil
    return true
end


-- This replaced the old "append if missing" code from the standalone bridge.
-- Same job, just now every ToT progression token goes through one gate.
local function append_unique_token(token)
    local options = get_options()
    if not options.active_connection or tostring(options.seed_name or "") == "" then
        return false
    end
    refresh_seed_state()
    local data = load_json_array(AP_OUT_FILE)
    for _, existing in ipairs(data) do
        if existing == token then
            return false
        end
    end

    table.insert(data, token)
    save_json_array(AP_OUT_FILE, data)
    return true
end


local function rebuild_progress_tokens()
    save_json_array(AP_OUT_FILE, {})
    local options = get_options()
    if not options.active_connection or tostring(options.seed_name or "") == "" then
        return
    end

    refresh_seed_state()
    local state = get_state()

    emit_threshold_tokens("TOT-CLEAR", state.scenario_clears, options.clear_thresholds)
    emit_threshold_tokens("TOT-KILLS", state.kills, options.kill_thresholds)
    emit_threshold_tokens("TOT-PERFECT", state.perfect_clears, options.perfect_thresholds)
    emit_threshold_tokens("TOT-ROGUESCORE", tonumber(PersistentVars.RogueScore or 0), options.roguescore_thresholds)

    state.goal_completed = false
    maybe_emit_goal_token()
end


emit_threshold_tokens = function(prefix, value, thresholds)
    for index, threshold in ipairs(thresholds or {}) do
        if tonumber(value or 0) >= tonumber(threshold or 0) then
            append_unique_token(string.format("%s-%03d", prefix, index))
        end
    end
end


local function find_unlock_by_id(unlock_id, unlocks)
    for _, unlock in ipairs(unlocks or {}) do
        if unlock.Id == unlock_id then
            return unlock
        end
    end
end


local function shop_section_unlock_id(section_index)
    return string.format("%s%03d", AP_SHOP_SECTION_UNLOCK_PREFIX, tonumber(section_index or 0) or 0)
end


local function shop_section_name(section_index, section_count)
    return TL("ha821951agfd74g4c04gb9b1g2a629b930840", tonumber(section_index or 0) or 0, tonumber(section_count or 0) or 0)
end


local function current_shop_fragments_received()
    refresh_seed_state()
    local state = get_state()
    local options = get_options()
    local max_fragments = tonumber(options.shop_fragment_count or 0) or 0
    local received = tonumber(state.shop_fragments_received or 0) or 0
    if max_fragments > 0 then
        received = math.max(0, math.min(received, max_fragments))
    else
        received = 0
    end
    state.shop_fragments_received = received
    return received
end


local function current_roguescore()
    return tonumber(PersistentVars.RogueScore or 0)
end


local function is_deathlink_active()
    local options = get_options()
    return options.active_connection and options.death_link and tostring(options.seed_name or "") ~= ""
end


local function get_active_party_members()
    local members = {}
    local seen = {}

    local function append_member(character)
        character = tostring(character or "")
        if character == "" or seen[character] then
            return
        end
        if Osi.IsCharacter(character) ~= 1 then
            return
        end
        if not GC.IsPlayable(character) then
            return
        end
        if Osi.CanJoinCombat(character) ~= 1 then
            return
        end

        seen[character] = true
        table.insert(members, character)
    end

    for _, character in ipairs(GU.DB.GetPlayers() or {}) do
        append_member(character)
    end

    if #members == 0 then
        for _, character in ipairs(GU.DB.GetAvatars() or {}) do
            append_member(character)
        end
    end

    return members
end


local function is_character_downed(character)
    if character == nil or character == "" or Osi.IsCharacter(character) ~= 1 then
        return false
    end

    local entity = Ext.Entity.Get(character)
    if entity and entity.Downed ~= nil then
        return true
    end

    return Osi.HasActiveStatus(character, "DOWNED") == 1 or Osi.HasActiveStatus(character, "DYING") == 1
end


local function is_character_incapacitated(character)
    return Osi.IsDead(character) == 1 or is_character_downed(character)
end


local function is_party_wiped()
    local party_members = get_active_party_members()
    if #party_members == 0 then
        return false
    end

    for _, character in ipairs(party_members) do
        if not is_character_incapacitated(character) then
            return false
        end
    end

    return true
end


local function update_party_wipe_state()
    runtime.deathlink_party_wipe_active = is_party_wiped()
    return runtime.deathlink_party_wipe_active
end


local function is_core_party_member(character)
    local party_members = GU.DB.GetPlayers() or {}
    if #party_members == 0 then
        party_members = GU.DB.GetAvatars() or {}
    end

    for _, party_member in ipairs(party_members) do
        if tostring(party_member or "") == character then
            return true
        end
    end

    return false
end


local function should_track_deathlink_character(character)
    character = tostring(character or "")
    if character == "" or Osi.IsCharacter(character) ~= 1 then
        return false
    end
    if not GC.IsPlayable(character) then
        return false
    end
    if not is_core_party_member(character) then
        return false
    end

    return Osi.CanJoinCombat(character) == 1 or is_character_incapacitated(character)
end


local function queue_outgoing_deathlink(text)
    if not is_deathlink_active() then
        return false
    end

    refresh_seed_state()
    local state = get_state()
    if state.deathlink_suppress_local then
        return false
    end

    local queue = load_json_array(AP_DEATHLINK_OUT_FILE)
    state.deathlink_out_counter = state.deathlink_out_counter + 1
    table.insert(queue, {
        id = state.deathlink_out_counter,
        text = tostring(text or "suffered a Trials defeat."),
        seed_name = tostring(get_options().seed_name or ""),
    })
    save_json_array(AP_DEATHLINK_OUT_FILE, queue)
    return true
end


local function maybe_queue_party_wipe_deathlink()
    if not is_deathlink_active() then
        return false
    end

    if runtime.deathlink_party_wipe_active then
        return false
    end

    if not is_party_wiped() then
        runtime.deathlink_party_wipe_active = false
        return false
    end

    runtime.deathlink_party_wipe_active = true
    return queue_outgoing_deathlink("suffered a full party wipe in Trials of Tav.")
end


local function get_deathlink_wipe_targets()
    if trap_rewards and type(trap_rewards.collect_targets) == "function" then
        local ok, targets = pcall(trap_rewards.collect_targets, nil, {
            get_active_party_members = get_active_party_members,
        })
        if ok and type(targets) == "table" and #targets > 0 then
            return targets
        end
        if not ok then
            L.Error("ArchipelagoTrialsCompat/DeathLinkTargets", targets)
        end
    end

    return get_active_party_members()
end


local function entity_handle_uuid(entity_handle)
    if not Ext or not Ext.Entity or entity_handle == nil then
        return ""
    end

    local entity = Ext.Entity.Get(entity_handle)
    if not entity or not entity.Uuid or not entity.Uuid.EntityUuid then
        return ""
    end

    return tostring(entity.Uuid.EntityUuid or "")
end


local function append_unique_deathlink_target(targets, seen, character)
    character = tostring(character or "")
    if character == "" or seen[character] then
        return
    end
    if Osi.IsCharacter(character) ~= 1 then
        return
    end
    if Osi.CanJoinCombat(character) ~= 1 then
        return
    end

    seen[character] = true
    table.insert(targets, character)
end


local function get_deathlink_party_targets()
    local targets = {}
    local seen = {}
    local owner_lookup = {}

    for _, character in ipairs(get_active_party_members()) do
        append_unique_deathlink_target(targets, seen, character)
        owner_lookup[character] = true
    end

    if Ext and Ext.Entity then
        for _, follower_handle in ipairs(Ext.Entity.GetAllEntitiesWithComponent("PartyFollower") or {}) do
            local follower_entity = Ext.Entity.Get(follower_handle)
            local party_follower = follower_entity and follower_entity.PartyFollower
            local followed_uuid = entity_handle_uuid(party_follower and party_follower.Following)
            if followed_uuid ~= "" and owner_lookup[followed_uuid] then
                append_unique_deathlink_target(targets, seen, entity_handle_uuid(follower_handle))
            end
        end
    end

    return targets
end


local function deathlink_notify(event, text)
    local source = tostring(event and event.source or "")
    if source ~= "" then
        Player.Notify(TL("h2357ca60g7602g49f3g9106g4f9533246db7", source, tostring(text or "")), true)
    else
        Player.Notify(TL("h5ef2b860g0ba7g4ed3g96dcg18b534fe3a97", tostring(text or "")), true)
    end
end


local function deathlink_character_name(character)
    if type(Player) == "table" and type(Player.DisplayName) == "function" then
        local ok, name = pcall(Player.DisplayName, character)
        if ok and type(name) == "string" and name ~= "" then
            return name
        end
    end

    return TL("h1ac9f6beg4f9cg4a3egb29fgac58d0bd8e7a")
end


local function temporarily_suppress_outgoing_deathlink(reset_delay_ms)
    local state = get_state()
    state.deathlink_suppress_local = true
    Defer(tonumber(reset_delay_ms or 1500) or 1500, function()
        local refreshed_state = get_state()
        refreshed_state.deathlink_suppress_local = false
        update_party_wipe_state()
    end)
end


local function choose_random_character(characters)
    if type(characters) ~= "table" or #characters == 0 then
        return ""
    end

    return tostring(characters[math.random(#characters)] or "")
end


local function filter_deathlink_targets(characters, predicate)
    local filtered = {}
    for _, character in ipairs(characters or {}) do
        if predicate(character) then
            table.insert(filtered, character)
        end
    end
    return filtered
end


local function kill_character_for_deathlink(character)
    character = tostring(character or "")
    if character == "" or Osi.IsDead(character) == 1 then
        return false
    end

    Osi.Die(character, 0, C.NullGuid, 0, 0)
    return true
end


local function down_character_for_deathlink(character)
    character = tostring(character or "")
    if character == "" or Osi.IsDead(character) == 1 or is_character_downed(character) then
        return false
    end

    local entity = Ext.Entity.Get(character)
    if entity and entity.Health then
        entity.Health.Hp = 0
        entity:Replicate("Health")
    end

    pcall(function()
        Osi.ApplyStatus(character, "DOWNED", -1, 1)
    end)

    if not is_character_downed(character) and Osi.SetHitpointsPercentage then
        pcall(function()
            Osi.SetHitpointsPercentage(character, 0)
        end)
    end

    return is_character_downed(character) or Osi.IsDead(character) == 1
end


local function action_resource_static_name(resource)
    if not Ext or not Ext.StaticData or resource == nil then
        return ""
    end

    local resource_uuid = tostring(resource.ResourceUUID or "")
    if resource_uuid == "" then
        return ""
    end

    local ok, definition = pcall(Ext.StaticData.Get, resource_uuid, "ActionResource")
    if not ok or definition == nil then
        return ""
    end

    return tostring(definition.Name or "")
end


local function normalized_action_resource_name(resource)
    local name = action_resource_static_name(resource)
    if name == "" then
        return ""
    end

    return string.lower((tostring(name):gsub("[%s_%-]", "")))
end


local function should_clear_turn_action_resource(resource)
    local normalized_name = normalized_action_resource_name(resource)
    if normalized_name == "" then
        return false
    end

    if string.find(normalized_name, "reaction", 1, true) then
        return false
    end

    if normalized_name == "actionpoint" then
        return true
    end
    if string.find(normalized_name, "bonusaction", 1, true) then
        return true
    end
    if string.find(normalized_name, "movement", 1, true) then
        return true
    end
    if string.find(normalized_name, "actionpoint", 1, true)
        and not string.find(normalized_name, "spellslot", 1, true)
    then
        return true
    end

    return false
end


local function clear_character_resources(character, should_clear_resource)
    character = tostring(character or "")
    if character == "" or Osi.IsCharacter(character) ~= 1 or Osi.IsDead(character) == 1 then
        return false
    end

    local entity = Ext.Entity.Get(character)
    local action_resources = entity and entity.ActionResources
    local resources = action_resources and action_resources.Resources
    if not resources then
        return false
    end

    local changed = false
    for _resource_uuid, list in pairs(resources) do
        for _, resource in pairs(list or {}) do
            if should_clear_resource == nil or should_clear_resource(resource) then
                local amount = tonumber(resource and resource.Amount or 0) or 0
                if amount ~= 0 then
                    resource.Amount = 0
                    changed = true
                end
            end
        end
    end

    if changed then
        entity:Replicate("ActionResources")
    end

    return changed
end


local function clear_character_all_resources(character)
    return clear_character_resources(character, nil)
end


local function clear_character_turn_actions(character)
    return clear_character_resources(character, should_clear_turn_action_resource)
end


local function clear_party_targets(characters, clear_character_fn)
    local changed_any = false
    for _, character in ipairs(characters or {}) do
        if clear_character_fn(character) then
            changed_any = true
        end
    end
    return changed_any
end


local function apply_deathlink_punishment(event)
    local options = get_options()
    local punishment = tonumber(options.death_link_punishment or DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS)
        or DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS

    if punishment == DEATHLINK_PUNISHMENT_NOTHING then
        deathlink_notify(event, TL("he39e5114gb6cbg4044g9d0agd6227f28f400"))
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_KILL_ALL_PARTY_MEMBERS then
        local state = get_state()
        state.deathlink_suppress_local = true

        local wipe_targets = get_deathlink_wipe_targets()
        for _, character in ipairs(wipe_targets) do
            kill_character_for_deathlink(character)
        end

        runtime.deathlink_party_wipe_active = true
        deathlink_notify(event, TL("h2dee447fg78bbg4112ga1edgd774c3cff556"))
        return
    end

    local party_targets = get_deathlink_party_targets()
    if punishment == DEATHLINK_PUNISHMENT_DOWN_RANDOM_PARTY_MEMBER then
        local eligible_targets = filter_deathlink_targets(party_targets, function(character)
            return Osi.IsDead(character) ~= 1 and not is_character_downed(character)
        end)
        local target = choose_random_character(eligible_targets)
        if target == "" then
            deathlink_notify(event, TL("hd4915f9fg81c4g40acgae7ag26cacc5804e8"))
            return
        end

        temporarily_suppress_outgoing_deathlink(1500)
        if down_character_for_deathlink(target) then
            deathlink_notify(event, TL("h280c6000g7d59g4355g91b3gf5333391d711", deathlink_character_name(target)))
        else
            deathlink_notify(event, TL("hd4915f9fg81c4g40acgae7ag26cacc5804e8"))
        end
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_KILL_RANDOM_PARTY_MEMBER then
        local eligible_targets = filter_deathlink_targets(party_targets, function(character)
            return Osi.IsDead(character) ~= 1
        end)
        local target = choose_random_character(eligible_targets)
        if target == "" then
            deathlink_notify(event, TL("hd4f28583g81a7g4d0dgae7cg1b6b0c5e3949"))
            return
        end

        temporarily_suppress_outgoing_deathlink(1500)
        if kill_character_for_deathlink(target) then
            deathlink_notify(event, TL("h2bfee70cg7eabg4b25g918cgdd43f3aeff61", deathlink_character_name(target)))
        else
            deathlink_notify(event, TL("hd4f28583g81a7g4d0dgae7cg1b6b0c5e3949"))
        end
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_REMOVE_ALL_RESOURCES_ALL then
        local drained_any = clear_party_targets(
            filter_deathlink_targets(party_targets, function(target)
                return Osi.IsDead(target) ~= 1
            end),
            clear_character_all_resources
        )

        if drained_any then
            deathlink_notify(
                event,
                TL("hf3cf4f3dga69ag41a6g8c0fgc7c0ee2de5e2")
            )
        else
            deathlink_notify(event, TL("h1dd9331fg488cg4664ga2eega002c0cc8220"))
        end
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_REMOVE_ALL_RESOURCES_RANDOM then
        local eligible_targets = filter_deathlink_targets(party_targets, function(character)
            return Osi.IsDead(character) ~= 1
        end)
        local target = choose_random_character(eligible_targets)
        if target == "" then
            deathlink_notify(event, TL("hd7151d29g8240g4487g8e42g62e1ac6040c3"))
            return
        end

        if clear_character_all_resources(target) then
            deathlink_notify(
                event,
                TL("h202fd298g757ag487cg9131gce1ab313ec38", deathlink_character_name(target))
            )
        else
            deathlink_notify(event, TL("h1dd9331fg488cg4664ga2eega002c0cc8220"))
        end
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_REMOVE_ALL_ACTIONS_ALL then
        local removed_any = clear_party_targets(
            filter_deathlink_targets(party_targets, function(target)
                return Osi.IsDead(target) ~= 1
            end),
            clear_character_turn_actions
        )

        if removed_any then
            deathlink_notify(event, TL("hc25d3ccfg9708g4699gaf16ge0ffcd34c2dd"))
        else
            deathlink_notify(event, TL("h4ffd5884g1aa8g40ddg97ccge6bb75eec499"))
        end
        return
    end

    if punishment == DEATHLINK_PUNISHMENT_REMOVE_ALL_ACTIONS_RANDOM then
        local eligible_targets = filter_deathlink_targets(party_targets, function(character)
            return Osi.IsDead(character) ~= 1
        end)
        local target = choose_random_character(eligible_targets)
        if target == "" then
            deathlink_notify(event, TL("h7033ee56g2566g4bb0gb430g0dd656122ff4"))
            return
        end

        if clear_character_turn_actions(target) then
            deathlink_notify(
                event,
                TL("h03b97a13g56ecg42f4ga308ga492012a86b0", deathlink_character_name(target))
            )
        else
            deathlink_notify(event, TL("h4ffd5884g1aa8g40ddg97ccge6bb75eec499"))
        end
        return
    end

    deathlink_notify(event, TL("he39e5114gb6cbg4044g9d0agd6227f28f400"))
end


local function process_incoming_deathlinks()
    if not is_deathlink_active() then
        return
    end

    refresh_seed_state()
    local queue = load_json_array(AP_DEATHLINK_IN_FILE)
    if #queue == 0 then
        return
    end

    apply_deathlink_punishment(queue[#queue])
    save_json_array(AP_DEATHLINK_IN_FILE, {})
end


local function on_deathlink_character_died(character)
    if not should_track_deathlink_character(character) then
        return
    end

    local options = get_options()
    if options.death_link_trigger == DEATHLINK_TRIGGER_ANY_PARTY_KILL then
        queue_outgoing_deathlink("lost a party member in Trials of Tav.")
    elseif options.death_link_trigger == DEATHLINK_TRIGGER_FULL_PARTY_WIPE then
        maybe_queue_party_wipe_deathlink()
    end
end


local function on_deathlink_character_downed(character, is_downed)
    if not should_track_deathlink_character(character) then
        return
    end

    local is_now_downed = is_downed == true
        or tonumber(is_downed or 0) == 1
        or tostring(is_downed or "") == "1"
    if not is_now_downed then
        update_party_wipe_state()
        return
    end

    local options = get_options()
    if options.death_link_trigger == DEATHLINK_TRIGGER_ANY_PARTY_DOWNED then
        queue_outgoing_deathlink("had a party member downed in Trials of Tav.")
    elseif options.death_link_trigger == DEATHLINK_TRIGGER_FULL_PARTY_WIPE then
        maybe_queue_party_wipe_deathlink()
    end
end


maybe_emit_goal_token = function()
    refresh_seed_state()
    local state = get_state()
    if state.goal_completed then
        return
    end

    local options = get_options()
    local complete = false

    if options.goal == GOAL_BUY_NG_PLUS then
        local unlock = find_unlock_by_id(options.goal_unlock_id, Unlock.Get())
        complete = unlock ~= nil and tonumber(unlock.Bought or 0) > 0
    elseif options.goal == GOAL_CLEAR_STAGES then
        complete = state.scenario_clears >= options.goal_clear_target
    elseif options.goal == GOAL_REACH_ROGUESCORE then
        complete = current_roguescore() >= options.goal_rogue_score_target
    end

    if complete then
        state.goal_completed = true
        append_unique_token("TOT-GOAL-001")
    end
end


local function record_roguescore(score)
    emit_threshold_tokens("TOT-ROGUESCORE", tonumber(score or 0), get_options().roguescore_thresholds)
    maybe_emit_goal_token()
end


local function extract_character_uuid(character)
    if not character or character == "" then
        return ""
    end

    local ok, extracted = pcall(U.UUID.Extract, character)
    if ok and extracted and extracted ~= "" then
        return extracted
    end

    return character
end


local function is_valid_reward_character(character)
    character = extract_character_uuid(character)
    if character == "" then
        return false, ""
    end
    if Osi.IsCharacter(character) ~= 1 then
        return false, ""
    end
    if not GU.Character.IsPlayable(character) then
        return false, ""
    end
    return true, character
end


local function first_valid_reward_character(characters)
    for _, character in ipairs(characters or {}) do
        local ok, normalized = is_valid_reward_character(character)
        if ok then
            return normalized
        end
    end
    return ""
end


local function resolve_reward_character(preferred_character)
    local ok, normalized = is_valid_reward_character(preferred_character)
    if ok then
        return normalized
    end

    local avatar = first_valid_reward_character(GU.DB.GetAvatars())
    if avatar ~= "" then
        return avatar
    end

    local player = first_valid_reward_character(GU.DB.GetPlayers())
    if player ~= "" then
        return player
    end

    local host_ok, host_character = pcall(Player.Host)
    if host_ok then
        local host_valid, host_normalized = is_valid_reward_character(host_character)
        if host_valid then
            return host_normalized
        end
    end

    return ""
end


local function append_reward_target(targets, seen, character)
    local ok, normalized = is_valid_reward_character(character)
    if not ok or seen[normalized] then
        return
    end

    seen[normalized] = true
    table.insert(targets, normalized)
end


local function collect_reward_party_members(preferred_character)
    local targets = {}
    local seen = {}

    for _, character in ipairs(get_active_party_members()) do
        append_reward_target(targets, seen, character)
    end

    local preferred = resolve_reward_character(preferred_character)
    if preferred ~= "" then
        append_reward_target(targets, seen, preferred)
    end

    return targets
end


local function determine_unlock_reward_targets(unlock_id, template, preferred_character)
    local fallback_character = resolve_reward_character(preferred_character)
    if fallback_character == "" then
        return {}
    end

    local options = get_options()
    local classification = tostring(table_get(options.unlock_classifications_by_id, unlock_id, ""))
    local excluded_useful_unlocks = {
        BuyLootRare = true,
        BuyLootEpic = true,
        BuyLootLegendary = true,
    }

    if classification == "progression" then
        if template.Character then
            local targets = collect_reward_party_members(preferred_character)
            if #targets > 0 then
                return targets
            end
        end
        return { fallback_character }
    end

    if classification ~= "useful"
        or excluded_useful_unlocks[unlock_id]
        or template.Character ~= true
    then
        return { fallback_character }
    end

    if options.permanent_buff_target == PERMANENT_BUFF_TARGET_ALL_PARTY_MEMBERS then
        local targets = collect_reward_party_members(preferred_character)
        if #targets > 0 then
            return targets
        end
        return { fallback_character }
    end

    if options.permanent_buff_target == PERMANENT_BUFF_TARGET_RANDOM_PARTY_MEMBER then
        local targets = collect_reward_party_members(preferred_character)
        if #targets > 0 then
            return { targets[math.random(#targets)] }
        end
    end

    return { fallback_character }
end


local function capture_original_unlock_templates()
    if runtime.original_templates_captured then
        return
    end

    -- This used to be the hand-off point between the old standalone bridge and CombatMod.
    -- We grab the real ToT templates once up front so AP rewards can still call the original unlock behavior later.
    for _, template in ipairs(Templates.GetUnlocks() or {}) do
        local copy = shallow_copy(template)
        runtime.original_templates_by_id[copy.Id] = copy
    end
    runtime.original_templates_captured = true
end


local function get_granted_unlock_record(unlock_id)
    local state = get_state()
    local record = state.granted_unlocks[unlock_id]
    if not record then
        record = {
            Bought = 0,
            BoughtBy = {},
        }
        state.granted_unlocks[unlock_id] = record
    end
    record.Bought = tonumber(record.Bought or 0)
    record.BoughtBy = record.BoughtBy or {}
    return record
end


local function get_shop_unlock_record(unlock_id)
    local state = get_state()
    local record = state.shop_unlocks[unlock_id]
    if not record then
        record = {
            Bought = 0,
            BoughtBy = {},
        }
        state.shop_unlocks[unlock_id] = record
    end
    record.Bought = tonumber(record.Bought or 0)
    record.BoughtBy = record.BoughtBy or {}
    return record
end


local function merge_shop_unlock_record(target_record, source_record)
    target_record.Bought = math.max(
        tonumber(target_record.Bought or 0) or 0,
        tonumber(table_get(source_record, "Bought", 0) or 0) or 0
    )
    target_record.BoughtBy = target_record.BoughtBy or {}
    for uuid, bought in pairs(table_get(source_record, "BoughtBy", {}) or {}) do
        if bought then
            target_record.BoughtBy[uuid] = true
        end
    end
end


local function reapply_pending_shop_unlocks()
    if next(runtime.pending_shop_unlock_replay or {}) == nil then
        return
    end

    for unlock_id, replay_record in pairs(runtime.pending_shop_unlock_replay) do
        local saved_record = get_shop_unlock_record(unlock_id)
        merge_shop_unlock_record(saved_record, replay_record)
    end
end


local function build_granted_unlock(unlock_id)
    capture_original_unlock_templates()
    local template = runtime.original_templates_by_id[unlock_id]
    if not template then
        return nil
    end

    local record = get_granted_unlock_record(unlock_id)
    local unlock = shallow_copy(template)
    unlock.Bought = record.Bought
    unlock.BoughtBy = shallow_copy(record.BoughtBy)
    return Unlock.Restore(unlock)
end


local function ensure_granted_unlock_initialized(unlock_id, unlock)
    if runtime.granted_unlock_session_init[unlock_id] then
        return
    end

    if unlock.OnInit then
        pcall(unlock.OnInit, unlock)
    end
    runtime.granted_unlock_session_init[unlock_id] = true
end


local function reapply_granted_unlocks()
    for unlock_id, _record in pairs(get_state().granted_unlocks) do
        local unlock = build_granted_unlock(unlock_id)
        if unlock then
            ensure_granted_unlock_initialized(unlock_id, unlock)
            if unlock.OnReapply then
                pcall(unlock.OnReapply, unlock)
            end
        end
    end
end


local function grant_unlock_reward(unlock_id, preferred_character)
    local prerequisite_unlock_by_id = {
        ExpMultiplier = "MOD_BOOSTS",
        LootMultiplier = "MOD_BOOSTS",
        CurrencyMultiplier = "MOD_BOOSTS",
    }
    local prerequisite_unlock_id = prerequisite_unlock_by_id[unlock_id]
    if prerequisite_unlock_id and not get_state().granted_unlocks[prerequisite_unlock_id] then
        if not grant_unlock_reward(prerequisite_unlock_id, preferred_character) then
            return false
        end
    end

    capture_original_unlock_templates()
    local template = runtime.original_templates_by_id[unlock_id]
    if not template then
        return false
    end

    local targets = determine_unlock_reward_targets(unlock_id, template, preferred_character)
    if #targets == 0 then
        return false
    end

    local unlock = build_granted_unlock(unlock_id)
    if not unlock then
        return false
    end

    ensure_granted_unlock_initialized(unlock_id, unlock)
    local granted = false
    for _, character in ipairs(targets) do
        local ok, err = pcall(function()
            unlock:Buy(character)
        end)
        if not ok then
            L.Error("ArchipelagoTrialsCompat/GrantUnlock", unlock_id, character, err)
        else
            granted = true
        end
    end
    if not granted then
        return false
    end

    if unlock.OnReapply then
        pcall(unlock.OnReapply, unlock)
    end

    local record = get_granted_unlock_record(unlock_id)
    record.Bought = tonumber(unlock.Bought or 0)
    record.BoughtBy = shallow_copy(unlock.BoughtBy or {})
    maybe_emit_goal_token()
    return true
end


local function grant_trials_filler(kind, amount)
    amount = tonumber(amount or 0)
    if amount <= 0 then
        return false
    end

    if kind == "Currency" then
        Unlock.UpdateCurrency((tonumber(PersistentVars.Currency) or 0) + amount)
        return true
    end

    if kind == "RogueScore" then
        GameMode.UpdateRogueScore(current_roguescore() + amount)
        record_roguescore(current_roguescore())
        return true
    end

    if kind == "Experience" then
        Player.GiveExperience(amount)
        return true
    end

    return false
end


local function extract_template_reward_id(entry)
    entry = tostring(entry or "")
    local duplicated_template = string.match(entry, "^Dupe%-%d+%-(.+)$")
    if duplicated_template and string.match(duplicated_template, "^%x+%-%x+%-%x+%-%x+%-%x+$") then
        return duplicated_template
    end
    if string.match(entry, "^%x+%-%x+%-%x+%-%x+%-%x+$") then
        return entry
    end
    return ""
end


local function grant_template_item_reward(entry, preferred_character)
    local template_id = extract_template_reward_id(entry)
    if template_id == "" then
        return false
    end

    local character = resolve_reward_character(preferred_character)
    if character == "" or not Osi or not Osi.TemplateAddTo then
        return false
    end

    -- The old AP bridge used to hand raw BG3 template rewards to the party here.
    -- Shop item checks still write those same UUID payloads, so the merged runtime
    -- needs to add them back into inventory instead of only handling unlock strings.
    local ok, err = pcall(function()
        Osi.TemplateAddTo(template_id, character, 1, 1)
    end)
    if not ok then
        L.Error("ArchipelagoTrialsCompat/GrantTemplateItem", template_id, err)
        return false
    end
    return true
end


local function grant_legacy_currency_reward(entry)
    local amount = tonumber(string.match(tostring(entry or ""), "^Gold%-(%d+)"))
    if not amount or amount <= 0 then
        return false
    end

    Unlock.UpdateCurrency((tonumber(PersistentVars.Currency) or 0) + amount)
    return true
end


local function grant_trap_reward(entry, preferred_character)
    if not trap_rewards or type(trap_rewards.try_grant) ~= "function" then
        return false
    end

    return trap_rewards.try_grant(entry, preferred_character, {
        extract_character_uuid = extract_character_uuid,
        get_active_party_members = get_active_party_members,
        resolve_reward_character = resolve_reward_character,
        logger = L,
    })
end


local function grant_progressive_tadpole_reward(entry, preferred_character)
    local state = get_state()
    local unlock_entry = tostring(state.progressive_tadpole_unlock_entry or "")
    local unlock_granted = state.granted_unlocks["UnlockTadpole"] ~= nil

    if unlock_granted then
        if unlock_entry == entry then
            return true
        end
        return grant_unlock_reward("Tadpole", preferred_character)
    end

    if unlock_entry ~= "" and unlock_entry ~= entry then
        return false
    end

    state.progressive_tadpole_unlock_entry = entry
    if grant_unlock_reward("UnlockTadpole", preferred_character) then
        return true
    end

    if unlock_entry == "" then
        state.progressive_tadpole_unlock_entry = ""
    end
    return false
end


local function grant_shop_fragment_reward()
    local options = get_options()
    local max_fragments = tonumber(options.shop_fragment_count or 0) or 0
    if max_fragments <= 0 then
        return true
    end

    refresh_seed_state()
    local state = get_state()
    local received = tonumber(state.shop_fragments_received or 0) or 0
    if received >= max_fragments then
        return true
    end

    state.shop_fragments_received = received + 1
    Unlock.Sync()
    write_shop_debug_snapshot("grant_shop_fragment_reward", Unlock.Get())
    return true
end


-- This used to be split across the old Archipelago mod and the separate ToT bridge.
-- Now it is the single inbox processor for Trials rewards, filler payouts, and the "replay after reload" safety net.
local function process_trials_inbox(preferred_character)
    local options = get_options()
    if not options.active_connection or tostring(options.seed_name or "") == "" then
        return
    end

    refresh_seed_state()
    local state = get_state()
    local inbox = load_json_array(AP_IN_FILE)

    if #inbox > 0 then
        for _, entry in ipairs(inbox) do
            local should_replay = runtime.pending_received_replay[entry] == true
            if should_replay or not state.received_items[entry] then
                local granted = false
                if string.sub(entry, 1, 10) == "ToTUnlock:" then
                    local unlock_id = string.match(entry, "^ToTUnlock:([^:]+)")
                    if unlock_id then
                        if should_replay
                            and state.granted_unlocks[unlock_id]
                            and not unlock_requires_regrant_on_replay(unlock_id)
                        then
                            granted = true
                        elseif unlock_id == "ShopFragment" then
                            granted = state.received_items[entry] == true or grant_shop_fragment_reward()
                        elseif unlock_id == "Tadpole" and grant_progressive_tadpole_reward(entry, preferred_character) then
                            granted = true
                        elseif grant_unlock_reward(unlock_id, preferred_character) then
                            granted = true
                        end
                    end
                elseif string.sub(entry, 1, 10) == "ToTFiller:" then
                    local kind, amount = string.match(entry, "^ToTFiller:([^:]+):([^:]+)")
                    if kind and amount and grant_trials_filler(kind, amount) then
                        granted = true
                    end
                elseif grant_template_item_reward(entry, preferred_character)
                    or grant_legacy_currency_reward(entry)
                    or grant_trap_reward(entry, preferred_character)
                then
                    granted = true
                end

                if granted then
                    state.received_items[entry] = true
                    remember_pending_received(entry)
                    runtime.pending_received_replay[entry] = nil
                    runtime.logged_unhandled_received[entry] = nil
                elseif runtime.logged_unhandled_received[entry] ~= true then
                    runtime.logged_unhandled_received[entry] = true
                    print("[ArchipelagoTrialsCompat] Unhandled AP reward entry: " .. tostring(entry))
                end
            end
        end
    end

    process_ap_notifications()
end


Net.On("ArchipelagoClientCommand", function(event)
    local payload = event.Payload or {}
    local command = tostring(table_get(payload, "command", "") or "")

    if not event:IsHost() then
        Net.Respond(event, { false, TL("h0c52c96bg5907g49c3ga3f6g1fa581d43d87") })
        return
    end

    if command == "connect" then
        local server_address = trim_archipelago_client_text(table_get(payload, "server_address", ""), 256)
        local slot_name = trim_archipelago_client_text(table_get(payload, "slot_name", ""), 128)
        local password = trim_archipelago_client_text(table_get(payload, "password", ""), 256)

        if server_address == "" then
            Net.Respond(event, { false, TL("hd60a6ce0g835fg439bg9e53g95fd3c71b7df") })
            return
        end
        if slot_name == "" then
            Net.Respond(event, { false, TL("h891683e6gdc43g4d6bgbba2g5b0d5980792f") })
            return
        end

        refresh_archipelago_client_ui(true)
        local backend_running = false
        local backend_stale = true
        if runtime.archipelago_client_ui_state then
            backend_running = runtime.archipelago_client_ui_state.bridge_running == true
            backend_stale = runtime.archipelago_client_ui_state.bridge_stale == true
        end
        if not backend_running or backend_stale then
            local backend_message = archipelago_backend_launch_message()
            if backend_running and backend_stale then
                backend_message = archipelago_backend_relaunch_message()
            end
            maybe_prompt_archipelago_backend(true)
            Net.Respond(event, {
                false,
                backend_message,
            })
            return
        end

        enqueue_archipelago_client_command("connect", {
            server_address = server_address,
            slot_name = slot_name,
            password = password,
        })
        refresh_archipelago_client_ui(true)
        Net.Respond(event, { true, TL("hff9ca69bgaac9g4f3cgaccagf95a8ee8db78") })
        return
    end

    if command == "disconnect" then
        enqueue_archipelago_client_command("disconnect", {})
        Net.Respond(event, { true, TL("h9fe5992cgcab0g4cc7g9acdg6aa1f8ef4883") })
        return
    end

    if command == "resync" then
        enqueue_archipelago_client_command("resync", {})
        Net.Respond(event, { true, TL("h09babe14g5cefg4eb4g93a8g98d2718abaf0") })
        return
    end

    if command == "clear_log" then
        save_json_array(AP_CLIENT_LOG_FILE, {})
        refresh_archipelago_client_ui(true)
        Net.Respond(event, { true, TL("hfdbb4998ga8eeg41ccg9ce8g87aabecaa588") })
        return
    end

    Net.Respond(event, { false, TL("hdbe11c7ag8eb4g4492gbe8dg22f49caf00d6") })
end)


local function shop_check_id(original_id, index)
    return string.format("APCHECK::%03d::%s", index, original_id)
end


local function build_refresh_signature(options)
    return Ext.Json.Stringify({
        active_connection = options.active_connection == true,
        progressive_shop = options.progressive_shop == true,
        progressive_shop_unlock_rate = options.progressive_shop_unlock_rate or 0,
        shop_fragment_count = options.shop_fragment_count or 0,
        goal_ng_plus_fragment_gate_percent = options.goal_ng_plus_fragment_gate_percent or 0,
        effective_goal_ng_plus_fragment_gate_percent = options.effective_goal_ng_plus_fragment_gate_percent or 0,
        effective_goal_ng_plus_fragment_gate_fragments = options.effective_goal_ng_plus_fragment_gate_fragments or 0,
        goal_unlock_id = options.goal_unlock_id or "",
        goal_unlock_template_id = options.goal_unlock_template_id or "",
        goal_unlock_cost = options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST,
        vanilla_pixie_blessing_in_shop = options.vanilla_pixie_blessing_in_shop == true,
        shop_check_unlock_ids = options.shop_check_unlock_ids or {},
        shop_check_costs = options.shop_check_costs or {},
        shop_section_indices = options.shop_section_indices or {},
        shop_section_names = options.shop_section_names or {},
        shop_display = options.shop_display or {},
    })
end


local function sync_connection_state(force)
    local options = get_options()
    local signature = tostring(options.active_connection == true) .. "|" .. tostring(options.seed_name or "")
    if not force and runtime.connection_signature == signature then
        return
    end

    runtime.connection_signature = signature
    rebuild_progress_tokens()
end


local function make_shop_section_unlock(section_index, options)
    local total_sections = tonumber(options.shop_fragment_count or 0) or 0
    local unlocked_sections = current_shop_fragments_received()
    return {
        Id = shop_section_unlock_id(section_index),
        Name = shop_section_name(section_index, total_sections),
        Icon = "ap_trials_icon_color_001",
        Cost = 0,
        Amount = 1,
        Character = false,
        Persistent = false,
        Requirement = nil,
        Bought = unlocked_sections >= section_index and 1 or 0,
        BoughtBy = {},
        HideStock = true,
        OnInit = function() end,
        OnReapply = function() end,
        OnBuy = function() end,
    }
end


local function make_shop_check_unlock(template, index, options)
    local shop_preview = table_get(options.shop_display, index, {})
    local token_index = tonumber(table_get(shop_preview, "token_index", index)) or index
    local section_index = tonumber(table_get(shop_preview, "section_index", 0)) or 0
    local section_name = tostring(table_get(shop_preview, "section_name", ""))
    local unlock = shallow_copy(template)
    unlock.Id = shop_check_id(template.Id, token_index)
    unlock.Name = table_get(shop_preview, "display_name", TL("h1c307686g4965g423dgb2f0g345b50d21679", tostring(template.Name or template.Id)))
    unlock.FallbackIcon = template.Icon
    local randomized_cost = tonumber(table_get(options.shop_check_costs, index, unlock.Cost))
    if randomized_cost ~= nil then
        unlock.Cost = math.max(0, randomized_cost)
    end
    local explicit_icon_key = tostring(table_get(shop_preview, "icon_key", ""))
    local is_local_item = table_get(shop_preview, "is_local_item", nil)
    if is_local_item == true then
        unlock.Icon = "ap_trials_icon_blue_001"
    elseif is_local_item == false then
        unlock.Icon = "ap_trials_icon_color_001"
    elseif explicit_icon_key ~= "" then
        unlock.Icon = explicit_icon_key
    end
    unlock.Description = TL("hc9778f97g9c22g4dacgafa4g4bca4d8669e8")
    if table_get(shop_preview, "item_name", "") ~= "" then
        unlock.Description = TL("he89ab093gbdcfg4e5cgadbag983a0f98ba18", tostring(shop_preview.item_name))
    end
    if table_get(shop_preview, "player_name", "") ~= "" then
        unlock.Description = TL("h28e4e464g7db1g4b13g91bdg7d75739f5f57", unlock.Description, tostring(shop_preview.player_name))
    end
    unlock.Character = false
    unlock.Persistent = false
    unlock.Amount = 1
    local saved_record = get_shop_unlock_record(unlock.Id)
    unlock.Bought = tonumber(saved_record.Bought or 0)
    unlock.BoughtBy = shallow_copy(saved_record.BoughtBy or {})
    unlock.HideStock = true
    unlock.Requirement = nil
    if options.progressive_shop == true and section_index > 0 then
        unlock.Requirement = shop_section_unlock_id(section_index)
    end
    unlock.SectionName = section_name
    unlock.SortSectionIndex = section_index
    unlock.SortSectionOrder = 0
    unlock.SortPlayerName = tostring(table_get(shop_preview, "player_name", ""))
    unlock.SortPrice = tonumber(unlock.Cost or 0) or 0
    unlock.SortItemName = tostring(table_get(shop_preview, "item_name", unlock.Name or ""))
    unlock.SortTokenIndex = token_index
    unlock.OnInit = function() end
    unlock.OnReapply = function() end
    unlock.OnBuy = function(self, _character)
        append_unique_token(string.format("TOT-SHOP-%03d", token_index))
        local saved_purchase = get_shop_unlock_record(self.Id)
        saved_purchase.Bought = tonumber(self.Bought or 0)
        saved_purchase.BoughtBy = shallow_copy(self.BoughtBy or {})
        remember_pending_shop_unlock(self.Id, saved_purchase)
    end
    return unlock
end


local function make_goal_unlock(template, options)
    local unlock = shallow_copy(template)
    unlock.Id = tostring(options.goal_unlock_id or AP_GOAL_UNLOCK_ID)
    unlock.Name = TL("h0fb4243eg5ae1g4716gb3c8g7170d1ea5352")
    unlock.Description = TL("hcdc81710g989dg4424g9fefgb2423dcd9060")
    local configured_cost = tonumber(options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST)
        or DEFAULT_GOAL_UNLOCK_COST
    unlock.Cost = math.max(0, configured_cost)
    unlock.Persistent = false
    unlock.Bought = 0
    unlock.BoughtBy = {}
    unlock.RequiredShopFragments = tonumber(options.effective_goal_ng_plus_fragment_gate_fragments or 0) or 0
    unlock.TotalShopFragments = tonumber(options.shop_fragment_count or 0) or 0
    unlock.Requirement = nil
    if unlock.RequiredShopFragments > 0 then
        unlock.Requirement = shop_section_unlock_id(unlock.RequiredShopFragments)
    end
    unlock.HideStock = true
    unlock.SectionName = TL(AP_LOCAL_SHOP_SECTION_NAME_HANDLE)
    unlock.SortSectionIndex = 0
    unlock.SortSectionOrder = 0
    local original_on_buy = unlock.OnBuy
    unlock.OnBuy = function(self, character)
        if original_on_buy then
            original_on_buy(self, character)
        end
        maybe_emit_goal_token()
    end
    return unlock
end


local function make_pixie_blessing_unlock(template)
    local unlock = shallow_copy(template)
    unlock.Id = AP_PIXIE_BLESSING_UNLOCK_ID
    unlock.Cost = 30
    unlock.Persistent = false
    unlock.Requirement = nil
    unlock.HideStock = true
    unlock.Icon = tostring(unlock.Icon or "statIcons_Moonshield")
    unlock.SectionName = TL(AP_LOCAL_SHOP_SECTION_NAME_HANDLE)
    unlock.SortSectionIndex = 0
    unlock.SortSectionOrder = 1
    return unlock
end


local function register_shop_patch()
    if runtime.patch_registered then
        return
    end

    -- This is the big merge point from the old multi-pak setup.
    -- We replace the shop templates in-place so AP checks look native inside the ToT unlock menu.
    capture_original_unlock_templates()
    Unlock.GetTemplates = function()
        local options = get_options()
        local transformed = {}
        local goal_template = runtime.original_templates_by_id[options.goal_unlock_template_id]
        if goal_template then
            table.insert(transformed, make_goal_unlock(goal_template, options))
        end

        if options.vanilla_pixie_blessing_in_shop == true then
            local pixie_blessing_template = runtime.original_templates_by_id[PIXIE_BLESSING_UNLOCK_ID]
            if pixie_blessing_template then
                table.insert(transformed, make_pixie_blessing_unlock(pixie_blessing_template))
            end
        end

        if options.progressive_shop == true and tonumber(options.shop_fragment_count or 0) > 0 then
            for section_index = 1, tonumber(options.shop_fragment_count or 0) or 0 do
                table.insert(transformed, make_shop_section_unlock(section_index, options))
            end
        end

        for index, unlock_id in ipairs(options.shop_check_unlock_ids or {}) do
            local template = runtime.original_templates_by_id[unlock_id]
            if template then
                table.insert(transformed, make_shop_check_unlock(template, index, options))
            end
        end

        write_shop_debug_snapshot("unlock_get_templates", transformed)
        return transformed
    end

    runtime.patch_registered = true
end


local function refresh_shop_configuration(force)
    if not runtime.patch_registered or not PersistentVars.Unlocks then
        return
    end

    local signature = build_refresh_signature(get_options())
    if not force and runtime.refresh_signature == signature then
        return
    end

    runtime.refresh_signature = signature
    Unlock.Sync()
    write_shop_debug_snapshot("refresh_shop_configuration", Unlock.Get())
end


local function on_scenario_enemy_killed(_scenario, _enemy)
    refresh_seed_state()
    local state = get_state()
    state.kills = state.kills + 1
    emit_threshold_tokens("TOT-KILLS", state.kills, get_options().kill_thresholds)
    process_trials_inbox(resolve_reward_character(nil))
end


local function on_scenario_perfect_clear(_scenario)
    refresh_seed_state()
    local state = get_state()
    state.perfect_clears = state.perfect_clears + 1
    emit_threshold_tokens("TOT-PERFECT", state.perfect_clears, get_options().perfect_thresholds)
    process_trials_inbox(resolve_reward_character(nil))
end


local function on_scenario_ended(_scenario)
    refresh_seed_state()
    local state = get_state()
    state.scenario_clears = state.scenario_clears + 1
    emit_threshold_tokens("TOT-CLEAR", state.scenario_clears, get_options().clear_thresholds)
    maybe_emit_goal_token()
    process_trials_inbox(resolve_reward_character(nil))
end


local function subscribe_progress_events()
    if runtime.event_subscriptions_ready then
        return
    end

    Ext.ModEvents.ToT.ScenarioEnemyKilled:Subscribe(on_scenario_enemy_killed)
    Ext.ModEvents.ToT.ScenarioPerfectClear:Subscribe(on_scenario_perfect_clear)
    Ext.ModEvents.ToT.ScenarioEnded:Subscribe(on_scenario_ended)
    runtime.event_subscriptions_ready = true
end


local function subscribe_score_events()
    if runtime.score_subscription_ready then
        return
    end

    Event.On("RogueScoreChanged", function(_previous, score)
        record_roguescore(score)
        process_trials_inbox(resolve_reward_character(nil))
    end)
    runtime.score_subscription_ready = true
end


local function subscribe_deathlink_events()
    if runtime.deathlink_events_ready then
        return
    end

    Ext.Osiris.RegisterListener("Died", 1, "after", function(character)
        on_deathlink_character_died(character)
    end)
    Ext.Osiris.RegisterListener("DownedChanged", 2, "after", function(character, is_downed)
        on_deathlink_character_downed(character, is_downed)
    end)
    runtime.deathlink_events_ready = true
end


local function ensure_poll_loop()
    if runtime.poll_started then
        return
    end

    -- I kept the poll loop from the CombatMod-side refactor because it is the least fragile way
    -- to catch AP file updates, DeathLinks, and unlock refreshes without depending on one specific game action.
    runtime.poll_started = true
    Interval(1500, function()
        refresh_archipelago_client_ui(false)
        sync_connection_state(false)
        refresh_shop_configuration(false)
        update_party_wipe_state()
        process_incoming_deathlinks()
        process_trials_inbox(resolve_reward_character(nil))
    end)
end


local function initialize_archipelago_trials_compat()
    -- This is the single init path now that the standalone bridge mod is gone.
    refresh_archipelago_client_ui(true)
    maybe_prompt_archipelago_backend(false)
    load_pending_received_replay()
    load_pending_shop_unlock_replay()
    reapply_pending_shop_unlocks()
    register_shop_patch()
    subscribe_progress_events()
    subscribe_score_events()
    subscribe_deathlink_events()
    ensure_poll_loop()
    sync_connection_state(true)
    refresh_shop_configuration(true)
    reapply_granted_unlocks()
    record_roguescore(current_roguescore())
    update_party_wipe_state()
    process_incoming_deathlinks()
    process_trials_inbox(resolve_reward_character(nil))
end


Event.On("ModInit", initialize_archipelago_trials_compat, true)
Ext.Events.SessionLoaded:Subscribe(function()
    get_state().deathlink_suppress_local = false
    refresh_archipelago_client_ui(true)
    maybe_prompt_archipelago_backend(false)
    load_pending_received_replay()
    load_pending_shop_unlock_replay()
    reapply_pending_shop_unlocks()
    sync_connection_state(true)
    update_party_wipe_state()
    if runtime.patch_registered then
        refresh_shop_configuration(true)
        reapply_granted_unlocks()
        process_incoming_deathlinks()
        process_trials_inbox(resolve_reward_character(nil))
    end
end)

Ext.Events.GameStateChanged:Subscribe(function(event)
    if event.FromState == "Save" and event.ToState == "Running" then
        clear_pending_received()
        clear_pending_shop_unlocks()
    end
end)
