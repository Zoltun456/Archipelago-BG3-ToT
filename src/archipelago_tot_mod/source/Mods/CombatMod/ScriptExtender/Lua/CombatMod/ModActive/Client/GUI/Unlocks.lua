ClientUnlock = {}

local function archipelago_shop_connected(state)
    local current_state = state or State or {}
    local ap_state = current_state.ArchipelagoClientState or {}
    if ap_state.bridge_stale then
        return false
    end

    return tostring(ap_state.connection_state or "") == "connected"
end


local function unlock_layout_signature(unlocks)
    local parts = {}
    for index, unlock in ipairs(table.values(unlocks or {})) do
        parts[index] = string.format("%03d:%s", index, tostring(unlock.Id or ""))
    end
    return table.concat(parts, "|")
end


local function build_unlock_layout(root, unlocks)
    local cols = 3
    local nrows = math.ceil(table.size(unlocks) / cols)
    return Components.Layout(root, cols, nrows, function(layout)
        layout.Table.Borders = true
        layout.Table.ScrollY = true
        for i, unlock in ipairs(table.values(unlocks)) do
            local c = (i - 1) % cols
            local r = math.ceil(i / cols)
            local cell = layout.Cells[r][c + 1]
            ClientUnlock.Tile(cell, unlock)
        end
    end)
end


---@param tab ExtuiTabBar
function ClientUnlock.Main(tab)
    ---@type ExtuiTabItem
    local root = tab:AddTabItem(TL("h231a0e4eg764fg45b1gb102g93d7d320b1f5"))
    root.Visible = false

    Components.Computed(root:AddSeparatorText(TL("h16af0aafg43fag45ffga259gc399c07be1bb", 0, 0)), function(root, state)
        return TL("h16af0aafg43fag45ffga259gc399c07be1bb", state.Currency, state.RogueScore or 0)
    end, "StateChange")

    local layout
    local layout_signature = ""
    Event.On("StateChange", function(state)
        local shop_connected = archipelago_shop_connected(state)
        root.Visible = shop_connected
        if not shop_connected then
            layout_signature = ""
            if layout and layout.Table then
                layout.Table:Destroy()
            end
            layout = nil
            return
        end

        local unlocks = state.Unlocks or {}
        if table.size(unlocks) == 0 then
            return
        end

        local next_signature = unlock_layout_signature(unlocks)
        if layout and layout_signature == next_signature then
            return
        end

        layout_signature = next_signature
        if layout and layout.Table then
            layout.Table:Destroy()
        end
        layout = build_unlock_layout(root, unlocks)
    end):Exec(State)
end


function ClientUnlock.GetStock(unlock)
    local stock = unlock.Amount - unlock.Bought
    if stock > 0 then
        local text = TL("h3e9c6432g6bc9g4316gb0dagf57012f8d752", unlock.Amount - unlock.Bought .. "/" .. unlock.Amount)

        if unlock.Persistent then
            text = string.format("%s (%s)", text, TL("h255ed026g700bg4857gb166gde315344fc13"))
        end

        return text
    end
    if unlock.Persistent then
        return TL("h270f8076g725ag4d52gb143gcb345361e916")
    end
    return TL("h298720feg7cd2g475agb1abg413cd389631e")
end


function ClientUnlock.Tile(root, unlock)
    local grp = root:AddGroup(unlock.Id)

    local icon = grp:AddImage(unlock.Icon, { 64, 64 })
    if unlock.Description then
        ---@type ExtuiTooltip
        local t = icon:Tooltip()
        t:SetStyle("WindowPadding", 30, 10)
        t:AddText(unlock.Description)
    end

    local col2 = grp:AddGroup(unlock.Id)
    col2.SameLine = true
    local cost = col2:AddText(TL("h38df043eg6d8ag4516gb0begc370d29ce152", unlock.Cost))

    local buyLabel = col2:AddText("")

    if unlock.Amount ~= nil then
        local amount = Components.Computed(buyLabel, function(root, unlock)
            return ClientUnlock.GetStock(unlock)
        end)
        amount.Update(unlock)

        Event.On("StateChange", function(state)
            for _, new in pairs(state.Unlocks) do
                if new.Id == unlock.Id then
                    amount.Update(new)
                end
            end
        end):Exec(State)
    end

    grp:AddSeparator()

    local text = grp:AddText(unlock.Name)
    if unlock.Description then
        local t = text:Tooltip()
        t:SetStyle("WindowPadding", 30, 10)
        t:AddText(unlock.Description)
    end

    grp:AddSeparator()
    do
        local unlock = unlock

        local bottomText = grp:AddText("")
        local function checkVisable()
            bottomText.Visible = not unlock.Unlocked and unlock.Bought < 1
        end
        checkVisable()

        if unlock.Requirement then
            if type(unlock.Requirement) ~= "table" then
                unlock.Requirement = { unlock.Requirement }
            end

            for _, req in pairs(unlock.Requirement) do
                if type(req) == "number" then
                    bottomText.Label = bottomText.Label .. TL("h8c0d708fgd958g425dgabf3ge43bc9d1c619", req) .. "\n"
                elseif type(req) == "string" then
                    local u = table.find(State.Unlocks, function(u)
                        return u.Id == req
                    end)
                    if u then
                        bottomText.Label = bottomText.Label .. TL("h28bc4630g7de9g4136g91b8gf750339ad572", u.Name) .. "\n"
                    end
                end
            end
        end

        grp:AddDummy(1, 2)

        local cond = Components.Conditional(grp, function()
            if unlock.Character then
                return ClientUnlock.BuyChar(grp, unlock)
            end

            return ClientUnlock.Buy(grp, unlock)
        end)
        cond.Update(unlock.Unlocked)

        Event.On("StateChange", function(state)
            for _, new in pairs(state.Unlocks) do
                if new.Id == unlock.Id then
                    unlock = new
                    cond.Update(unlock.Unlocked)
                    checkVisable()
                end
            end
        end):Exec(State)
    end
end


function ClientUnlock.Buy(root, unlock)
    local grp = root:AddGroup(U.RandomId())

    ---@type ExtuiButton
    local btn = grp:AddButton(TL("h322023aeg6775g476fgb011g3109d233132b"))
    btn.IDContext = U.RandomId()
    btn.Label = string.format("    %s    ", TL("h322023aeg6775g476fgb011g3109d233132b"))

    if unlock.Amount ~= nil then
        Event.On("StateChange", function(state)
            for _, new in pairs(state.Unlocks) do
                if new.Id == unlock.Id then
                    btn.Visible = new.Bought < new.Amount
                    return
                end
            end
        end):Exec(State)
    end

    btn.OnClick = function()
        btn:SetStyle("Alpha", 0.2)
        Net.Request("BuyUnlock", { Id = unlock.Id }):After(function(event)
            local ok, res = table.unpack(event.Payload)

            if not ok then
                Event.Trigger("Error", res)
            else
                Event.Trigger("Success", TL("h2308c823g765dg49d7ga103gbfb103219d93", unlock.Name))
            end
            btn:SetStyle("Alpha", 1)
        end)
    end

    grp:AddText("").SameLine = true

    grp:AddDummy(1, 2)

    return grp
end


function ClientUnlock.GetCharacters()
    local characters = table.values(GE.GetPCs())

    table.sort(characters, function(a, b)
        return a.Uuid.EntityUuid < b.Uuid.EntityUuid
    end)

    return characters
end


function ClientUnlock.BuyChar(root, unlock)
    local grp = root:AddGroup(U.RandomId())

    ---@type ExtuiButton
    local btn = grp:AddButton(TL("h322023aeg6775g476fgb011g3109d233132b"))
    btn.IDContext = U.RandomId()
    btn.Label = string.format("    %s    ", TL("h322023aeg6775g476fgb011g3109d233132b"))

    ---@type ExtuiPopup
    local popup = grp:AddPopup("")
    popup.IDContext = U.RandomId()
    popup:AddSeparatorText(TL("h2cb33b1dg79e6g46e4g81f8g0082e3da22a0"))

    local list = {}
    local function createPopup(unlock)
        for _, b in pairs(list) do
            b:Destroy()
        end
        list = {}

        for i, u in ipairs(ClientUnlock.GetCharacters()) do
            local name
            if u.CustomName then
                name = u.CustomName.Name
            else
                name = Localization.Get(u.DisplayName.NameKey.Handle.Handle)
            end

            local uuid = u.Uuid.EntityUuid

            ---@type ExtuiButton
            local b = popup:AddButton("")
            b.IDContext = U.RandomId()
            b.Label = string.format("%s", name)
            table.insert(list, b)
            b.Size = { 200, 0 }

            local ping = popup:AddButton("")
            ping.IDContext = U.RandomId()
            ping.Label = TL("h37333c06g6266g4695gb040g00f3526222d1")
            ping.OnClick = function()
                Net.Send("Ping", { Target = uuid })
            end
            ping.SameLine = true
            table.insert(list, ping)

            if unlock.BoughtBy[uuid] then
                b.Label = string.format("%s (%s)", name, TL("h22c9bc4eg779cg4e91gb11fga8f7d33d8ad5"))

                -- b:SetStyle("Alpha", 0.5)
            end

            b.Label = string.format("  %s  ", b.Label)

            b.OnClick = function()
                b:SetStyle("Alpha", 0.2)
                Net.Request("BuyUnlock", { Id = unlock.Id, Character = uuid }):After(function(event)
                    local ok, res = table.unpack(event.Payload)

                    if not ok then
                        Event.Trigger("Error", res)
                    else
                        Event.Trigger("Success", TL("hd0c773c3g8592g4269gae3fg440f0c1d662d", unlock.Name, name))
                    end

                    -- might not exist anymore
                    pcall(function()
                        b:SetStyle("Alpha", 1)
                    end)
                end)
            end
        end
    end

    Event.On("StateChange", function(state)
        for _, new in pairs(state.Unlocks) do
            if new.Id == unlock.Id then
                local buyable = new.Amount == nil or new.Bought < new.Amount
                btn.Visible = buyable

                popup.Visible = buyable
                createPopup(new)
                return
            end
        end
    end):Exec(State)

    btn.OnClick = function()
        popup:Open()
    end

    grp:AddText("").SameLine = true

    grp:AddDummy(1, 2)

    return grp
end
