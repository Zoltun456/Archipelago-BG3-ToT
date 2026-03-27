local AP_OUT_FILE = "ap_out.json"
local AP_IN_FILE = "ap_in.json"
local AP_NOTIFICATION_FILE = "ap_notifications.json"
local AP_OPTIONS_FILE = "ap_options.json"
local AP_DEATHLINK_IN_FILE = "ap_deathlink_in.json"
local AP_DEATHLINK_OUT_FILE = "ap_deathlink_out.json"
local AP_PENDING_RECEIVED_FILE = "ap_pending_received.json"
local AP_SHOP_DEBUG_FILE = "ap_shop_debug.json"

local GOAL_BUY_NG_PLUS = 0
local GOAL_CLEAR_STAGES = 1
local GOAL_REACH_ROGUESCORE = 2
local DEATHLINK_TRIGGER_FULL_PARTY_WIPE = 0
local DEATHLINK_TRIGGER_ANY_PARTY_KILL = 1
local DEATHLINK_TRIGGER_ANY_PARTY_DOWNED = 2
local AP_GOAL_UNLOCK_ID = "APGOAL::QUICKSTART"
local DEFAULT_GOAL_UNLOCK_TEMPLATE_ID = "QUICKSTART"
local DEFAULT_GOAL_UNLOCK_COST = 2000
local AP_NOTIFICATION_DURATION = 6

Mod.PersistentVarsTemplate.ArchipelagoTrialsCompat = Mod.PersistentVarsTemplate.ArchipelagoTrialsCompat or {
    scenario_clears = 0,
    perfect_clears = 0,
    kills = 0,
    received_items = {},
    granted_unlocks = {},
    shop_unlocks = {},
    goal_completed = false,
    deathlink_out_counter = 0,
    deathlink_suppress_local = false,
    seed_name = "",
}

local compat = {
    patch_registered = false,
    poll_started = false,
    event_subscriptions_ready = false,
    score_subscription_ready = false,
    connection_signature = "",
    refresh_signature = "",
    original_unlock_get_templates = nil,
    original_templates_by_id = {},
    original_template_order = {},
    granted_unlock_session_init = {},
    deathlink_events_ready = false,
    deathlink_party_wipe_active = false,
    pending_received_replay = {},
}

local emit_threshold_tokens
local maybe_emit_goal_token

_G.ArchipelagoTrialsCompatNotificationsOwner = true


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


local function clear_pending_received()
    compat.pending_received_replay = {}
    save_json_array(AP_PENDING_RECEIVED_FILE, {})
end


local function load_pending_received_replay()
    compat.pending_received_replay = build_lookup(load_json_array(AP_PENDING_RECEIVED_FILE))
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


local function process_ap_notifications()
    local queue = load_json_array(AP_NOTIFICATION_FILE)
    if #queue == 0 then
        return
    end

    for _, entry in ipairs(queue) do
        notify_player(entry)
    end

    save_json_array(AP_NOTIFICATION_FILE, {})
end


local function get_state()
    local state = PersistentVars.ArchipelagoTrialsCompat or {}
    PersistentVars.ArchipelagoTrialsCompat = state
    state.received_items = state.received_items or {}
    state.granted_unlocks = state.granted_unlocks or {}
    state.shop_unlocks = state.shop_unlocks or {}
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
    options.active_connection = options.active_connection == true
    options.death_link = options.death_link == true or tonumber(options.death_link or 0) == 1
    options.death_link_trigger = tonumber(options.death_link_trigger or DEATHLINK_TRIGGER_FULL_PARTY_WIPE)
    options.goal = tonumber(options.goal or GOAL_BUY_NG_PLUS)
    options.goal_clear_target = tonumber(options.goal_clear_target or 0)
    options.goal_rogue_score_target = tonumber(options.goal_rogue_score_target or 0)
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
    return unlock_id == AP_GOAL_UNLOCK_ID or string.match(tostring(unlock_id or ""), "^APCHECK::") ~= nil
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
    state.goal_completed = false
    state.deathlink_out_counter = 0
    state.deathlink_suppress_local = false
    compat.granted_unlock_session_init = {}
    compat.deathlink_party_wipe_active = false
    reset_ap_runtime_unlock_state()
    save_json_array(AP_OUT_FILE, {})
    save_json_array(AP_DEATHLINK_IN_FILE, {})
    save_json_array(AP_DEATHLINK_OUT_FILE, {})
    clear_pending_received()
    return true
end


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
    compat.deathlink_party_wipe_active = is_party_wiped()
    return compat.deathlink_party_wipe_active
end


local function should_track_deathlink_character(character)
    character = tostring(character or "")
    if character == "" or Osi.IsCharacter(character) ~= 1 then
        return false
    end
    if not GC.IsPlayable(character) then
        return false
    end
    return Osi.CanJoinCombat(character) == 1
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

    if compat.deathlink_party_wipe_active then
        return false
    end

    if not is_party_wiped() then
        compat.deathlink_party_wipe_active = false
        return false
    end

    compat.deathlink_party_wipe_active = true
    return queue_outgoing_deathlink("suffered a full party wipe in Trials of Tav.")
end


local function kill_party_for_deathlink(event)
    local state = get_state()
    state.deathlink_suppress_local = true

    local source = tostring(event and event.source or "")
    local party_members = get_active_party_members()
    for _, character in ipairs(party_members) do
        if Osi.IsDead(character) ~= 1 then
            Osi.Die(character, 0, C.NullGuid, 0, 0)
        end
    end

    compat.deathlink_party_wipe_active = true

    if source ~= "" then
        Player.Notify(__("DeathLink received from %s. Reload your latest save.", source), true)
    else
        Player.Notify(__("DeathLink received. Reload your latest save."), true)
    end
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

    kill_party_for_deathlink(queue[#queue])
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


local function capture_original_unlock_templates()
    if compat.original_template_order[1] then
        return
    end

    for _, template in ipairs(Templates.GetUnlocks() or {}) do
        local copy = shallow_copy(template)
        compat.original_templates_by_id[copy.Id] = copy
        table.insert(compat.original_template_order, copy.Id)
    end
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


local function build_granted_unlock(unlock_id)
    capture_original_unlock_templates()
    local template = compat.original_templates_by_id[unlock_id]
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
    if compat.granted_unlock_session_init[unlock_id] then
        return
    end

    if unlock.OnInit then
        pcall(unlock.OnInit, unlock)
    end
    compat.granted_unlock_session_init[unlock_id] = true
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
    capture_original_unlock_templates()
    local template = compat.original_templates_by_id[unlock_id]
    if not template then
        return false
    end

    local character = resolve_reward_character(preferred_character)
    if character == "" then
        return false
    end

    local unlock = build_granted_unlock(unlock_id)
    if not unlock then
        return false
    end

    ensure_granted_unlock_initialized(unlock_id, unlock)
    local ok, err = pcall(function()
        unlock:Buy(character)
    end)
    if not ok then
        L.Error("ArchipelagoTrialsCompat/GrantUnlock", unlock_id, err)
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
            local should_replay = compat.pending_received_replay[entry] == true
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
                        elseif grant_unlock_reward(unlock_id, preferred_character) then
                            granted = true
                        end
                    end
                elseif string.sub(entry, 1, 10) == "ToTFiller:" then
                    local kind, amount = string.match(entry, "^ToTFiller:([^:]+):([^:]+)")
                    if kind and amount and grant_trials_filler(kind, amount) then
                        granted = true
                    end
                end

                if granted then
                    state.received_items[entry] = true
                    remember_pending_received(entry)
                    compat.pending_received_replay[entry] = nil
                end
            end
        end
    end

    process_ap_notifications()
end


local function shop_check_id(original_id, index)
    return string.format("APCHECK::%03d::%s", index, original_id)
end


local function build_refresh_signature(options)
    return Ext.Json.Stringify({
        active_connection = options.active_connection == true,
        goal_unlock_id = options.goal_unlock_id or "",
        goal_unlock_template_id = options.goal_unlock_template_id or "",
        goal_unlock_cost = options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST,
        shop_check_unlock_ids = options.shop_check_unlock_ids or {},
        shop_check_costs = options.shop_check_costs or {},
        shop_display = options.shop_display or {},
    })
end


local function sync_connection_state(force)
    local options = get_options()
    local signature = tostring(options.active_connection == true) .. "|" .. tostring(options.seed_name or "")
    if not force and compat.connection_signature == signature then
        return
    end

    compat.connection_signature = signature
    rebuild_progress_tokens()
end


local function make_shop_check_unlock(template, index, options)
    local shop_preview = table_get(options.shop_display, index, {})
    local token_index = tonumber(table_get(shop_preview, "token_index", index)) or index
    local unlock = shallow_copy(template)
    unlock.Id = shop_check_id(template.Id, token_index)
    unlock.Name = table_get(shop_preview, "display_name", "AP Check: " .. tostring(template.Name or template.Id))
    unlock.FallbackIcon = template.Icon
    local randomized_cost = tonumber(table_get(options.shop_check_costs, index, unlock.Cost))
    if randomized_cost and randomized_cost > 0 then
        unlock.Cost = randomized_cost
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
    unlock.Description = "Sends an Archipelago check. The reward is delivered from the multiworld."
    if table_get(shop_preview, "item_name", "") ~= "" then
        unlock.Description = "Sends " .. tostring(shop_preview.item_name) .. " from the multiworld."
    end
    if table_get(shop_preview, "player_name", "") ~= "" then
        unlock.Description = unlock.Description .. " Recipient: " .. tostring(shop_preview.player_name) .. "."
    end
    unlock.Character = false
    unlock.Persistent = false
    unlock.Amount = 1
    local saved_record = get_shop_unlock_record(unlock.Id)
    unlock.Bought = tonumber(saved_record.Bought or 0)
    unlock.BoughtBy = shallow_copy(saved_record.BoughtBy or {})
    unlock.HideStock = true
    unlock.Requirement = nil
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
    end
    return unlock
end


local function make_goal_unlock(template, options)
    local unlock = shallow_copy(template)
    unlock.Id = tostring(options.goal_unlock_id or AP_GOAL_UNLOCK_ID)
    local configured_cost = tonumber(options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST)
        or DEFAULT_GOAL_UNLOCK_COST
    unlock.Cost = math.max(0, configured_cost)
    unlock.Persistent = false
    unlock.Bought = 0
    unlock.BoughtBy = {}
    unlock.Requirement = nil
    unlock.HideStock = true
    local original_on_buy = unlock.OnBuy
    unlock.OnBuy = function(self, character)
        if original_on_buy then
            original_on_buy(self, character)
        end
        maybe_emit_goal_token()
    end
    return unlock
end


local function register_shop_patch()
    if compat.patch_registered then
        return
    end

    capture_original_unlock_templates()
    compat.original_unlock_get_templates = compat.original_unlock_get_templates or Unlock.GetTemplates
    Unlock.GetTemplates = function()
        local options = get_options()
        local transformed = {}
        for index, unlock_id in ipairs(options.shop_check_unlock_ids or {}) do
            local template = compat.original_templates_by_id[unlock_id]
            if template then
                table.insert(transformed, make_shop_check_unlock(template, index, options))
            end
        end

        local goal_template = compat.original_templates_by_id[options.goal_unlock_template_id]
        if goal_template then
            table.insert(transformed, make_goal_unlock(goal_template, options))
        end

        return transformed
    end

    compat.patch_registered = true
end


local function write_shop_debug_snapshot()
    local options = get_options()
    local template_ids = {}
    for _, unlock in ipairs((Unlock.GetTemplates and Unlock.GetTemplates()) or {}) do
        table.insert(template_ids, tostring(unlock.Id or ""))
    end

    local persistent_ids = {}
    for _, unlock in ipairs(PersistentVars.Unlocks or {}) do
        table.insert(persistent_ids, tostring(unlock.Id or ""))
    end

    save_json_object(AP_SHOP_DEBUG_FILE, {
        active_connection = options.active_connection == true,
        seed_name = tostring(options.seed_name or ""),
        goal_unlock_id = tostring(options.goal_unlock_id or ""),
        goal_unlock_template_id = tostring(options.goal_unlock_template_id or ""),
        goal_unlock_cost = tonumber(options.goal_unlock_cost or DEFAULT_GOAL_UNLOCK_COST)
            or DEFAULT_GOAL_UNLOCK_COST,
        selected_shop_count = #(options.shop_check_unlock_ids or {}),
        selected_shop_ids = options.shop_check_unlock_ids or {},
        selected_shop_costs = options.shop_check_costs or {},
        template_ids = template_ids,
        persistent_unlock_ids = persistent_ids,
    })
end


local function refresh_shop_configuration(force)
    if not compat.patch_registered or not PersistentVars.Unlocks then
        return
    end

    local signature = build_refresh_signature(get_options())
    if not force and compat.refresh_signature == signature then
        return
    end

    compat.refresh_signature = signature
    Unlock.Sync()
    write_shop_debug_snapshot()
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
    if compat.event_subscriptions_ready then
        return
    end

    Ext.ModEvents.ToT.ScenarioEnemyKilled:Subscribe(on_scenario_enemy_killed)
    Ext.ModEvents.ToT.ScenarioPerfectClear:Subscribe(on_scenario_perfect_clear)
    Ext.ModEvents.ToT.ScenarioEnded:Subscribe(on_scenario_ended)
    compat.event_subscriptions_ready = true
end


local function subscribe_score_events()
    if compat.score_subscription_ready then
        return
    end

    Event.On("RogueScoreChanged", function(_previous, score)
        record_roguescore(score)
        process_trials_inbox(resolve_reward_character(nil))
    end)
    compat.score_subscription_ready = true
end


local function subscribe_deathlink_events()
    if compat.deathlink_events_ready then
        return
    end

    Ext.Osiris.RegisterListener("Died", 1, "after", function(character)
        on_deathlink_character_died(character)
    end)
    Ext.Osiris.RegisterListener("DownedChanged", 2, "after", function(character, is_downed)
        on_deathlink_character_downed(character, is_downed)
    end)
    compat.deathlink_events_ready = true
end


local function ensure_poll_loop()
    if compat.poll_started then
        return
    end

    compat.poll_started = true
    Interval(1500, function()
        sync_connection_state(false)
        refresh_shop_configuration(false)
        update_party_wipe_state()
        process_incoming_deathlinks()
        process_trials_inbox(resolve_reward_character(nil))
    end)
end


local function initialize_archipelago_trials_compat()
    load_pending_received_replay()
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
    load_pending_received_replay()
    sync_connection_state(true)
    update_party_wipe_state()
    if compat.patch_registered then
        refresh_shop_configuration(true)
        reapply_granted_unlocks()
        process_incoming_deathlinks()
        process_trials_inbox(resolve_reward_character(nil))
    end
end)

Ext.Events.GameStateChanged:Subscribe(function(event)
    if event.FromState == "Save" and event.ToState == "Running" then
        clear_pending_received()
    end
end)
