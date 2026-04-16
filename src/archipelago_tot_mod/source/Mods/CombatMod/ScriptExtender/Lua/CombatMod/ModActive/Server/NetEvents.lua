local function ArchipelagoClientStatePayload()
    local provider = rawget(_G, "ArchipelagoTrialsCompatGetClientUiState")
    if type(provider) ~= "function" then
        return nil
    end

    local ok, payload = pcall(provider)
    if not ok or type(payload) ~= "table" then
        return nil
    end

    return payload
end

local function SyncArchipelagoClientState(peerId)
    local payload = ArchipelagoClientStatePayload()
    if payload then
        Net.Send("ArchipelagoClientState", payload, nil, peerId)
    end
end

function SyncState(peerId)
    Net.Send(
        "SyncState",
        table.filter(PersistentVars, function(v, k)
            if k == "SpawnedEnemies" and table.size(v) > 30 then
                return false
            end
            return true
        end, true),
        nil,
        peerId
    )
    SyncArchipelagoClientState(peerId)
end

Net.On("SyncState", function(event)
    SyncState(event.PeerId)
end)

Net.On("IsHost", function(event)
    Net.Respond(event, event:IsHost())
end)

Net.On("GUIReady", function(event)
    if PersistentVars.GUIOpen then
        Net.Send("OpenGUI")
    end
    SyncArchipelagoClientState(event.PeerId)
end)

Event.On("ArchipelagoClientUiStateChanged", function()
    SyncArchipelagoClientState()
end)

Net.On("GetSelection", function(event)
    Net.Respond(event, {
        Scenarios = table.map(Scenario.GetTemplates(), function(v, k)
            if PersistentVars.RogueModeActive and not v.RogueLike then
                return nil
            end
            return { Id = k, Name = v.Name }
        end),
		
		
        Maps = table.map(Map.GetTemplates(), function(v, k)
            return { Id = k, Name = v.Name, Author = v.Author }
        end),
    })
end)

Net.On("GetTemplates", function(event)
    Net.Respond(event, {
        Scenarios = Scenario.GetTemplates(),
        Maps = Map.GetTemplates(),
        -- Enemies = Enemy.GetTemplates(),
    })
end)

Net.On("ResetTemplates", function(event)
    if event.Payload.Scenarios then
        Templates.ExportScenarios()
    end
    if event.Payload.Maps then
        Templates.ExportMaps()
    end
	local exandriaCheck = Ext.Mod.IsModLoaded("a27fdbe3-4d1a-641d-d05f-1ba4ee529da8")
	
    if event.Payload.Enemies and PersistentVars.LoneWolfMode and exandriaCheck then
        Templates.ExportExandriaSoloModeEnemies()
    elseif event.Payload.Enemies and exandriaCheck then
        Templates.ExportExandriaModeEnemies()
	elseif event.Payload.Enemies and PersistentVars.LoneWolfMode then
		Templates.ExportSoloModeEnemies()
	else
		Templates.ExportEnemies()
    end
    if event.Payload.LootRates then
        Templates.ExportLootRates()
    end

    Net.Respond(event, { true })
end)

Net.On("GetEnemies", function(event)
    local tier = event.Payload and event.Payload.Tier

    local grouped = {}
    for _, v in ipairs(Enemy.GetTemplates()) do
        if not tier or v.Tier == tier then
            if not grouped[v.Tier] then
                grouped[v.Tier] = {}
            end
            table.insert(grouped[v.Tier], v)
        end
    end

    Net.Respond(event, grouped)
end)

Net.On("GetItems", function(event)
    local rarity = event.Payload and event.Payload.Rarity
    Net.Respond(event, {
        Objects = Item.Objects(rarity, false),
        CombatObjects = Item.Objects(rarity, true),
        Armor = Item.Armor(rarity),
        Weapons = Item.Weapons(rarity),
    })
end)

Net.On("Start", function(event)
    local scenarioName = event.Payload.Scenario
    local mapName = event.Payload.Map
	local difficultyValue = event.Payload.Difficulty
	
	if difficultyValue == 0 then
        PersistentVars.HardMode = false
        PersistentVars.SuperHardMode = false
        Event.Trigger("difficultyModeChanged", true)
	elseif difficultyValue == 1 then
	    PersistentVars.HardMode = true
		PersistentVars.SuperHardMode = false
		Event.Trigger("difficultyModeChanged", true)
	elseif difficultyValue == 2 then
	    PersistentVars.HardMode = false
		PersistentVars.SuperHardMode = true
		Event.Trigger("difficultyModeChanged", true)
	else
	    Net.Respond(event, { false, TL("h296c87dcg7c39g4d28g91a5gfb4ef387d96c") })
	end

    local template = table.find(Scenario.GetTemplates(), function(v)
        return v.Name == scenarioName
    end)

    local map = table.find(Map.Get(), function(v)
        return v.Name == mapName
    end)

    if template == nil then
        Net.Respond(event, { false, TL("h296c87dcg7c39g4d28g91a5gfb4ef387d96c") })
        return
    end
    if mapName and map == nil then
        Net.Respond(event, { false, TL("h26d5eb62g7380g4be3gb15eg6d85137c4fa7") })
        return
    end
    Scenario.Start(template, map)

    Net.Respond(event, { true, TL("hbc1acb0ege94fg49e5gb8f2g9f83dad0bda1", template.Name) })
end)

Net.On("Stop", function(event)
    local s = Scenario.Current()

    if not s then
        Net.Respond(event, { false, TL("hb72bdac5ge27eg48f9g8841g8e9f6a63acbd") })
        return
    end

    if s:HasStarted() and not Mod.Debug then
        Net.Respond(event, { false, TL("hf4935a60ga1c6g40f3g9c7ag06953e5824b7") })
        return
    end

    Scenario.Stop()
    Net.Respond(event, { true, TL("h2a7aafc0g7f2fg4fa9g9194g99cf33b6bbed") })
end)

Net.On("BuyUnlock", function(event)
    Net.Respond(event, { Unlock.Buy(event.Payload.Id, event:Character(), event.Payload.Character) })
end)

Net.On("ToCamp", function(event)
    if Player.Region() == C.Regions.Act0 then
        Intro.AskTutSkip()
        Net.Send("CloseGUI")
        return
    end

    if Player.InCombat() and not Mod.Debug then
        Net.Respond(event, { false, TL("he740f325gb215g4a67g8d47g3c016f651e23") })
        return
    end
    Player.ReturnToCamp()

    Net.Respond(event, { true })
end)

Net.On("ForwardCombat", function(event)
    local s = Scenario.Current()

    if not s then
        Net.Respond(event, { false, TL("hb72bdac5ge27eg48f9g8841g8e9f6a63acbd") })
        return
    end

    Scenario.ForwardCombat()

    Net.Respond(event, { true })
end)

Net.On("Teleport", function(event)
    if Player.Region() == C.Regions.Act0 then
        Intro.AskTutSkip()
        Net.Send("CloseGUI")
        return
    end

    local mapName = event.Payload.Map

    local map = table.find(Map.Get(), function(v)
        return v.Name == mapName
    end)

    if map == nil then
        Net.Respond(event, { false, TL("h2cb85222g79edg4077gb1f8gb61113da9433") })
        return
    end

    if event.Payload.Restrict and Player.InCombat() and not Mod.Debug then
        Net.Respond(event, { false, TL("he740f325gb215g4a67g8d47g3c016f651e23") })
        return
    end

    local s = Scenario.Current()

    if s and eq(map, s.Map) then
        Scenario.Teleport(event:Character())
    else
        map:Teleport(event:Character())
    end

    Net.Respond(event, { true })
end)

Net.On("WindowOpened", function(event)
    PersistentVars.GUIOpen = true
    Event.Trigger("ModActive")
    SyncState(event.PeerId)
end)
Net.On("WindowClosed", function(event)
    PersistentVars.GUIOpen = false
end)

Event.On("ScenarioStarted", function()
    Net.Send("OpenGUI", "Optional")
end)
Event.On("ScenarioMapEntered", function()
    Net.Send("CloseGUI", "Optional")
end)

Net.On("KillSpawned", function(event)
    Enemy.KillSpawned()

    Net.Respond(event, { true })
end)

Net.On("Ping", function(event)
    local target = event.Payload.Target
    if target then
        local character = event:Character()
        local x, y, z = Osi.GetPosition(target)
        Osi.RequestPing(x, y, z, target, character)
    end

    local pos = event.Payload.Pos
    if pos then
        Osi.RequestPing(pos[1], pos[2], pos[3], nil, event:Character())
    end

    Net.Respond(event, { true })
end)

Net.On("MarkSpawns", function(event)
    local mapName = event.Payload.Map
    local map = table.find(Map.Get(), function(v)
        return v.Name == mapName
    end)
    if map == nil then
        Net.Respond(event, { false, TL("h2cb85222g79edg4077gb1f8gb61113da9433") })
        return
    end

    map:VFXSpawns(table.keys(map.Spawns), 72)

    if Scenario.Current() then
        Scenario.MarkSpawns(Scenario.Current().Round + 1, 72)
    end

    Net.Respond(event, { true })
end)

Net.On("PingSpawns", function(event)
    local mapName = event.Payload.Map
    local map = table.find(Map.Get(), function(v)
        return v.Name == mapName
    end)
    if map == nil then
        Net.Respond(event, { false, TL("h2cb85222g79edg4077gb1f8gb61113da9433") })
        return
    end

    map:PingSpawns()

    Net.Respond(event, { true })
end)

local function broadcastState()
    Schedule(SyncState)
end

local function broadcastConfig()
    Schedule(function()
        local c = table.deepclone(Config)
        c.RoguelikeMode = PersistentVars.RogueModeActive
        c.HardMode = PersistentVars.HardMode
        c.SuperHardMode = PersistentVars.SuperHardMode
        c.LoneWolfMode = PersistentVars.LoneWolfMode
		c.GMMode = PersistentVars.GMMode
        c.Debug = Mod.Debug

        Net.Send("Config", c)
    end)
end

Event.On("RogueModeChanged", broadcastConfig)
Event.On("difficultyModeChanged", broadcastConfig)

Event.On("RogueModeChanged", broadcastState)
Event.On("difficultyModeChanged", broadcastState)
Event.On("ScenarioStarted", broadcastState)
Event.On("ScenarioMapEntered", broadcastState)
Event.On("ScenarioRoundStarted", broadcastState)
Event.On("ScenarioEnemyKilled", broadcastState)
Event.On("ScenarioCombatStarted", broadcastState)
Event.On("ScenarioEnded", broadcastState)
Event.On("ScenarioStopped", broadcastState)
Event.On("RogueScoreChanged", broadcastState)

Net.On("Config", function(event)
    if event:IsHost() then
        local config = event.Payload
        if config then
            if config.Default then
                config = DefaultConfig
            end

            External.ApplyConfig(config)

            if config.Persist then
                External.SaveConfig()
            end

            if config.Reset then
                External.LoadConfig()
            end

            if config.RoguelikeMode ~= nil then
                if PersistentVars.RogueModeActive ~= config.RoguelikeMode then
                    PersistentVars.RogueModeActive = config.RoguelikeMode
                    Event.Trigger("RogueModeChanged", PersistentVars.RogueModeActive)
                end
            end

            if config.HardMode ~= nil then
                PersistentVars.HardMode = config.HardMode
                if PersistentVars.HardMode == true then
                    config.SuperHardMode = false
                    PersistentVars.SuperHardMode = config.SuperHardMode
                end
                broadcastState()
            end

            if config.SuperHardMode ~= nil then
                PersistentVars.SuperHardMode = config.SuperHardMode
                if PersistentVars.SuperHardMode == true then
                    config.HardMode = false
                    PersistentVars.HardMode = config.HardMode
                end
                broadcastState()
            end

            if config.LoneWolfMode ~= nil then
                PersistentVars.LoneWolfMode = config.LoneWolfMode
				if PersistentVars.LoneWolfMode == true then
                    config.GMMode = false
                    PersistentVars.GMMode = config.GMMode
                end
                broadcastState()
			end
			
			if config.GMMode ~= nil then
				PersistentVars.GMMode = config.GMMode
				PersistentVars.GameMaster = Player.Host()
				if PersistentVars.GMMode == true then
					Player.Notify(TL("h3e1f65deg6b4ag4308gb0d2gc56ed2f0e74c", Osi.ResolveTranslatedString(Osi.GetDisplayName(PersistentVars.GameMaster))))
                    config.LoneWolfMode = false
                    PersistentVars.LoneWolfMode = config.LoneWolfMode
                end
                broadcastState()
            end
        end
    end

    broadcastConfig()
end)

Net.On("KillNearby", function(event)
    StoryBypass.ClearArea(event:Character())
end)

Net.On("ClearSurfaces", function(event)
    local s = Scenario.Current()
    if s then
        for i, guid in pairs(s.Map.Helpers) do
            WaitTicks(i, function()
                StoryBypass.ClearSurfaces(guid)
            end)
        end
    else
        StoryBypass.ClearSurfaces(event:Character())
    end

    Net.Respond(event, { true })
end)

Net.On("RemoveAllEntities", function(event)
    local count = #StoryBypass.RemoveAllEntities()
    Net.Respond(event, { true, TL("hba5a2ecbgef0fg47b9ga896g91df8ab4b3fd", count) })
end)

Net.On("RecruitOrigin", function(event)
    local name = event.Payload
    local char = table.find(C.OriginCharacters, function(v, k)
        return k == name
    end)
    if char then
        Player.RecruitOrigin(name)
        Net.Respond(event, { true, TL("h2e7ceb9cg7b29g4becg91d4gfd8af3f6dfa8", name) })
    else
        Net.Respond(event, { false, TL("hbe6d0621geb38g4537g88d5ge3512af7c173", name) })
    end
end)

Net.On("FixFactions", function(event)
    if Player.InCombat() then
        Net.Respond(event, { false, TL("h96296675gc37cg4332g8a51ga55468738776") })
    else
        for _, player in pairs(GU.DB.GetPlayers()) do
            Osi.SetFaction(player, C.CompanionFaction)
        end
        Net.Respond(event, { true })
    end
end)

Net.On("FixLongRest", function(event)
    if Player.InCombat() then
        Net.Respond(event, { false, TL("hf21d5640ga748g4031g9c12ge6573e30c475") })
    else
        Osi.DB_Camp_Unlocked(1)
        Osi.SetLongRestAvailable(1)
        Osi.SetJoinBlock(0)
        for _, player in pairs(GU.DB.GetPlayers()) do
            Osi.SetIsInDangerZone(player, 0)
            Osi.PROC_SetBlockDismiss(player, 0)
            Osi.DB_InDangerZone:Delete(player, "ENDGAME")
        end
		Osi.DB_INT_EmperorRevealed_WeakToAbsolute:Delete(1)
        Net.Respond(event, { true })
    end
end)

Net.On("CancelLongRest", function(event)
    StoryBypass.EndLongRest()
    Net.Respond(event, { true })
end)

Net.On("CancelDialog", function(event)
    local dialog, instance = Osi.SpeakerGetDialog(event:Character(), 1)

    if dialog then
        StoryBypass.CancelDialog(dialog, instance)
        Net.Respond(event, { true, TL("hbc56c73ege903g4926gb8f6g5f40dad47d62", dialog) })
    else
        Net.Respond(event, { false, TL("h214d3377g7418g4662ga127ge0044305c226") })
    end
end)

Net.On("UpdateLootFilter", function(event)
    local rarity, type, bool = table.unpack(event.Payload)
    PersistentVars.LootFilter[type][rarity] = bool

    broadcastState()
    Net.Respond(event, { true, TL("hb6e91cdbge3bcg4498ga85dga2fe8a7f80dc") })
end)

Net.On("PickupAll", function(event)
    local count = 0
    for _, rarity in pairs(C.ItemRarity) do
        count = count + Item.PickupAll(event:Character())
    end

    Net.Respond(event, { true, TL("h410f889dg145ag4ddcg8723gcbbae501e998", count) })
end)

Net.On("Pickup", function(event)
    local rarity, type = table.unpack(event.Payload)
    local count = Item.PickupAll(event:Character(), rarity, type)

    Net.Respond(event, { true, TL("h410f889dg145ag4ddcg8723gcbbae501e998", count) })
end)

Net.On("DestroyAll", function(event)
    local count = 0
    for _, rarity in pairs(C.ItemRarity) do
        count = count + Item.DestroyAll(rarity)
    end

    Net.Respond(event, { true, TL("h42fa25a1g17afg470fg871cg9169253eb34b", count) })
end)

Net.On("DestroyLoot", function(event)
    local rarity, type = table.unpack(event.Payload)
    local count = Item.DestroyAll(rarity, type)

    Net.Respond(event, { true, TL("h42fa25a1g17afg470fg871cg9169253eb34b", count) })
end)

Net.On("GetFilterableModList", function(event)
    local list = {}

    local function t(modId, modName)
        return { Id = modId, Name = modName, Blacklist = false }
    end
    for modId, modName in pairs(Item.GetModList()) do
        if not string.contains(modName, { "Gustav", "GustavDev", "Shared", "SharedDev", "Honour" }) then
            list[modId] = t(modId, modName)
        end
    end

    local filters = External.Templates.GetItemFilters()
    for _, modId in pairs(filters.Mods) do
        if not list[modId] then
            local name = TL("h2bda2046g7e8fg4751gb18eg913753acb315")
            if Ext.Mod.GetMod(modId) then
                name = Ext.Mod.GetMod(modId).Info.Directory
            end

            list[modId] = t(modId, name)
        end

        list[modId].Blacklist = true
    end

    Net.Respond(event, list)
end)

Net.On("UpdateModFilter", function(event)
    local modId, bool = table.unpack(event.Payload)
    local filters = External.Templates.GetItemFilters(true)

    if bool then
        table.insert(filters.Mods, modId)
    else
        table.removevalue(filters.Mods, modId)
    end

    External.File.Export("ItemFilters", filters)

    Item.ClearCache()

    Net.Respond(event, { true, TL("h2f73e820g7a26g4bd7g91c4g0db133e62f93") })
end)
