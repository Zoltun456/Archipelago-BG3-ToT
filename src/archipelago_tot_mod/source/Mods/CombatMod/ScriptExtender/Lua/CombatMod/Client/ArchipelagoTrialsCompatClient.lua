-- This whole file used to be split between the old standalone bridge UI and the newer CombatMod patch.
-- I merged it here so there is exactly one client-side place that owns the AP shop tiles and notifications.

local patched = false
local original_get_stock = nil

local GOAL_UNLOCK_ID = "APGOAL::QUICKSTART"
local PIXIE_BLESSING_UNLOCK_ID = "APLOCAL::PIXIE_BLESSING"
local AP_LOCAL_SHOP_SECTION_NAME = "Local Unlocks"
local SHOP_SECTION_UNLOCK_PREFIX = "APSHOP::SECTION::"
local AP_ATLAS_TEXTURE_UUID = "aa417c69-e69a-f1ef-5a8d-65b7b5d4e195"
local AP_CLIENT_DEBUG_SHOP_FILE = "ap_debug_shop_client.json"
local AP_ICON_UVS = {
    ["original-logo"] = {
        { 0.0009765625, 0.0009765625 },
        { 0.12402344, 0.12402344 },
    },
    ["ap_trials_icon_blue_001"] = {
        { 0.1259765625, 0.0009765625 },
        { 0.24902344, 0.12402344 },
    },
    ["ap_trials_icon_color_001"] = {
        { 0.2509765625, 0.0009765625 },
        { 0.37402344, 0.12402344 },
    },
}

local AP_NOTIFICATION_DEFAULT_DURATION = 6
local AP_NOTIFICATION_FADE_DURATION = 2
local AP_NOTIFICATION_MAX_VISIBLE = 5
local AP_NOTIFICATION_WINDOW_SIZE = { 1100, 240 }
local AP_NOTIFICATION_ANCHOR_X = 200
local AP_NOTIFICATION_ANCHOR_BOTTOM_Y = 930
local AP_NOTIFICATION_ROW_HEIGHT = 26
local AP_NOTIFICATION_ROW_GAP = 2
local AP_NOTIFICATION_VERTICAL_PADDING = 32
local AP_NOTIFICATION_COLORS = {
    black = { 0.0, 0.0, 0.0, 1.0 },
    red = { 0.933, 0.0, 0.0, 1.0 },
    green = { 0.0, 1.0, 0.498, 1.0 },
    yellow = { 0.98, 0.98, 0.824, 1.0 },
    blue = { 0.392, 0.584, 0.929, 1.0 },
    magenta = { 0.933, 0.0, 0.933, 1.0 },
    cyan = { 0.0, 0.933, 0.933, 1.0 },
    slateblue = { 0.427, 0.545, 0.909, 1.0 },
    plum = { 0.686, 0.6, 0.937, 1.0 },
    salmon = { 0.98, 0.502, 0.447, 1.0 },
    white = { 1.0, 1.0, 1.0, 1.0 },
    orange = { 1.0, 0.467, 0.0, 1.0 },
}

local ap_notification_window = nil
local ap_notification_content = nil
local ap_notification_queue = {}
local ap_active_notifications = {}
local ap_notification_tick_hooked = false


local function stringify(value)
    if value == nil then
        return ""
    end

    return tostring(value)
end


local function save_debug_object(path, data)
    Ext.IO.SaveFile(path, Ext.Json.Stringify(data))
end


local function unlock_id_list(unlocks)
    local ids = {}
    for _, unlock in ipairs(unlocks or {}) do
        table.insert(ids, stringify(unlock and unlock.Id))
    end
    return ids
end


local function write_shop_debug_snapshot(stage, state, visible_unlocks)
    local all_unlocks = table.values((state and state.Unlocks) or {})
    save_debug_object(AP_CLIENT_DEBUG_SHOP_FILE, {
        stage = stringify(stage),
        generated_at = Ext.Utils.MonotonicTime(),
        total_unlock_count = table.size((state and state.Unlocks) or {}),
        visible_unlock_count = table.size(visible_unlocks or {}),
        total_unlock_ids = unlock_id_list(all_unlocks),
        visible_unlock_ids = unlock_id_list(visible_unlocks),
        has_goal_unlock = table.find(all_unlocks, function(unlock)
            return stringify(unlock and unlock.Id) == GOAL_UNLOCK_ID
        end) ~= nil,
        has_pixie_unlock = table.find(all_unlocks, function(unlock)
            return stringify(unlock and unlock.Id) == PIXIE_BLESSING_UNLOCK_ID
        end) ~= nil,
        pixie_visible = table.find(visible_unlocks or {}, function(unlock)
            return stringify(unlock and unlock.Id) == PIXIE_BLESSING_UNLOCK_ID
        end) ~= nil,
        has_moonshield_unlock = table.find(all_unlocks, function(unlock)
            return stringify(unlock and unlock.Id) == "Moonshield"
        end) ~= nil,
    })
end


local function notification_color(color_name, alpha)
    local base = AP_NOTIFICATION_COLORS[tostring(color_name or "")] or AP_NOTIFICATION_COLORS.white
    return {
        base[1],
        base[2],
        base[3],
        (tonumber(alpha) or 1.0) * (base[4] or 1.0),
    }
end


local function update_ap_notification_window_anchor(window, active_notifications)
    if not window or not window.SetPos then
        return
    end

    -- This popup reads better when it hugs the lower-left and grows upward.
    -- We estimate the current height and move the window up so the bottom row
    -- stays anchored near the same spot instead of marching toward the middle.
    local row_count = math.max(1, #(active_notifications or {}))
    local estimated_height = AP_NOTIFICATION_VERTICAL_PADDING
        + (row_count * AP_NOTIFICATION_ROW_HEIGHT)
        + (math.max(0, row_count - 1) * AP_NOTIFICATION_ROW_GAP)
    window:SetPos({ AP_NOTIFICATION_ANCHOR_X, AP_NOTIFICATION_ANCHOR_BOTTOM_Y - estimated_height })
end


local function ensure_ap_notification_window()
    if ap_notification_window then
        return ap_notification_window
    end
    if not Ext or not Ext.IMGUI or not Ext.IMGUI.NewWindow then
        return nil
    end

    ap_notification_window = Ext.IMGUI.NewWindow("Archipelago Notifications")
    ap_notification_window:SetSize(AP_NOTIFICATION_WINDOW_SIZE)
    ap_notification_window.Open = true
    ap_notification_window.Visible = false
    ap_notification_window.Closeable = false
    ap_notification_window.NoFocusOnAppearing = true

    pcall(function()
        ap_notification_window:SetStyle("Alpha", 0.85)
        ap_notification_window:SetStyle("WindowPadding", 24, 14)
    end)
    pcall(function()
        ap_notification_window.NoDecoration = true
        ap_notification_window.NoSavedSettings = true
        ap_notification_window.NoMove = true
        ap_notification_window.NoInputs = true
        ap_notification_window.AlwaysAutoResize = true
        update_ap_notification_window_anchor(ap_notification_window, {})
    end)

    return ap_notification_window
end


local function clear_ap_notification_content()
    if ap_notification_content then
        ap_notification_content:Destroy()
        ap_notification_content = nil
    end
end


local function hide_ap_notification()
    clear_ap_notification_content()
    if ap_notification_window then
        ap_notification_window.Visible = false
    end
end


local function render_ap_notifications(active_notifications, now)
    local window = ensure_ap_notification_window()
    if not window then
        return
    end

    update_ap_notification_window_anchor(window, active_notifications)
    clear_ap_notification_content()
    ap_notification_content = window:AddGroup(U.RandomId())

    for row_index, notification in ipairs(active_notifications or {}) do
        local row = ap_notification_content:AddGroup(U.RandomId())
        local fade_alpha = 1.0
        if now >= (notification.display_until or 0) then
            local remaining = math.max(0, (notification.remove_at or 0) - now)
            fade_alpha = math.max(0, math.min(1, remaining / (AP_NOTIFICATION_FADE_DURATION * 1000)))
        end

        local segments = notification.segments or {}
        if type(segments) ~= "table" or #segments == 0 then
            segments = {
                { text = tostring(notification.text or "") },
            }
        end

        for index, segment in ipairs(segments) do
            local node = row:AddText(tostring(segment.text or ""))
            node.SameLine = index > 1
            node:SetColor("Text", notification_color(segment.color, fade_alpha))
        end

        if row_index < #active_notifications then
            ap_notification_content:AddDummy(1, 2)
        end
    end

    window.Visible = true
    window.Open = true
end


local function advance_ap_notification_queue()
    local now = Ext.Utils.MonotonicTime()

    for index = #ap_active_notifications, 1, -1 do
        if now >= (ap_active_notifications[index].remove_at or 0) then
            table.remove(ap_active_notifications, index)
        end
    end

    while #ap_active_notifications < AP_NOTIFICATION_MAX_VISIBLE and #ap_notification_queue > 0 do
        local next_notification = table.remove(ap_notification_queue, 1)
        local duration = tonumber(next_notification.duration or AP_NOTIFICATION_DEFAULT_DURATION)
            or AP_NOTIFICATION_DEFAULT_DURATION
        duration = math.max(0.5, duration)
        next_notification.display_until = now + duration * 1000
        next_notification.remove_at = next_notification.display_until + AP_NOTIFICATION_FADE_DURATION * 1000
        table.insert(ap_active_notifications, next_notification)
    end

    if #ap_active_notifications == 0 then
        hide_ap_notification()
        return
    end

    render_ap_notifications(ap_active_notifications, now)
end


local function sync_notification_location_segment(payload)
    if type(payload) ~= "table" then
        return
    end

    local text = tostring(payload.text or "")
    local segments = payload.segments
    if text == "" or type(segments) ~= "table" or #segments == 0 then
        return
    end

    local location_text = string.match(text, "%(([^()]*)%)")
    if not location_text then
        return
    end

    for _, segment in ipairs(segments) do
        if tostring(segment.color or "") == "green" then
            segment.text = location_text
            return
        end
    end
end


local function queue_ap_notification(payload)
    if type(payload) ~= "table" then
        payload = { text = tostring(payload or "") }
    end

    local text = tostring(payload.text or "")
    local segments = payload.segments
    local has_segments = type(segments) == "table" and #segments > 0
    if has_segments then
        sync_notification_location_segment(payload)
        segments = payload.segments
    end
    if text == "" and not has_segments then
        return
    end

    table.insert(ap_notification_queue, payload)
    advance_ap_notification_queue()
end


local function reset_ap_notifications()
    ap_notification_queue = {}
    ap_active_notifications = {}
    hide_ap_notification()
end


local function ensure_ap_notification_tick()
    if ap_notification_tick_hooked then
        return
    end

    Ext.Events.Tick:Subscribe(function()
        advance_ap_notification_queue()
    end)
    ap_notification_tick_hooked = true
end


local function ensure_unlock_module_loaded()
    if ClientUnlock and ClientUnlock.Main and ClientUnlock.Tile then
        return true
    end

    local ok = pcall(Require, "CombatMod/ModActive/Client/GUI/Unlocks")
    if not ok then
        return false
    end

    return ClientUnlock and ClientUnlock.Main and ClientUnlock.Tile
end


local function make_signature(unlocks)
    return table.concat(table.map(unlocks, function(unlock)
        return table.concat({
            tostring(unlock.Id or ""),
            tostring(unlock.Name or ""),
            tostring(unlock.Description or ""),
            tostring(unlock.Icon or ""),
            tostring(unlock.FallbackIcon or ""),
            tostring(unlock.Bought or 0),
            tostring(unlock.Unlocked and 1 or 0),
            tostring(unlock.Amount or ""),
            tostring(unlock.HideStock and 1 or 0),
            tostring(unlock.Cost or 0),
            tostring(unlock.SectionName or ""),
            tostring(unlock.SortSectionIndex or ""),
            tostring(unlock.SortSectionOrder or ""),
            tostring(unlock.RequiredShopFragments or ""),
            tostring(unlock.TotalShopFragments or ""),
        }, "|")
    end), "\n")
end


local function shop_unlock_sort_key(unlock)
    local section_index = tonumber(unlock and unlock.SortSectionIndex or 9999) or 9999
    local section_order = tonumber(unlock and unlock.SortSectionOrder or 0) or 0
    if unlock and unlock.Id == GOAL_UNLOCK_ID then
        return 0, section_index, section_order, "", 0, tostring(unlock.Name or ""), 0
    end

    if unlock and unlock.Id == PIXIE_BLESSING_UNLOCK_ID then
        return 0, section_index, section_order, "", tonumber(unlock.Cost or 0) or 0, tostring(unlock.Name or ""), 0
    end

    if unlock and unlock.Id and string.match(tostring(unlock.Id), "^APCHECK::") then
        return 1,
            section_index,
            section_order,
            tostring(unlock.SortPlayerName or ""):lower(),
            tonumber(unlock.SortPrice or unlock.Cost or 0) or 0,
            tostring(unlock.SortItemName or unlock.Name or ""),
            tonumber(unlock.SortTokenIndex or 0) or 0
    end

    return 2, section_index, section_order, "", 0, tostring(unlock.Name or ""), 0
end


local function sort_unlocks(unlocks)
    table.sort(unlocks, function(a, b)
        local ag, asection, aorder, ap, apr, an, at = shop_unlock_sort_key(a)
        local bg, bsection, border, bp, bpr, bn, bt = shop_unlock_sort_key(b)
        if ag ~= bg then
            return ag < bg
        end
        if asection ~= bsection then
            return asection < bsection
        end
        if aorder ~= border then
            return aorder < border
        end
        if ap ~= bp then
            return ap < bp
        end
        if apr ~= bpr then
            return apr < bpr
        end
        if an ~= bn then
            return an < bn
        end
        return at < bt
    end)
    return unlocks
end


local function is_visible_ap_unlock(unlock)
    if not unlock or not unlock.Id then
        return false
    end

    local unlock_id = tostring(unlock.Id)
    local is_ap_entry = unlock_id == GOAL_UNLOCK_ID
        or unlock_id == PIXIE_BLESSING_UNLOCK_ID
        or string.match(unlock_id, "^APCHECK::") ~= nil
    if not is_ap_entry then
        return false
    end

    if string.match(unlock_id, "^APCHECK::") ~= nil and unlock.Unlocked ~= true then
        return false
    end

    if unlock.Amount ~= nil and tonumber(unlock.Bought or 0) >= tonumber(unlock.Amount or 0) then
        return false
    end

    return true
end


local function unlock_section_name(unlock)
    local section_name = tostring(unlock and unlock.SectionName or "")
    if section_name ~= "" then
        return section_name
    end

    local unlock_id = tostring(unlock and unlock.Id or "")
    if unlock_id == GOAL_UNLOCK_ID or unlock_id == PIXIE_BLESSING_UNLOCK_ID then
        return AP_LOCAL_SHOP_SECTION_NAME
    end

    return "Shop Checks"
end


local function parse_shop_section_unlock_id(unlock_id)
    local index = string.match(stringify(unlock_id), "^APSHOP::SECTION::(%d+)$")
    if not index then
        return nil
    end

    return tonumber(index)
end


local function shop_fragment_progress(state)
    local collected = 0
    local total = 0
    for _, candidate in pairs((state and state.Unlocks) or {}) do
        local section_index = parse_shop_section_unlock_id(candidate and candidate.Id)
        if section_index then
            total = math.max(total, section_index)
            if tonumber(candidate.Bought or 0) > 0 then
                collected = collected + 1
            end
        end
    end

    return collected, total
end


local function shop_fragment_requirement_counts(unlock, state)
    local required = tonumber(unlock and unlock.RequiredShopFragments or 0) or 0
    local total = tonumber(unlock and unlock.TotalShopFragments or 0) or 0
    if required <= 0 then
        local requirement = unlock and unlock.Requirement
        if type(requirement) ~= "table" then
            requirement = { requirement }
        end

        for _, entry in pairs(requirement or {}) do
            local section_index = parse_shop_section_unlock_id(entry)
            if section_index and section_index > required then
                required = section_index
            end
        end
    end

    if required <= 0 then
        return nil
    end

    local collected, inferred_total = shop_fragment_progress(state)
    if total <= 0 then
        total = inferred_total
    end
    if total < required then
        total = required
    end

    return collected, required, total
end


local function build_requirement_label(unlock, state)
    local lines = {}
    local collected, required, total = shop_fragment_requirement_counts(unlock, state)
    if required and required > 0 then
        table.insert(
            lines,
            __("Shop Fragments: %d/%d collected", collected, required)
                .. string.format(" (%d/%d total)", required, total)
        )
    end

    local requirement = unlock and unlock.Requirement
    if type(requirement) ~= "table" then
        requirement = { requirement }
    end

    for _, entry in pairs(requirement or {}) do
        if type(entry) == "number" then
            table.insert(lines, __("%d RogueScore required", entry))
        elseif type(entry) == "string" and not parse_shop_section_unlock_id(entry) then
            local needed_unlock = table.find((state and state.Unlocks) or {}, function(candidate)
                return candidate.Id == entry
            end)
            if needed_unlock then
                table.insert(lines, __("%s required", needed_unlock.Name))
            end
        end
    end

    return table.concat(lines, "\n")
end


local function image_data(image)
    return image and image.ImageData or nil
end


local function image_has_size(image)
    local data = image_data(image)
    if not data or type(data.Size) ~= "table" then
        return false
    end

    local width = tonumber(data.Size[1] or data.Size.x or 0) or 0
    local height = tonumber(data.Size[2] or data.Size.y or 0) or 0
    return width > 0 and height > 0
end


local function image_uses_icon_key(image, icon_key)
    local data = image_data(image)
    return data ~= nil and tostring(data.Icon or "") == tostring(icon_key or "")
end


local function set_image_size(image, width, height)
    local data = image_data(image)
    if data then
        data.Size = { width, height }
    end
end


local function try_icon_key_image(root, icon_key)
    if tostring(icon_key or "") == "" then
        return nil
    end

    local image = root:AddImage(icon_key, { 64, 64 })
    if image_uses_icon_key(image, icon_key) then
        return image
    end

    image:Destroy()
    return nil
end


local function try_ap_atlas_image(root, icon_key)
    local uv = AP_ICON_UVS[tostring(icon_key or "")]
    if not uv then
        return nil
    end

    local image = root:AddImage(AP_ATLAS_TEXTURE_UUID, nil, uv[1], uv[2])
    if image_has_size(image) then
        set_image_size(image, 64, 64)
        return image
    end

    image:Destroy()
    return nil
end


local function add_unlock_icon(root, unlock)
    local requested_icon = stringify(unlock.Icon or "")
    local fallback_icon = stringify(unlock.FallbackIcon or "")

    -- These AP icon keys are generated by the build script. If ImGui refuses the key directly,
    -- we fall back to the atlas texture by hand instead of dumping a bunch of debug junk to disk.
    local requested_image = try_icon_key_image(root, requested_icon)
    if requested_image then
        return requested_image
    end

    local atlas_image = try_ap_atlas_image(root, requested_icon)
    if atlas_image then
        return atlas_image
    end

    local fallback_image = try_icon_key_image(root, fallback_icon)
    if fallback_image then
        return fallback_image
    end

    return root:AddImage(requested_icon, { 64, 64 })
end


local function patch_unlock_ui()
    if patched or not ensure_unlock_module_loaded() then
        return
    end

    -- This stock override started in the CombatMod-side patch once AP shop entries became one-purchase checks.
    original_get_stock = original_get_stock or ClientUnlock.GetStock
    ClientUnlock.GetStock = function(unlock)
        if unlock and unlock.HideStock then
            return ""
        end

        return original_get_stock(unlock)
    end

    -- The tile body started life in the old standalone bridge client UI.
    -- Same idea now, just trimmed down to the AP entries that matter in the merged build.
    ClientUnlock.Tile = function(root, unlock)
        local grp = root:AddGroup(unlock.Id)

        local icon = add_unlock_icon(grp, unlock)
        if unlock.Description then
            local tooltip = icon:Tooltip()
            tooltip:SetStyle("WindowPadding", 30, 10)
            tooltip:AddText(unlock.Description)
        end

        local header = grp:AddGroup(unlock.Id)
        header.SameLine = true
        header:AddText(__("Cost: %s", unlock.Cost))

        local stock_label = header:AddText("")
        if unlock.Amount ~= nil then
            local stock = Components.Computed(stock_label, function(_, unlock_state)
                return ClientUnlock.GetStock(unlock_state)
            end)
            stock.Update(unlock)

            Event.On("StateChange", function(state)
                for _, candidate in pairs(state.Unlocks) do
                    if candidate.Id == unlock.Id then
                        stock.Update(candidate)
                    end
                end
            end):Exec(State)
        end

        grp:AddSeparator()

        local title = grp:AddText(unlock.Name)
        if unlock.Description then
            local tooltip = title:Tooltip()
            tooltip:SetStyle("WindowPadding", 30, 10)
            tooltip:AddText(unlock.Description)
        end

        grp:AddSeparator()

        local tile_unlock = unlock
        local requirement_text = grp:AddText("")

        local function update_requirement_text(state)
            requirement_text.Label = build_requirement_label(tile_unlock, state or State)
            requirement_text.Visible = requirement_text.Label ~= ""
                and not tile_unlock.Unlocked
                and tile_unlock.Bought < 1
        end

        update_requirement_text(State)
        grp:AddDummy(1, 2)

        local purchase_widget = Components.Conditional(grp, function()
            if tile_unlock.Character then
                return ClientUnlock.BuyChar(grp, tile_unlock)
            end

            return ClientUnlock.Buy(grp, tile_unlock)
        end)
        purchase_widget.Update(tile_unlock.Unlocked)

        Event.On("StateChange", function(state)
            for _, candidate in pairs(state.Unlocks) do
                if candidate.Id == tile_unlock.Id then
                    tile_unlock = candidate
                    purchase_widget.Update(tile_unlock.Unlocked)
                    update_requirement_text(state)
                end
            end
        end):Exec(State)
    end

    ClientUnlock.Main = function(tab)
        local root = tab:AddTabItem(__("Unlocks"))
        local content = nil
        local last_signature = ""

        Components.Computed(root:AddSeparatorText(__("Currency owned: %d   RogueScore: %d", 0, 0)), function(_, state)
            return __("Currency owned: %d   RogueScore: %d", state.Currency, state.RogueScore or 0)
        end, "StateChange")

        local function rebuild(state)
            local unlocks = sort_unlocks(table.filter(table.values(state.Unlocks or {}), is_visible_ap_unlock))
            write_shop_debug_snapshot("client_rebuild", state, unlocks)
            if table.size(unlocks) == 0 then
                if content then
                    content:Destroy()
                    content = nil
                end
                last_signature = ""
                return
            end

            local signature = make_signature(unlocks)
            if signature == last_signature then
                return
            end
            last_signature = signature

            if content then
                content:Destroy()
                content = nil
            end

            content = root:AddGroup(U.RandomId())

            local sections = {}
            for _, visible_unlock in ipairs(unlocks) do
                local section_name = unlock_section_name(visible_unlock)
                if table.size(sections) == 0 or sections[#sections].name ~= section_name then
                    table.insert(sections, {
                        name = section_name,
                        unlocks = {},
                    })
                end
                table.insert(sections[#sections].unlocks, visible_unlock)
            end

            for section_number, section in ipairs(sections) do
                content:AddSeparatorText(section.name)

                local section_root = content:AddGroup(U.RandomId())
                local columns = 3
                local rows = math.max(1, math.ceil(table.size(section.unlocks) / columns))
                Components.Layout(section_root, columns, rows, function(layout)
                    layout.Table.Borders = true
                    layout.Table.ScrollY = false
                    for index, visible_unlock in ipairs(section.unlocks) do
                        local column = (index - 1) % columns
                        local row = math.ceil(index / columns)
                        local cell = layout.Cells[row][column + 1]
                        ClientUnlock.Tile(cell, visible_unlock)
                    end
                end)

                if section_number < #sections then
                    content:AddDummy(1, 8)
                end
            end
        end

        Event.On("StateChange", rebuild):Exec(State)
    end

    patched = true
end


patch_unlock_ui()
ensure_ap_notification_tick()

Net.On("ArchipelagoTrialsNotification", function(event)
    queue_ap_notification(event.Payload or {})
end)

Ext.Events.SessionLoaded:Subscribe(function()
    reset_ap_notifications()
    patch_unlock_ui()
end)
