Loot = {}

-- TODO UI feedback
function Loot.Main(tab)
    local root = tab:AddTabItem(TL("h31b71a1eg64e2g44f4gb028g4292d20a60b0")):AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }

    if IsHost then
        local btn = root:AddButton(TL("h2dba28d2g78efg47d8gb1e8g91be13cab39c"))
        btn.IDContext = U.RandomId()
        btn.OnClick = function()
            Net.Request("PickupAll"):After(DisplayResponse)
        end

        local btn = root:AddButton(TL("h2cf955d8g79acg4008g91fcga66eb3de844c"))
        btn.IDContext = U.RandomId()
        btn.SameLine = true
        btn.OnClick = function()
            Net.Request("DestroyAll"):After(DisplayResponse)
        end
    else
        root:AddSeparatorText(TL("h501f8202g054ag4d75gb632gcb131410e931"))
    end

    Components.Layout(root, 1, 1, function(layout)
        local root = layout.Cells[1][1]:AddGroup("")

        root:AddSeparatorText(TL("h94e5715dgc1b0g4240g8a7dg6426e85f4604"))
        for _, rarity in pairs(C.ItemRarity) do
            Loot.Rarity(root, rarity, "Armor")
        end

        root:AddSeparatorText(TL("hfe76c8bdgab23g49deg8cd4g5fb8eef67d9a"))
        for _, rarity in pairs(C.ItemRarity) do
            Loot.Rarity(root, rarity, "Weapon")
        end

        root:AddSeparatorText(TL("hc777ee1dg9222g4bb4g8f44g4dd2ed666ff0"))
        for _, rarity in pairs(C.ItemRarity) do
            Loot.Rarity(root, rarity, "Object")
        end

        root:AddSeparatorText(TL("h91fd8555gc4a8g4d00g8a2cgeb66680ec944"))
        for _, rarity in pairs(C.ItemRarity) do
            Loot.Rarity(root, rarity, "CombatObject")
        end
    end)

    local ckb = Config.Checkbox(root, "h3e82a111g6bd7g4f44g80dbg192222f93b00", "hd8cafdddg8d9fg4a88g8ebfg9ceeec9dbecc", "LootIncludesCampSlot")

    root:AddSeparatorText(TL("h230707dfg7652g4528ga103g434ec321616c"))
    root:AddText(TL("h25b59712g70e0g4c24gb168g6a42134a4860"))

    Net.Request("GetFilterableModList"):After(function(event)
        local list = table.values(event.Payload)

        table.sort(list, function(a, b)
            return a.Name < b.Name
        end)
        L.Dump(list)

        for _, mod in pairs(list) do
            Loot.BlacklistMod(root, mod)
        end
    end)
end

function Loot.Rarity(root, rarity, type)
    Components.Layout(root, 2, 1, function(layout)
        local checkbox = layout.Cells[1][1]:AddCheckbox(__(rarity))
        checkbox.IDContext = U.RandomId()

        Components.Computed(checkbox, function(_, state)
            return state and state.LootFilter[type] and state.LootFilter[type][rarity]
        end, "StateChange", "Checked")

        checkbox.OnChange = function(ckb)
            if not IsHost then
                ckb.Checked = not ckb.Checked
                return
            end
            Net.Request("UpdateLootFilter", { rarity, type, ckb.Checked }):After(DisplayResponse)
        end

        local btn = layout.Cells[1][2]:AddButton(TL("h243c04feg7169g451agb170gf37cd352d15e"))
        btn.IDContext = U.RandomId()
        btn.OnClick = function()
            Net.Request("Pickup", { rarity, type }):After(DisplayResponse)
        end

        local btn2 = layout.Cells[1][2]:AddButton(TL("h254298eeg7017g4cdbgb167g1abdd345389f"))
        btn2.IDContext = U.RandomId()
        btn2.SameLine = true
        btn2.OnClick = function()
            Net.Request("DestroyLoot", { rarity, type }):After(DisplayResponse)
        end
    end)
end

function Loot.BlacklistMod(root, mod)
    local checkbox = root:AddCheckbox(mod.Name .. " - " .. mod.Id)
    checkbox.IDContext = U.RandomId()
    checkbox.OnChange = function(ckb)
        if not IsHost then
            ckb.Checked = not ckb.Checked
            return
        end

        Net.Request("UpdateModFilter", { mod.Id, ckb.Checked }):After(DisplayResponse)
    end

    checkbox.Checked = mod.Blacklist
end
