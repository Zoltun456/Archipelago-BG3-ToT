PersistentVars = PersistentVars or {}

local AP_OUT_FILE = "ap_out.json"
local AP_IN_FILE = "ap_in.json"
local AP_OPTIONS_FILE = "ap_options.json"

local GOAL_BUY_NG_PLUS = 0
local GOAL_CLEAR_STAGES = 1
local GOAL_REACH_ROGUESCORE = 2

local shop_state = {
    initialized = false,
    patch_registered = false,
    options_signature = "",
    original_templates_by_id = {},
    original_template_order = {},
}

local subscriptions_ready = false
local roguescore_subscription_ready = false
local loot_patch_ready = false
local granted_unlock_session_init = {}


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


local function list_contains(values, target)
    for _, value in ipairs(values or {}) do
        if value == target then
            return true
        end
    end
    return false
end


local function find_unlock_by_id(unlock_id, unlocks)
    for _, unlock in ipairs(unlocks or {}) do
        if unlock.Id == unlock_id then
            return unlock
        end
    end
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


local function extract_character_uuid(character)
    if not character or character == "" then
        return ""
    end

    if U and U.UUID and U.UUID.Extract then
        local ok, extracted = pcall(U.UUID.Extract, character)
        if ok and extracted and extracted ~= "" then
            return extracted
        end
    end

    return character
end


local function is_valid_reward_character(character)
    character = extract_character_uuid(character)
    if character == "" then
        return false, ""
    end

    if Osi and Osi.IsCharacter and Osi.IsCharacter(character) ~= 1 then
        return false, ""
    end

    if GU and GU.Character and GU.Character.IsPlayable and not GU.Character.IsPlayable(character) then
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

    if GU and GU.DB and GU.DB.GetAvatars then
        local avatar = first_valid_reward_character(GU.DB.GetAvatars())
        if avatar ~= "" then
            return avatar
        end
    end

    if GU and GU.DB and GU.DB.GetPlayers then
        local player = first_valid_reward_character(GU.DB.GetPlayers())
        if player ~= "" then
            return player
        end
    end

    if Player and Player.Host then
        local host_ok, host_character = pcall(Player.Host)
        if host_ok then
            local host_valid, host_normalized = is_valid_reward_character(host_character)
            if host_valid then
                return host_normalized
            end
        end
    end

    if GetHostCharacter then
        local host_valid, host_normalized = is_valid_reward_character(GetHostCharacter())
        if host_valid then
            return host_normalized
        end
    end

    return ""
end


local function reset_comm_files_for_new_seed()
    save_json_array(AP_OUT_FILE, {})
end


local function get_state()
    if not PersistentVars.ArchipelagoTrials then
        PersistentVars.ArchipelagoTrials = {
            scenario_clears = 0,
            perfect_clears = 0,
            kills = 0,
            received_items = {},
            granted_unlocks = {},
            goal_completed = false,
        }
    end

    local state = PersistentVars.ArchipelagoTrials
    state.received_items = state.received_items or {}
    state.granted_unlocks = state.granted_unlocks or {}
    if state.goal_completed == nil then
        state.goal_completed = false
    end

    return state
end


local function get_options()
    local options = load_json_object(AP_OPTIONS_FILE)
    options.clear_thresholds = options.clear_thresholds or {}
    options.kill_thresholds = options.kill_thresholds or {}
    options.perfect_thresholds = options.perfect_thresholds or {}
    options.roguescore_thresholds = options.roguescore_thresholds or {}
    options.shop_check_unlock_ids = options.shop_check_unlock_ids or {}
    options.shop_display = options.shop_display or {}
    options.goal = options.goal or GOAL_BUY_NG_PLUS
    options.goal_clear_target = options.goal_clear_target or 0
    options.goal_rogue_score_target = options.goal_rogue_score_target or 0
    options.goal_unlock_id = options.goal_unlock_id or "QUICKSTART"
    options.sync_method = options.sync_method or 1
    return options
end


local function ensure_seed_initialized()
    local seed_name = tostring(get_options().seed_name or "")
    if seed_name == "" then
        return
    end

    local state = get_state()
    if state.seed_name == seed_name then
        return
    end

    state.seed_name = seed_name
    reset_comm_files_for_new_seed()
end


local function append_unique_token(token)
    local data = load_json_array(AP_OUT_FILE)
    for _, existing in ipairs(data) do
        if existing == token then
            return false
        end
    end

    table.insert(data, token)
    save_json_array(AP_OUT_FILE, data)
    print("[ArchipelagoTrials] Logged token " .. token)
    return true
end


local function emit_threshold_tokens(prefix, count_value, thresholds)
    for index, threshold in ipairs(thresholds or {}) do
        if count_value >= (tonumber(threshold) or 0) then
            append_unique_token(string.format("%s-%03d", prefix, index))
        end
    end
end


local function current_roguescore()
    return tonumber(PersistentVars.RogueScore) or 0
end


local function goal_unlock_bought(goal_unlock_id)
    if not Unlock or not Unlock.Get then
        return false
    end

    local unlock = find_unlock_by_id(goal_unlock_id, Unlock.Get())
    return unlock ~= nil and tonumber(unlock.Bought or 0) > 0
end


local function maybe_emit_goal_token()
    local state = get_state()
    if state.goal_completed then
        return
    end

    local options = get_options()
    local complete = false

    if tonumber(options.goal) == GOAL_BUY_NG_PLUS then
        complete = goal_unlock_bought(options.goal_unlock_id)
    elseif tonumber(options.goal) == GOAL_CLEAR_STAGES then
        complete = state.scenario_clears >= (tonumber(options.goal_clear_target) or 0)
    elseif tonumber(options.goal) == GOAL_REACH_ROGUESCORE then
        complete = current_roguescore() >= (tonumber(options.goal_rogue_score_target) or 0)
    end

    if complete then
        state.goal_completed = true
        append_unique_token("TOT-GOAL-001")
    end
end


local function record_roguescore(score)
    emit_threshold_tokens("TOT-ROGUESCORE", tonumber(score) or 0, get_options().roguescore_thresholds)
    maybe_emit_goal_token()
end


local function restore_unlock_with_state(template, state)
    local unlock_data = shallow_copy(template)
    unlock_data.Bought = tonumber(table_get(state, "Bought", 0) or 0)
    unlock_data.BoughtBy = shallow_copy(table_get(state, "BoughtBy", {}))
    return Unlock.Restore(unlock_data)
end


local function capture_original_unlock_templates()
    if shop_state.initialized then
        return
    end

    if not Templates or not Templates.GetUnlocks then
        if not External or not External.Templates or not External.Templates.GetUnlocks then
            return
        end
    end

    local templates = {}
    if Templates and Templates.GetUnlocks then
        templates = Templates.GetUnlocks()
    elseif External and External.Templates and External.Templates.GetUnlocks then
        templates = External.Templates.GetUnlocks()
    end

    if not templates then
        return
    end
    for _, template in ipairs(templates or {}) do
        local copy = shallow_copy(template)
        shop_state.original_templates_by_id[copy.Id] = copy
        table.insert(shop_state.original_template_order, copy.Id)
    end
    shop_state.initialized = true
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


local function build_granted_unlock(unlock_id)
    local template = shop_state.original_templates_by_id[unlock_id]
    if not template then
        return nil
    end

    local record = get_granted_unlock_record(unlock_id)
    local unlock = shallow_copy(template)
    unlock.Bought = record.Bought
    unlock.BoughtBy = shallow_copy(record.BoughtBy)
    if Unlock and Unlock.Restore then
        return Unlock.Restore(unlock)
    end
    return unlock
end


local function ensure_granted_unlock_initialized(unlock_id, unlock)
    if granted_unlock_session_init[unlock_id] then
        return
    end

    if unlock and unlock.OnInit then
        pcall(unlock.OnInit, unlock)
    end
    granted_unlock_session_init[unlock_id] = true
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
    local template = shop_state.original_templates_by_id[unlock_id]
    if not template then
        print("[ArchipelagoTrials] Missing unlock template for " .. tostring(unlock_id))
        return false
    end

    local character = resolve_reward_character(preferred_character)
    if template.Character and character == "" then
        print("[ArchipelagoTrials] Could not resolve a party avatar for AP reward " .. tostring(unlock_id))
        return false
    end

    local unlock = build_granted_unlock(unlock_id)
    if not unlock then
        return false
    end

    ensure_granted_unlock_initialized(unlock_id, unlock)
    if unlock.Buy then
        local ok, err = pcall(function()
            unlock:Buy(character)
        end)
        if not ok then
            print("[ArchipelagoTrials] Failed to grant AP unlock " .. tostring(unlock_id) .. ": " .. tostring(err))
            return false
        end
    elseif unlock.OnBuy then
        pcall(unlock.OnBuy, unlock, character)
    end
    if unlock.OnReapply then
        pcall(unlock.OnReapply, unlock)
    end

    local record = get_granted_unlock_record(unlock_id)
    record.Bought = tonumber(unlock.Bought or 0)
    record.BoughtBy = shallow_copy(unlock.BoughtBy or {})

    print("[ArchipelagoTrials] Granted AP unlock " .. tostring(unlock_id))
    maybe_emit_goal_token()
    return true
end


local function shop_check_id(original_id)
    return "APCHECK::" .. original_id
end


local function remap_requirement_value(requirement_value, selected_by_id)
    if type(requirement_value) == "string" and selected_by_id[requirement_value] then
        return shop_check_id(requirement_value)
    end

    return requirement_value
end


local function remap_requirement(requirement, selected_by_id)
    if type(requirement) ~= "table" then
        return remap_requirement_value(requirement, selected_by_id)
    end

    local remapped = {}
    for index, value in ipairs(requirement) do
        remapped[index] = remap_requirement_value(value, selected_by_id)
    end
    return remapped
end


local function selected_unlock_indexes(options)
    local selected_by_id = {}
    local selected_index_by_id = {}

    for index, unlock_id in ipairs(options.shop_check_unlock_ids or {}) do
        selected_by_id[unlock_id] = true
        selected_index_by_id[unlock_id] = index
    end

    return selected_by_id, selected_index_by_id
end


local function build_shop_options_signature(options)
    if not Ext or not Ext.Json or not Ext.Json.Stringify then
        return tostring(#(options.shop_check_unlock_ids or {}))
    end

    return Ext.Json.Stringify({
        goal_unlock_id = options.goal_unlock_id or "",
        shop_check_unlock_ids = options.shop_check_unlock_ids or {},
        shop_display = options.shop_display or {},
    })
end


local function make_shop_check_unlock(template, index, selected_by_id)
    local shop_preview = table_get(get_options().shop_display, index, {})
    local unlock_data = shallow_copy(template)
    unlock_data.Id = shop_check_id(template.Id)
    unlock_data.Name = table_get(
        shop_preview,
        "display_name",
        "AP Check: " .. tostring(template.Name or template.Id)
    )
    unlock_data.Description = "Sends an Archipelago check. The reward is delivered from the multiworld."
    if table_get(shop_preview, "item_name", "") ~= "" then
        unlock_data.Description = "Sends "
            .. tostring(shop_preview.item_name)
            .. " from the multiworld."
    end
    if table_get(shop_preview, "player_name", "") ~= "" then
        unlock_data.Description = unlock_data.Description
            .. " Recipient: "
            .. tostring(shop_preview.player_name)
            .. "."
    end
    unlock_data.Character = false
    unlock_data.Persistent = false
    unlock_data.Requirement = remap_requirement(template.Requirement, selected_by_id)
    unlock_data.OnInit = function() end
    unlock_data.OnReapply = function() end
    unlock_data.OnBuy = function(_self, _character)
        append_unique_token(string.format("TOT-SHOP-%03d", index))
    end
    return unlock_data
end


local function register_shop_patch()
    if shop_state.patch_registered then
        return
    end

    if not External or not External.Templates or not External.Templates.PatchUnlocks then
        return
    end

    External.Templates.PatchUnlocks(function(unlock)
        local options = get_options()
        local selected_by_id, selected_index_by_id = selected_unlock_indexes(options)

        if selected_by_id[unlock.Id] then
            return make_shop_check_unlock(unlock, selected_index_by_id[unlock.Id], selected_by_id)
        end

        unlock.Requirement = remap_requirement(unlock.Requirement, selected_by_id)
        if unlock.Id == options.goal_unlock_id then
            local original_on_buy = unlock.OnBuy
            unlock.OnBuy = function(self, character)
                if original_on_buy then
                    original_on_buy(self, character)
                end
                maybe_emit_goal_token()
            end
        end
        return unlock
    end)

    shop_state.patch_registered = true
end


local function apply_shop_configuration()
    if not Unlock or not Unlock.Sync then
        return
    end

    capture_original_unlock_templates()
    register_shop_patch()
    if not shop_state.initialized or not shop_state.patch_registered then
        return
    end

    local signature = build_shop_options_signature(get_options())
    if shop_state.options_signature == signature then
        maybe_emit_goal_token()
        return
    end

    shop_state.options_signature = signature
    Unlock.Sync()
    maybe_emit_goal_token()
end


local function grant_trials_filler(kind, amount)
    amount = tonumber(amount) or 0
    if amount <= 0 then
        return false
    end

    if kind == "Currency" then
        if Unlock and Unlock.UpdateCurrency then
            Unlock.UpdateCurrency((tonumber(PersistentVars.Currency) or 0) + amount)
        else
            PersistentVars.Currency = (tonumber(PersistentVars.Currency) or 0) + amount
        end
        return true
    end

    if kind == "RogueScore" then
        if GameMode and GameMode.UpdateRogueScore then
            GameMode.UpdateRogueScore(current_roguescore() + amount)
        else
            PersistentVars.RogueScore = current_roguescore() + amount
        end
        record_roguescore(current_roguescore())
        return true
    end

    if kind == "Experience" then
        if Player and Player.GiveExperience then
            Player.GiveExperience(amount)
            return true
        end
    end

    return false
end


local function patch_trials_loot()
    if loot_patch_ready or not Item or not Item.GenerateLoot or not Item.GenerateSimpleLoot then
        return
    end

    Item.GenerateLoot = function(rolls, lootRates)
        local reduced_rolls = math.max(1, math.ceil((tonumber(rolls) or 1) / 4))
        return Item.GenerateSimpleLoot(reduced_rolls, 0.85, lootRates)
    end

    loot_patch_ready = true
end


local function process_trials_inbox(character)
    ensure_seed_initialized()
    apply_shop_configuration()
    local state = get_state()
    local inbox = load_json_array(AP_IN_FILE)

    for _, entry in ipairs(inbox) do
        if not state.received_items[entry] then
            if string.sub(entry, 1, 10) == "ToTUnlock:" then
                local unlock_id = string.match(entry, "^ToTUnlock:([^:]+)")
                if unlock_id and grant_unlock_reward(unlock_id, character) then
                    state.received_items[entry] = true
                end
            elseif string.sub(entry, 1, 10) == "ToTFiller:" then
                local kind, amount = string.match(entry, "^ToTFiller:([^:]+):([^:]+)")
                if kind and amount and grant_trials_filler(kind, amount) then
                    state.received_items[entry] = true
                end
            end
        end
    end
end


local function should_sync_on_spell(spell_name)
    local options = get_options()
    if tonumber(options.sync_method) == 0 then
        return spell_name == "Shout_AP_Sync"
    end
    return true
end


local function on_scenario_enemy_killed(_scenario, _enemy)
    ensure_seed_initialized()
    local state = get_state()
    state.kills = (tonumber(state.kills) or 0) + 1
    emit_threshold_tokens("TOT-KILLS", state.kills, get_options().kill_thresholds)
end


local function on_scenario_perfect_clear(_scenario)
    ensure_seed_initialized()
    local state = get_state()
    state.perfect_clears = (tonumber(state.perfect_clears) or 0) + 1
    emit_threshold_tokens("TOT-PERFECT", state.perfect_clears, get_options().perfect_thresholds)
end


local function on_scenario_ended(_scenario)
    ensure_seed_initialized()
    local state = get_state()
    state.scenario_clears = (tonumber(state.scenario_clears) or 0) + 1
    emit_threshold_tokens("TOT-CLEAR", state.scenario_clears, get_options().clear_thresholds)
    maybe_emit_goal_token()
end


local function subscribe_tot_events()
    if subscriptions_ready then
        return
    end

    if not Ext.ModEvents or not Ext.ModEvents.ToT then
        print("[ArchipelagoTrials] Trials ModEvents namespace not available yet.")
        return
    end

    Ext.ModEvents.ToT.ScenarioEnemyKilled:Subscribe(on_scenario_enemy_killed)
    Ext.ModEvents.ToT.ScenarioPerfectClear:Subscribe(on_scenario_perfect_clear)
    Ext.ModEvents.ToT.ScenarioEnded:Subscribe(on_scenario_ended)

    subscriptions_ready = true
    print("[ArchipelagoTrials] Subscribed to Trials of Tav mod events.")
end


local function subscribe_roguescore_events()
    if roguescore_subscription_ready then
        return
    end

    if not Event or not Event.On then
        return
    end

    Event.On("RogueScoreChanged", function(_previous, score)
        record_roguescore(score)
    end)

    roguescore_subscription_ready = true
end


local function on_session_loaded()
    get_state()
    ensure_seed_initialized()
    subscribe_tot_events()
    subscribe_roguescore_events()
    patch_trials_loot()
    apply_shop_configuration()
    reapply_granted_unlocks()
end


Ext.Events.SessionLoaded:Subscribe(on_session_loaded)

Ext.Osiris.RegisterListener("CastedSpell", 5, "after", function(_caster, spell, _spellType, _spellElement, _storyActionID)
    if not should_sync_on_spell(spell) then
        return
    end

    local host_character = nil
    if GetHostCharacter then
        host_character = GetHostCharacter()
    end
    process_trials_inbox(host_character)
end)

print("[ArchipelagoTrials] Ready")
