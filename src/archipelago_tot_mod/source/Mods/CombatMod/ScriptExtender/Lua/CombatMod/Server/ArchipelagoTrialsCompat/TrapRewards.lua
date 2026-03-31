local TrapRewards = {}

TrapRewards.RETIRED = {
    Sussur = true,
    Clown = true,
    Overburdened = true,
}

TrapRewards.STATUSES = {
    -- Round time stored in seconds. Osiris uses 6 seconds for one turn.
    Bleeding = { id = "BLEEDING", duration = 6.0 },
    Stun = { id = "STUNNED", duration = 6.0, force = 1 },
    -- Only statuses with SourceSpellDC()-based turn saves need a source.
    Confusion = { id = "CONFUSION", duration = 6.0, use_source = true },
    Bane = { id = "BANE", duration = 6.0 },
    Blindness = { id = "BLINDNESS", duration = 6.0, use_source = true },
    Slow = { id = "SLOW", duration = 6.0, use_source = true },
    Poisoned = { id = "POISONED", duration = 6.0 },
    FaerieFire = { id = "FAERIE_FIRE", duration = 6.0 },
    Ensnared = { id = "ENSNARING_STRIKE", duration = 6.0, use_source = true },
    Frightened = { id = "FRIGHTENED", duration = 6.0 },
    Burning = { id = "BURNING", duration = 6.0 },
    HoldPerson = { id = "HOLD_PERSON", duration = 6.0, force = 1, use_source = true },
    Silence = { id = "SILENCED", duration = 6.0 },
    Grease = { id = "PRONE", duration = 6.0 },
    Cheesed = { id = "POLYMORPH_CHEESE", duration = 6.0 },
}

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


local function extract_character_uuid(character, helpers)
    local extractor = helpers and helpers.extract_character_uuid
    if type(extractor) == "function" then
        return tostring(extractor(character) or "")
    end
    return tostring(character or "")
end


local function resolve_reward_character(preferred_character, helpers)
    local resolver = helpers and helpers.resolve_reward_character
    if type(resolver) == "function" then
        return tostring(resolver(preferred_character) or "")
    end
    return ""
end


local function active_party_members(helpers)
    local getter = helpers and helpers.get_active_party_members
    if type(getter) ~= "function" then
        return {}
    end
    return getter() or {}
end


local function append_target(targets, seen, character, helpers)
    character = extract_character_uuid(character, helpers)
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


local function append_party_followers(targets, seen, owner_lookup, helpers)
    if not Ext or not Ext.Entity then
        return
    end

    for _, follower_handle in ipairs(Ext.Entity.GetAllEntitiesWithComponent("PartyFollower") or {}) do
        local follower_entity = Ext.Entity.Get(follower_handle)
        local party_follower = follower_entity and follower_entity.PartyFollower
        local followed_uuid = entity_handle_uuid(party_follower and party_follower.Following)
        if followed_uuid ~= "" and owner_lookup[followed_uuid] then
            append_target(targets, seen, entity_handle_uuid(follower_handle), helpers)
        end
    end
end


local function append_owned_summons(targets, seen, owner_character, helpers)
    if not Ext or not Ext.Entity then
        return
    end

    local owner_entity = Ext.Entity.Get(owner_character)
    local summon_container = owner_entity and owner_entity.SummonContainer
    if not summon_container or not summon_container.Characters then
        return
    end

    for summon_handle, _value in pairs(summon_container.Characters) do
        append_target(targets, seen, entity_handle_uuid(summon_handle), helpers)
    end
end


function TrapRewards.collect_targets(preferred_character, helpers)
    local targets = {}
    local seen = {}
    local owner_lookup = {}

    for _, character in ipairs(active_party_members(helpers)) do
        append_target(targets, seen, character, helpers)
        owner_lookup[extract_character_uuid(character, helpers)] = true
    end

    local preferred = resolve_reward_character(preferred_character, helpers)
    if preferred ~= "" then
        append_target(targets, seen, preferred, helpers)
        owner_lookup[preferred] = true
    end

    append_party_followers(targets, seen, owner_lookup, helpers)

    -- Summons can own more summons, so expand until the list stops growing.
    local index = 1
    while index <= #targets do
        append_owned_summons(targets, seen, targets[index], helpers)
        index = index + 1
    end

    return targets
end


local function log_error(helpers, trap_kind, character, err)
    local logger = helpers and helpers.logger
    if logger and type(logger.Error) == "function" then
        logger.Error("ArchipelagoTrialsCompat/GrantTrap", trap_kind, character, err)
        return
    end

    print(
        "[ArchipelagoTrialsCompat] Trap error for "
            .. tostring(trap_kind)
            .. " on "
            .. tostring(character)
            .. ": "
            .. tostring(err)
    )
end


function TrapRewards.try_grant(entry, preferred_character, helpers)
    local trap_kind = string.match(tostring(entry or ""), "^Trap%-([^%-]+)")
    if not trap_kind then
        return false
    end

    if TrapRewards.RETIRED[trap_kind] then
        return true
    end

    if trap_kind == "Monster" then
        -- Monster traps used a separate spawn path in the old bridge.
        -- Keeping this as a no-op is safer than spawning the wrong thing.
        return false
    end

    local trap = TrapRewards.STATUSES[trap_kind]
    if not trap or not Osi or not Osi.ApplyStatus then
        return false
    end

    local targets = TrapRewards.collect_targets(preferred_character, helpers)
    if #targets == 0 then
        return false
    end

    local trap_source = resolve_reward_character(preferred_character, helpers)
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
            log_error(helpers, trap_kind, character, err)
        else
            applied = true
        end
    end

    return applied
end


_G.ArchipelagoTrialsCompatTrapRewards = TrapRewards

return TrapRewards
