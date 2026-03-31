ArchipelagoClient = {}
local DEFAULT_SERVER_ADDRESS = "archipelago.gg:"

local AP_STATUS_COLORS = {
    offline = { 0.75, 0.75, 0.75, 1.0 },
    disconnected = { 0.85, 0.85, 0.85, 1.0 },
    connecting = { 1.0, 0.82, 0.25, 1.0 },
    connected = { 0.4, 1.0, 0.4, 1.0 },
    error = { 1.0, 0.4, 0.4, 1.0 },
}

ArchipelagoClient.Settings = UT.Proxy(
    table.merge({ ServerAddress = DEFAULT_SERVER_ADDRESS, SlotName = "" }, IO.LoadJson("ArchipelagoClientConfig.json") or {}),
    function(value, _, raw)
        Schedule(function()
            IO.SaveJson("ArchipelagoClientConfig.json", {
                ServerAddress = raw.ServerAddress,
                SlotName = raw.SlotName,
            })
        end)

        return value
    end
)

if tostring(ArchipelagoClient.Settings.ServerAddress or "") == "" then
    ArchipelagoClient.Settings.ServerAddress = DEFAULT_SERVER_ADDRESS
end

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
        return __("Archipelago runtime not detected. Start `Baldur's Gate 3 - ToT` from the Archipelago launcher.")
    end

    return __("Archipelago client idle.")
end

local function build_detail_lines(apState)
    local lines = {}
    local room = tostring(apState.server_address or "")
    local slotName = tostring(apState.slot_name or "")
    local seedName = tostring(apState.seed_name or "")

    if room ~= "" then
        table.insert(lines, __("Room: %s", room))
    end
    if slotName ~= "" then
        table.insert(lines, __("Slot: %s", slotName))
    end
    if seedName ~= "" then
        table.insert(lines, __("Seed: %s", seedName))
    end

    table.insert(lines, __("Checks sent: %d", tonumber(apState.locations_checked or 0) or 0))
    table.insert(lines, __("Items received: %d", tonumber(apState.items_received or 0) or 0))
    table.insert(lines, __("DeathLink: %s", apState.death_link_enabled and "On" or "Off"))

    local lastError = tostring(apState.last_error or "")
    if lastError ~= "" then
        table.insert(lines, __("Last error: %s", lastError))
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
        return __("No Archipelago log lines yet.")
    end

    return table.concat(lines, "\n")
end

---@param tab ExtuiTabBar
function ArchipelagoClient.Main(tab)
    local root = tab:AddTabItem(__("Archipelago Client")):AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }

    root:AddSeparatorText(__("Status"))
    local statusText = root:AddText("")
    local detailText = root:AddText("")
    root:AddDummy(1, 4)

    root:AddSeparatorText(__("Connection"))
    if not IsHost then
        root:AddText(__("Only the host can connect or disconnect the Archipelago client."))
    end

    local roomInput = root:AddInputText(__("Room address"))
    roomInput.Text = tostring(ArchipelagoClient.Settings.ServerAddress or "")
    roomInput.OnChange = function(input)
        ArchipelagoClient.Settings.ServerAddress = input.Text
    end

    local slotInput = root:AddInputText(__("Slot name"))
    slotInput.Text = tostring(ArchipelagoClient.Settings.SlotName or "")
    slotInput.OnChange = function(input)
        ArchipelagoClient.Settings.SlotName = input.Text
    end

    local passwordInput = root:AddInputText(__("Password"))
    local passwordDraft = ""
    passwordInput.OnChange = function(input)
        passwordDraft = input.Text
    end

    root:AddText(__("Room and slot are stored locally on this client. Password is kept for this session only."))
    root:AddText(__("The Archipelago launcher no longer opens a separate ToT client window. Start `Baldur's Gate 3 - ToT`, then connect here."))

    local connectButton = root:AddButton(__("Connect"))
    connectButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "connect",
            server_address = roomInput.Text,
            slot_name = slotInput.Text,
            password = passwordDraft,
        }):After(DisplayResponse)
    end

    local disconnectButton = root:AddButton(__("Disconnect"))
    disconnectButton.SameLine = true
    disconnectButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "disconnect",
        }):After(DisplayResponse)
    end

    local resyncButton = root:AddButton(__("Resync"))
    resyncButton.SameLine = true
    resyncButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "resync",
        }):After(DisplayResponse)
    end

    local clearLogButton = root:AddButton(__("Clear Log"))
    clearLogButton.SameLine = true
    clearLogButton.OnClick = function()
        Net.Request("ArchipelagoClientCommand", {
            command = "clear_log",
        }):After(DisplayResponse)
    end

    root:AddSeparatorText(__("Logs"))
    local scrollable = root:AddChildWindow(U.RandomId())
    local logText = scrollable:AddText(__("No Archipelago log lines yet."))

    local function refresh(state)
        local apState = (state and state.ArchipelagoClientState) or current_state()
        statusText.Label = build_status_label(apState)
        statusText:SetColor("Text", status_color(apState))
        detailText.Label = build_detail_lines(apState)
        logText.Label = build_log_text(apState)
    end

    Event.On("StateChange", refresh):Exec(State)
end
