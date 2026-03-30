-- This started as a mashup of the old standalone ArchipelagoTrials bridge and the later CombatMod patch.
-- Everything BG3-side for the merged ToT build lives here now.

local AP_OUT_FILE = "ap_out.json"
local AP_IN_FILE = "ap_in.json"
local AP_NOTIFICATION_FILE = "ap_notifications.json"
local AP_OPTIONS_FILE = "ap_options.json"
local AP_DEATHLINK_IN_FILE = "ap_deathlink_in.json"
local AP_DEATHLINK_OUT_FILE = "ap_deathlink_out.json"
local AP_PENDING_RECEIVED_FILE = "ap_pending_received.json"

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
    logged_unhandled_received = {},
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
    runtime.pending_received_replay = {}
    save_json_array(AP_PENDING_RECEIVED_FILE, {})
end


local function load_pending_received_replay()
    runtime.pending_received_replay = build_lookup(load_json_array(AP_PENDING_RECEIVED_FILE))
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

    runtime.deathlink_party_wipe_active = true

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


local function append_trap_target(targets, seen, character)
    character = extract_character_uuid(character)
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


local function append_party_followers(targets, seen, owner_lookup)
    if not Ext or not Ext.Entity then
        return
    end

    for _, follower_handle in ipairs(Ext.Entity.GetAllEntitiesWithComponent("PartyFollower") or {}) do
        local follower_entity = Ext.Entity.Get(follower_handle)
        local party_follower = follower_entity and follower_entity.PartyFollower
        local followed_uuid = entity_handle_uuid(party_follower and party_follower.Following)
        if followed_uuid ~= "" and owner_lookup[followed_uuid] then
            append_trap_target(targets, seen, entity_handle_uuid(follower_handle))
        end
    end
end


local function append_owned_summons(targets, seen, owner_character)
    if not Ext or not Ext.Entity then
        return
    end

    local owner_entity = Ext.Entity.Get(owner_character)
    local summon_container = owner_entity and owner_entity.SummonContainer
    if not summon_container or not summon_container.Characters then
        return
    end

    for summon_handle, _value in pairs(summon_container.Characters) do
        append_trap_target(targets, seen, entity_handle_uuid(summon_handle))
    end
end


local function collect_party_trap_targets(preferred_character)
    local targets = {}
    local seen = {}
    local owner_lookup = {}

    for _, character in ipairs(get_active_party_members()) do
        append_trap_target(targets, seen, character)
        owner_lookup[extract_character_uuid(character)] = true
    end

    local preferred = resolve_reward_character(preferred_character)
    if preferred ~= "" then
        append_trap_target(targets, seen, preferred)
        owner_lookup[preferred] = true
    end

    append_party_followers(targets, seen, owner_lookup)

    -- Summons can themselves own more summons, so expand until the target list stops growing.
    local index = 1
    while index <= #targets do
        append_owned_summons(targets, seen, targets[index])
        index = index + 1
    end

    return targets
end


local function collect_party_member_trap_targets(preferred_character)
    local targets = {}
    local seen = {}
    local owner_lookup = {}

    for _, character in ipairs(get_active_party_members()) do
        append_trap_target(targets, seen, character)
        owner_lookup[extract_character_uuid(character)] = true
    end

    local preferred = resolve_reward_character(preferred_character)
    if preferred ~= "" then
        append_trap_target(targets, seen, preferred)
        owner_lookup[preferred] = true
    end

    append_party_followers(targets, seen, owner_lookup)
    return targets
end


local function get_character_ability_value(character, ability_name)
    if character == "" or not Osi or not Osi.GetAbility then
        return 0
    end

    local ok, value = pcall(function()
        return Osi.GetAbility(character, ability_name)
    end)
    if not ok then
        return 0
    end
    return tonumber(value or 0) or 0
end


local function pick_highest_mental_trap_target(preferred_character)
    local best_character = ""
    local best_primary = -1
    local best_total = -1

    for _, character in ipairs(collect_party_member_trap_targets(preferred_character)) do
        local intelligence = get_character_ability_value(character, "Intelligence")
        local wisdom = get_character_ability_value(character, "Wisdom")
        local charisma = get_character_ability_value(character, "Charisma")
        local primary = math.max(intelligence, wisdom, charisma)
        local total = intelligence + wisdom + charisma
        if primary > best_primary or (primary == best_primary and total > best_total) then
            best_character = character
            best_primary = primary
            best_total = total
        end
    end

    return best_character
end


local function pick_random_trap_target(targets)
    if #targets == 0 then
        return ""
    end
    return tostring(targets[math.random(1, #targets)] or "")
end


local function get_character_position(character)
    if character == "" or not Osi or not Osi.GetPosition then
        return nil
    end

    local ok, x, y, z = pcall(function()
        return Osi.GetPosition(character)
    end)
    if not ok then
        return nil
    end

    return {
        x = tonumber(x or 0) or 0,
        y = tonumber(y or 0) or 0,
        z = tonumber(z or 0) or 0,
    }
end


local function cast_position_trap_spell(spell_id, caster_character, target_character)
    if spell_id == "" or caster_character == "" or target_character == "" or not Osi or not Osi.UseSpellAtPosition then
        return false
    end

    local position = get_character_position(target_character)
    if not position then
        return false
    end

    local ok, err = pcall(function()
        Osi.UseSpellAtPosition(caster_character, spell_id, position.x, position.y, position.z, 1)
    end)
    if not ok then
        L.Error("ArchipelagoTrialsCompat/TrapSpell", spell_id, caster_character, target_character, err)
        return false
    end
    return true
end


local function cast_targeted_trap_spell(spell_id, caster_character, target_character)
    if spell_id == "" or caster_character == "" or target_character == "" or not Osi or not Osi.UseSpell then
        return false
    end

    local ok, err = pcall(function()
        Osi.UseSpell(caster_character, spell_id, target_character)
    end)
    if not ok then
        L.Error("ArchipelagoTrialsCompat/TrapSpell", spell_id, caster_character, target_character, err)
        return false
    end
    return true
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
    local trap_kind = string.match(tostring(entry or ""), "^Trap%-([^%-]+)")
    if not trap_kind then
        return false
    end

    local retired_traps = {
        Sussur = true,
        Clown = true,
        Overburdened = true,
    }
    if retired_traps[trap_kind] then
        return true
    end

    if trap_kind == "Monster" then
        -- Monster traps were a separate spawn path in the old bridge. I would rather
        -- leave this as a clean no-op than fake a spawn and break someone's run.
        return false
    end

    local targets = collect_party_trap_targets(preferred_character)
    if #targets == 0 or not Osi then
        return false
    end
    local trap_source = resolve_reward_character(preferred_character)
    local positional_traps = {
        Silence = function()
            local silence_target = pick_highest_mental_trap_target(preferred_character)
            if silence_target == "" then
                return false
            end
            return cast_position_trap_spell("Target_Silence", silence_target, silence_target)
        end,
        Grease = function()
            local grease_target = pick_random_trap_target(targets)
            if grease_target == "" then
                return false
            end
            return cast_position_trap_spell("Target_Grease", grease_target, grease_target)
        end,
    }
    local positional_trap = positional_traps[trap_kind]
    if positional_trap then
        return positional_trap()
    end

    local targeted_traps = {
        Cheesed = function()
            local applied = false
            for _, character in ipairs(targets) do
                -- The circus cheese spell is concentration-based, so each target self-casts it.
                -- That keeps the whole party cheesed instead of one shared caster dropping older applications.
                if cast_targeted_trap_spell("Target_WYR_PolymorhphCheese_Djinni", character, character) then
                    applied = true
                end
            end
            return applied
        end,
    }
    local targeted_trap = targeted_traps[trap_kind]
    if targeted_trap then
        return targeted_trap()
    end

    local statuses = {
        Bleeding = { id = "BLEEDING", duration = 5 },
        Stun = { id = "STUNNED", duration = 5 },
        -- BG3's spell data applies the CONFUSION status, not CONFUSED.
        -- It also relies on a source for SourceSpellDC()-based turn saves.
        Confusion = { id = "CONFUSION", duration = 6, force = 1, use_source = true },
        Bane = { id = "BANE", duration = 6, use_source = true },
        Blindness = { id = "BLINDNESS", duration = 6, use_source = true },
        Slow = { id = "SLOW", duration = 6, use_source = true },
        Poisoned = { id = "POISONED", duration = 6 },
        FaerieFire = { id = "FAERIE_FIRE", duration = 6 },
        Ensnared = { id = "ENSNARING_STRIKE", duration = 6, use_source = true },
        Frightened = { id = "FRIGHTENED", duration = 6, use_source = true },
        Burning = { id = "BURNING", duration = 6 },
        HoldPerson = { id = "HOLD_PERSON", duration = 6, force = 1, use_source = true },
    }
    local trap = statuses[trap_kind]
    if not trap or not Osi.ApplyStatus then
        return false
    end

    local applied = false
    for _, character in ipairs(targets) do
        local ok, err = pcall(function()
            if trap.use_source then
                local source_character = trap_source ~= "" and trap_source or character
                Osi.ApplyStatus(character, trap.id, trap.duration, tonumber(trap.force or 0), source_character)
            elseif trap.force ~= nil then
                Osi.ApplyStatus(character, trap.id, trap.duration, tonumber(trap.force or 0))
            else
                Osi.ApplyStatus(character, trap.id, trap.duration)
            end
        end)
        if not ok then
            L.Error("ArchipelagoTrialsCompat/GrantTrap", trap_kind, character, err)
        else
            applied = true
        end
    end

    return applied
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
    if not force and runtime.connection_signature == signature then
        return
    end

    runtime.connection_signature = signature
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
    unlock.Name = "NG+"
    unlock.Description = "Archipelago goal item. Buy this to complete the seed."
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
    if runtime.patch_registered then
        return
    end

    -- This is the big merge point from the old multi-pak setup.
    -- We replace the shop templates in-place so AP checks look native inside the ToT unlock menu.
    capture_original_unlock_templates()
    Unlock.GetTemplates = function()
        local options = get_options()
        local transformed = {}
        for index, unlock_id in ipairs(options.shop_check_unlock_ids or {}) do
            local template = runtime.original_templates_by_id[unlock_id]
            if template then
                table.insert(transformed, make_shop_check_unlock(template, index, options))
            end
        end

        local goal_template = runtime.original_templates_by_id[options.goal_unlock_template_id]
        if goal_template then
            table.insert(transformed, make_goal_unlock(goal_template, options))
        end

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
        sync_connection_state(false)
        refresh_shop_configuration(false)
        update_party_wipe_state()
        process_incoming_deathlinks()
        process_trials_inbox(resolve_reward_character(nil))
    end)
end


local function initialize_archipelago_trials_compat()
    -- This is the single init path now that the standalone bridge mod is gone.
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
    end
end)
