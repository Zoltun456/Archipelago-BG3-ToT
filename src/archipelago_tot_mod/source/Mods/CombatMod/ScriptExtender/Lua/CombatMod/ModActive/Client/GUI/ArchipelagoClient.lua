ArchipelagoClient = {}
local DEFAULT_SERVER_ADDRESS = "archipelago.gg:"

local AP_STATUS_COLORS = {
    offline = { 0.75, 0.75, 0.75, 1.0 },
    disconnected = { 0.85, 0.85, 0.85, 1.0 },
    connecting = { 1.0, 0.82, 0.25, 1.0 },
    connected = { 0.4, 1.0, 0.4, 1.0 },
    error = { 1.0, 0.4, 0.4, 1.0 },
}

ArchipelagoClient.Settings = {
    ServerAddress = DEFAULT_SERVER_ADDRESS,
    SlotName = "",
}

local function clear_persisted_connection_settings()
    Schedule(function()
        IO.SaveJson("ArchipelagoClientConfig.json", {
            ServerAddress = DEFAULT_SERVER_ADDRESS,
            SlotName = "",
        })
    end)
end

local function reset_connection_form()
    ArchipelagoClient.Settings.ServerAddress = DEFAULT_SERVER_ADDRESS
    ArchipelagoClient.Settings.SlotName = ""
    clear_persisted_connection_settings()
    Event.Trigger("ArchipelagoClientFormReset", {
        ServerAddress = DEFAULT_SERVER_ADDRESS,
        SlotName = "",
    })
end

reset_connection_form()
GameState.OnLoad(reset_connection_form)
GameState.OnUnload(reset_connection_form)

local function current_state()
    local state = State or {}
    local apState = state.ArchipelagoClientState or {}
    return apState
end

local function status_color(apState)
    if apState.bridge_stale then
        return AP_STATUS_COLORS.offline
    end

    local connectionState = tostring(apState.connection_state or "offline")
    return AP_STATUS_COLORS[connectionState] or AP_STATUS_COLORS.offline
end

local function build_status_label(apState)
    local text = tostring(apState.status_text or "")
    if text ~= "" then
        return text
    end

    if apState.bridge_stale then
        return TL("h48ec300ag1db9g4655gb7bdgf033959fd211")
    end

    return TL("h28925ddeg7dc7g4088gb1bag16eed39834cc")
end

local function build_detail_lines(apState)
    local lines = {}
    local room = tostring(apState.server_address or "")
    local slotName = tostring(apState.slot_name or "")
    local seedName = tostring(apState.seed_name or "")
    local connectionState = tostring(apState.connection_state or "offline")

    if apState.bridge_stale or connectionState == "offline" then
        table.insert(lines, TL("h55a72833g00f2g47d6ga669g41b0044b6392"))
        table.insert(lines, TL("h9a29f3c8gcf7cg4a69g9a91gac0fb8b38e2d"))
    end

    if room ~= "" then
        table.insert(lines, TL("h38c0165eg6d95g4430gb0bfg3256d29d1074", room))
    end
    if slotName ~= "" then
        table.insert(lines, TL("h390f045eg6c5ag4510gb0a3gc376d281e154", slotName))
    end
    if seedName ~= "" then
        table.insert(lines, TL("h3f4f248eg6a1ag471dgb0c7gc17bd2e5e359", seedName))
    end

    table.insert(lines, TL("h2fd23e33g7a87g46b6ga1ceg10d003ec32f2", tonumber(apState.locations_checked or 0) or 0))
    table.insert(lines, TL("h34bdbce7g61e8g4e9bga078ge8fd425acadf", tonumber(apState.items_received or 0) or 0))
    table.insert(
        lines,
        TL(
            "h3e15a8a0g6b40g4fdfg90d2g69b932f04b9b",
            apState.death_link_enabled and TL("h31f326aeg64a6g473fgb02cg0159d20e237b")
                or TL("h37f322c6g62a6g4779gb04cg011f526e233d")
        )
    )

    local lastError = tostring(apState.last_error or "")
    if lastError ~= "" then
        table.insert(lines, TL("h2bf6eed8g7ea3g4bb8g918cg5ddeb3ae7ffc", lastError))
    end

    return table.concat(lines, "\n")
end

local function build_log_text(apState)
    local rawLines = apState.log_lines or {}
    local lines = {}

    for _, entry in ipairs(rawLines) do
        if type(entry) == "table" then
            local timestamp = tostring(entry.timestamp or "")
            local text = tostring(entry.text or entry.message or "")
            if text ~= "" then
                if timestamp ~= "" then
                    table.insert(lines, string.format("[%s] %s", timestamp, text))
                else
                    table.insert(lines, text)
                end
            end
        elseif entry ~= nil then
            local text = tostring(entry)
            if text ~= "" then
                table.insert(lines, text)
            end
        end
    end

    if #lines == 0 then
        return TL("h01c821efg549dg474bga32fgb12dc10d930f")
    end

    return table.concat(lines, "\n")
end

---@param tab ExtuiTabBar
function ArchipelagoClient.Main(tab)
    local root = tab:AddTabItem(TL("h2ec6a75eg7b93g4f20gb1dfg5946d3fd7b64")):AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }

    root:AddSeparatorText(TL("h21911aeeg74c4g44fbgb12ag229dd30800bf"))
    local statusText = root:AddText("")
    local detailText = root:AddText("")
    root:AddDummy(1, 4)

    root:AddSeparatorText(TL("h29ae997ag7cfbg4cc2gb1a9gdaa4938bf886"))
    if not IsHost then
        root:AddText(TL("hcce399e2g99b6g4ccbgbffdg0aad1ddf288f"))
    end

    local roomInput = root:AddInputText(TL("h29e28ae6g7cb7g4dfbgb1adg1b9d538f39bf"))
    roomInput.Text = tostring(ArchipelagoClient.Settings.ServerAddress or "")
    roomInput.OnChange = function(input)
        ArchipelagoClient.Settings.ServerAddress = input.Text
    end

    local slotInput = root:AddInputText(TL("h237e812eg762bg4d47gb104gdb21d326f903"))
    slotInput.Text = tostring(ArchipelagoClient.Settings.SlotName or "")
    slotInput.OnChange = function(input)
        ArchipelagoClient.Settings.SlotName = input.Text
    end

    local passwordInput = root:AddInputText(TL("h2643860ag7316g4d35gb157g0b5393752971"))
    pcall(function()
        passwordInput.Password = true
    end)
    pcall(function()
        passwordInput.NoUndoRedo = true
    end)
    pcall(function()
        passwordInput.AutoSelectAll = false
    end)
    local passwordDraft = ""
    passwordInput.OnChange = function(input)
        passwordDraft = input.Text
    end

    root:AddText(TL("hf42a12e9ga17fg447bg8c71g921dae53b03f"))
    root:AddText(TL("hc701aedfg9254g4fb8gaf43g29decd610bfc"))
    root:AddText(TL("h202a0f80g757fg45adg9131g93cb3313b1e9"))

    local connectButton = root:AddButton(TL("h20490c7ag751cg4592gb137ga3f4931581d6"))
    connectButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "connect",
            server_address = roomInput.Text,
            slot_name = slotInput.Text,
            password = passwordDraft,
        }):After(DisplayResponse)
    end

    local disconnectButton = root:AddButton(TL("h2e67a71ag7b32g4f24gb1d5g494293f76b60"))
    disconnectButton.SameLine = true
    disconnectButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "disconnect",
        }):After(DisplayResponse)
    end

    local resyncButton = root:AddButton(TL("h27dae07eg728fg4b52gb14eg9d34d36cbf16"))
    resyncButton.SameLine = true
    resyncButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "resync",
        }):After(DisplayResponse)
    end

    local clearLogButton = root:AddButton(TL("h39462a12g6c13g47f4gb0a7g5192128573b0"))
    clearLogButton.SameLine = true
    clearLogButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "clear_log",
        }):After(DisplayResponse)
    end

    root:AddSeparatorText(TL("h31b714deg64e2g4418gb028g427ed20a605c"))
    local scrollable = root:AddChildWindow(U.RandomId())
    local logText = scrollable:AddText(TL("h01c821efg549dg474bga32fgb12dc10d930f"))

    local function refresh_form(formState)
        local nextState = formState or {}
        roomInput.Text = tostring(nextState.ServerAddress or DEFAULT_SERVER_ADDRESS)
        slotInput.Text = tostring(nextState.SlotName or "")
        passwordDraft = ""
        passwordInput.Text = ""
    end

    local function refresh(state)
        local apState = (state and state.ArchipelagoClientState) or current_state()
        statusText.Label = build_status_label(apState)
        statusText:SetColor("Text", status_color(apState))
        detailText.Label = build_detail_lines(apState)
        logText.Label = build_log_text(apState)
    end

    Event.On("ArchipelagoClientFormReset", refresh_form)
    refresh_form(ArchipelagoClient.Settings)
    Event.On("StateChange", refresh):Exec(State)
end
