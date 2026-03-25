local patched = false


local function show_unlock(unlock)
    if not unlock or not unlock.Id then
        return false
    end

    if unlock.Id == "QUICKSTART" then
        return true
    end

    return string.sub(unlock.Id, 1, 9) == "APCHECK::"
end


local function ensure_base_unlock_gui_loaded()
    if ClientUnlock and ClientUnlock.Tile and ClientUnlock.Main then
        return true
    end

    local ok = false
    if Require then
        ok = pcall(Require, "CombatMod/ModActive/Client/GUI/Unlocks")
    end

    if not ok and Ext and Ext.Require then
        ok = pcall(Ext.Require, "CombatMod/ModActive/Client/GUI/Unlocks.lua")
    end

    if not ok then
        return false
    end

    return ClientUnlock and ClientUnlock.Tile and ClientUnlock.Main
end


local function patch_unlock_ui()
    if patched or not ensure_base_unlock_gui_loaded() then
        return
    end

    ClientUnlock.Main = function(tab)
        local root = tab:AddTabItem(__("Unlocks"))

        Components.Computed(root:AddSeparatorText(__("Currency owned: %d   RogueScore: %d", 0, 0)), function(_, state)
            return __("Currency owned: %d   RogueScore: %d", state.Currency, state.RogueScore or 0)
        end, "StateChange")

        local handler
        handler = Event.On("StateChange", function(state)
            local unlocks = table.filter(state.Unlocks or {}, function(unlock)
                return show_unlock(unlock)
            end)

            if table.size(unlocks) == 0 then
                return
            end

            handler:Unregister()

            local cols = 3
            local nrows = math.ceil(table.size(unlocks) / cols)
            Components.Layout(root, cols, nrows, function(layout)
                layout.Table.Borders = true
                layout.Table.ScrollY = true
                for i, unlock in ipairs(table.values(unlocks)) do
                    local c = (i - 1) % cols
                    local r = math.ceil(i / cols)
                    local cell = layout.Cells[r][c + 1]
                    ClientUnlock.Tile(cell, unlock)
                end
            end)
        end)
    end

    patched = true
end


patch_unlock_ui()
Ext.Events.SessionLoaded:Subscribe(patch_unlock_ui)
