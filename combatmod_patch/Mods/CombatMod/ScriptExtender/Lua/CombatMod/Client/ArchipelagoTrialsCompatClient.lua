local patched = false
local original_get_stock = nil
local GOAL_UNLOCK_ID = "APGOAL::QUICKSTART"
local AP_ICON_DEBUG_FILE = "ap_icon_debug.json"
local AP_ATLAS_TEXTURE_UUID = "aa417c69-e69a-f1ef-5a8d-65b7b5d4e195"
local PROXY_BLUE_ICON = "statIcons_WretchedGrowth_Aura"
local PROXY_COLOR_ICON = "statIcons_WretchedGrowth_Buff"
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
local binding_cache = {}
local current_icon_debug_entries = {}


local function save_json_object(path, data)
    Ext.IO.SaveFile(path, Ext.Json.Stringify(data))
end


local function stringify(value)
    if value == nil then
        return ""
    end

    return tostring(value)
end


local function vec2_to_array(value)
    if type(value) ~= "table" then
        return { 0, 0 }
    end

    return {
        tonumber(value[1] or value.x or 0) or 0,
        tonumber(value[2] or value.y or 0) or 0,
    }
end


local function image_binding_summary(image, request, method)
    local image_data = image and image.ImageData or nil
    local size = vec2_to_array(image_data and image_data.Size or nil)
    return {
        method = method,
        request = stringify(request),
        bound_icon = stringify(image_data and image_data.Icon or ""),
        texture_resource = stringify(image_data and image_data.TextureResource or ""),
        size = size,
        ok = size[1] > 0 and size[2] > 0,
    }
end


local function icon_key_binding_ok(summary, requested_icon)
    return summary.ok and summary.bound_icon == stringify(requested_icon)
end


local function set_image_size(image, width, height)
    if image and image.ImageData then
        image.ImageData.Size = { width, height }
    end
end


local function get_texture_resource_debug(texture_uuid)
    local debug = {
        requested_uuid = stringify(texture_uuid),
        lookup_ok = false,
        exists = false,
        source_file = "",
        width = 0,
        height = 0,
        texture_type = "",
    }

    if not Ext.Resource or not Ext.Resource.Get then
        return debug
    end

    local ok, texture_or_error = pcall(Ext.Resource.Get, texture_uuid, "Texture")
    debug.lookup_ok = ok
    if not ok then
        debug.error = stringify(texture_or_error)
        return debug
    end

    if not texture_or_error then
        return debug
    end

    debug.exists = true
    debug.guid = stringify(texture_or_error.Guid or "")
    debug.source_file = stringify(texture_or_error.SourceFile or "")
    debug.width = tonumber(texture_or_error.Width or 0) or 0
    debug.height = tonumber(texture_or_error.Height or 0) or 0
    debug.texture_type = stringify(texture_or_error.Type or "")
    return debug
end


local function texture_resource_membership(texture_uuid)
    local result = {
        requested_uuid = stringify(texture_uuid),
        get_all_ok = false,
        found_in_get_all = false,
    }

    if not Ext.Resource or not Ext.Resource.GetAll then
        return result
    end

    local ok, texture_ids = pcall(Ext.Resource.GetAll, "Texture")
    result.get_all_ok = ok
    if not ok then
        result.error = stringify(texture_ids)
        return result
    end

    for _, candidate in ipairs(texture_ids or {}) do
        if stringify(candidate) == stringify(texture_uuid) then
            result.found_in_get_all = true
            break
        end
    end

    return result
end


local function record_icon_debug(unlock, attempts, chosen)
    if unlock and unlock.Id ~= GOAL_UNLOCK_ID and #current_icon_debug_entries >= 12 then
        return
    end

    table.insert(current_icon_debug_entries, {
        unlock_id = stringify(unlock and unlock.Id or ""),
        unlock_name = stringify(unlock and unlock.Name or ""),
        requested_icon = stringify(unlock and unlock.Icon or ""),
        fallback_icon = stringify(unlock and unlock.FallbackIcon or ""),
        attempts = attempts,
        chosen = chosen,
    })
end


local function probe_binding_once(root, cache_key, request, method, uv0, uv1)
    local cached = binding_cache[cache_key]
    if cached then
        return cached
    end

    local probe = root:AddImage(request, nil, uv0, uv1)
    local summary = image_binding_summary(probe, request, method)
    probe:Destroy()
    binding_cache[cache_key] = summary
    return summary
end


local function write_icon_debug(root, unlocks)
    local goal_unlock = table.find(unlocks or {}, function(candidate)
        return candidate.Id == GOAL_UNLOCK_ID
    end)
    local sample_ap_unlock = table.find(unlocks or {}, function(candidate)
        return string.match(stringify(candidate.Id or ""), "^APCHECK::") ~= nil
    end)

    local diagnostics = {
        ap_atlas_texture = get_texture_resource_debug(AP_ATLAS_TEXTURE_UUID),
        ap_atlas_membership = texture_resource_membership(AP_ATLAS_TEXTURE_UUID),
        legacy_archipelago_texture = get_texture_resource_debug("10bdc905-ca87-bbee-b0b2-bf04f1fdcc33"),
        legacy_archipelago_membership = texture_resource_membership("10bdc905-ca87-bbee-b0b2-bf04f1fdcc33"),
        goal_unlock = {
            id = stringify(goal_unlock and goal_unlock.Id or ""),
            icon = stringify(goal_unlock and goal_unlock.Icon or ""),
        },
        sample_ap_unlock = {
            id = stringify(sample_ap_unlock and sample_ap_unlock.Id or ""),
            icon = stringify(sample_ap_unlock and sample_ap_unlock.Icon or ""),
            fallback_icon = stringify(sample_ap_unlock and sample_ap_unlock.FallbackIcon or ""),
        },
        probes = {
            proxy_blue = probe_binding_once(root, "probe|icon|" .. PROXY_BLUE_ICON, PROXY_BLUE_ICON, "icon-key-probe"),
            proxy_color = probe_binding_once(root, "probe|icon|" .. PROXY_COLOR_ICON, PROXY_COLOR_ICON, "icon-key-probe"),
            original_logo = probe_binding_once(root, "probe|icon|original-logo", "original-logo", "icon-key-probe"),
            ap_blue = probe_binding_once(root, "probe|icon|ap_trials_icon_blue_001", "ap_trials_icon_blue_001", "icon-key-probe"),
            ap_color = probe_binding_once(root, "probe|icon|ap_trials_icon_color_001", "ap_trials_icon_color_001", "icon-key-probe"),
            atlas_texture = probe_binding_once(root, "probe|texture|" .. AP_ATLAS_TEXTURE_UUID, AP_ATLAS_TEXTURE_UUID, "texture-probe"),
            atlas_texture_blue_uv = probe_binding_once(
                root,
                "probe|texture|" .. AP_ATLAS_TEXTURE_UUID .. "|blue",
                AP_ATLAS_TEXTURE_UUID,
                "texture-uv-probe",
                AP_ICON_UVS["ap_trials_icon_blue_001"][1],
                AP_ICON_UVS["ap_trials_icon_blue_001"][2]
            ),
        },
        sample_entries = current_icon_debug_entries,
        binding_cache = binding_cache,
    }

    if goal_unlock and goal_unlock.Icon then
        diagnostics.probes.goal_icon = probe_binding_once(
            root,
            "probe|icon|" .. stringify(goal_unlock.Icon),
            goal_unlock.Icon,
            "icon-key-probe"
        )
    end

    if sample_ap_unlock and sample_ap_unlock.FallbackIcon then
        diagnostics.probes.sample_fallback_icon = probe_binding_once(
            root,
            "probe|icon|" .. stringify(sample_ap_unlock.FallbackIcon),
            sample_ap_unlock.FallbackIcon,
            "icon-key-probe"
        )
    end

    if sample_ap_unlock and sample_ap_unlock.Icon then
        diagnostics.probes.sample_requested_icon = probe_binding_once(
            root,
            "probe|icon|" .. stringify(sample_ap_unlock.Icon),
            sample_ap_unlock.Icon,
            "icon-key-probe"
        )
    end

    local goal_texture_uuid = stringify(diagnostics.probes.goal_icon and diagnostics.probes.goal_icon.texture_resource or "")
    if goal_texture_uuid ~= "" then
        diagnostics.goal_texture = get_texture_resource_debug(goal_texture_uuid)
        diagnostics.goal_texture_membership = texture_resource_membership(goal_texture_uuid)
    end

    local sample_fallback_texture_uuid = stringify(diagnostics.probes.sample_fallback_icon and diagnostics.probes.sample_fallback_icon.texture_resource or "")
    if sample_fallback_texture_uuid ~= "" then
        diagnostics.sample_fallback_texture = get_texture_resource_debug(sample_fallback_texture_uuid)
        diagnostics.sample_fallback_texture_membership = texture_resource_membership(sample_fallback_texture_uuid)
    end

    local sample_requested_texture_uuid = stringify(diagnostics.probes.sample_requested_icon and diagnostics.probes.sample_requested_icon.texture_resource or "")
    if sample_requested_texture_uuid ~= "" then
        diagnostics.sample_requested_texture = get_texture_resource_debug(sample_requested_texture_uuid)
        diagnostics.sample_requested_texture_membership = texture_resource_membership(sample_requested_texture_uuid)
    end

    save_json_object(AP_ICON_DEBUG_FILE, diagnostics)
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
        }, "|")
    end), "\n")
end


local function shop_unlock_sort_key(unlock)
    if unlock and unlock.Id == GOAL_UNLOCK_ID then
        return 0, 0, tostring(unlock.Name or "")
    end

    local ap_index = nil
    if unlock and unlock.Id then
        ap_index = tonumber(string.match(tostring(unlock.Id), "^APCHECK::(%d+)::"))
    end
    if ap_index then
        return 1, ap_index, tostring(unlock.Name or "")
    end

    return 2, 0, tostring(unlock.Name or "")
end


local function sort_unlocks(unlocks)
    table.sort(unlocks, function(a, b)
        local ag, ai, an = shop_unlock_sort_key(a)
        local bg, bi, bn = shop_unlock_sort_key(b)
        if ag ~= bg then
            return ag < bg
        end
        if ai ~= bi then
            return ai < bi
        end
        return an < bn
    end)
    return unlocks
end


local function add_unlock_icon(root, unlock)
    local requested_icon = stringify(unlock.Icon or "")
    local fallback_icon = stringify(unlock.FallbackIcon or "")
    local ap_uvs = AP_ICON_UVS[requested_icon]
    local attempts = {}

    if requested_icon ~= "" then
        local requested_image = root:AddImage(requested_icon, { 64, 64 })
        local requested_summary = image_binding_summary(requested_image, requested_icon, "requested-icon")
        table.insert(attempts, requested_summary)
        if icon_key_binding_ok(requested_summary, requested_icon) then
            record_icon_debug(unlock, attempts, requested_summary)
            return requested_image
        end
        requested_image:Destroy()
    end

    if ap_uvs then
        local key_probe = root:AddImage(requested_icon)
        local key_summary = image_binding_summary(key_probe, requested_icon, "icon-key")
        table.insert(attempts, key_summary)
        if icon_key_binding_ok(key_summary, requested_icon) then
            set_image_size(key_probe, 64, 64)
            record_icon_debug(unlock, attempts, key_summary)
            return key_probe
        end
        key_probe:Destroy()

        local texture_probe = root:AddImage(AP_ATLAS_TEXTURE_UUID, nil, ap_uvs[1], ap_uvs[2])
        local texture_summary = image_binding_summary(texture_probe, AP_ATLAS_TEXTURE_UUID, "direct-texture")
        table.insert(attempts, texture_summary)
        if texture_summary.ok then
            set_image_size(texture_probe, 64, 64)
            record_icon_debug(unlock, attempts, texture_summary)
            return texture_probe
        end
        texture_probe:Destroy()
    end

    if fallback_icon ~= "" then
        local fallback_image = root:AddImage(fallback_icon, { 64, 64 })
        local fallback_summary = image_binding_summary(fallback_image, fallback_icon, "fallback-icon")
        table.insert(attempts, fallback_summary)
        record_icon_debug(unlock, attempts, fallback_summary)
        return fallback_image
    end

    local default_image = root:AddImage(requested_icon, { 64, 64 })
    local default_summary = image_binding_summary(default_image, requested_icon, "default-icon")
    table.insert(attempts, default_summary)
    record_icon_debug(unlock, attempts, default_summary)
    return default_image
end


local function patch_unlock_ui()
    if patched or not ensure_unlock_module_loaded() then
        return
    end

    original_get_stock = original_get_stock or ClientUnlock.GetStock
    ClientUnlock.GetStock = function(unlock)
        if unlock and unlock.HideStock then
            return ""
        end

        return original_get_stock(unlock)
    end

    ClientUnlock.Tile = function(root, unlock)
        local grp = root:AddGroup(unlock.Id)

        local icon = add_unlock_icon(grp, unlock)
        if unlock.Description then
            local t = icon:Tooltip()
            t:SetStyle("WindowPadding", 30, 10)
            t:AddText(unlock.Description)
        end

        local col2 = grp:AddGroup(unlock.Id)
        col2.SameLine = true
        col2:AddText(__("Cost: %s", unlock.Cost))

        local buyLabel = col2:AddText("")

        if unlock.Amount ~= nil then
            local amount = Components.Computed(buyLabel, function(_, unlock_state)
                return ClientUnlock.GetStock(unlock_state)
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
            local tile_unlock = unlock

            local bottomText = grp:AddText("")
            local function checkVisible()
                bottomText.Visible = not tile_unlock.Unlocked and tile_unlock.Bought < 1
            end
            checkVisible()

            if tile_unlock.Requirement then
                if type(tile_unlock.Requirement) ~= "table" then
                    tile_unlock.Requirement = { tile_unlock.Requirement }
                end

                for _, req in pairs(tile_unlock.Requirement) do
                    if type(req) == "number" then
                        bottomText.Label = bottomText.Label .. __("%d RogueScore required", req) .. "\n"
                    elseif type(req) == "string" then
                        local u = table.find(State.Unlocks, function(candidate)
                            return candidate.Id == req
                        end)
                        if u then
                            bottomText.Label = bottomText.Label .. __("%s required", u.Name) .. "\n"
                        end
                    end
                end
            end

            grp:AddDummy(1, 2)

            local cond = Components.Conditional(grp, function()
                if tile_unlock.Character then
                    return ClientUnlock.BuyChar(grp, tile_unlock)
                end

                return ClientUnlock.Buy(grp, tile_unlock)
            end)
            cond.Update(tile_unlock.Unlocked)

            Event.On("StateChange", function(state)
                for _, new in pairs(state.Unlocks) do
                    if new.Id == tile_unlock.Id then
                        tile_unlock = new
                        cond.Update(tile_unlock.Unlocked)
                        checkVisible()
                    end
                end
            end):Exec(State)
        end
    end

    ClientUnlock.Main = function(tab)
        local root = tab:AddTabItem(__("Unlocks"))
        local content = nil
        local last_signature = ""

        Components.Computed(root:AddSeparatorText(__("Currency owned: %d   RogueScore: %d", 0, 0)), function(_, state)
            return __("Currency owned: %d   RogueScore: %d", state.Currency, state.RogueScore or 0)
        end, "StateChange")

        local function rebuild(state)
            local unlocks = sort_unlocks(table.values(state.Unlocks or {}))
            if table.size(unlocks) == 0 then
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

            current_icon_debug_entries = {}
            local cols = 3
            local rows = math.max(1, math.ceil(table.size(unlocks) / cols))
            content = root:AddGroup(U.RandomId())
            Components.Layout(content, cols, rows, function(layout)
                layout.Table.Borders = true
                layout.Table.ScrollY = true
                for index, unlock in ipairs(unlocks) do
                    local column = (index - 1) % cols
                    local row = math.ceil(index / cols)
                    local cell = layout.Cells[row][column + 1]
                    ClientUnlock.Tile(cell, unlock)
                end
            end)
            write_icon_debug(content, unlocks)
        end

        Event.On("StateChange", rebuild):Exec(State)
    end

    patched = true
end


patch_unlock_ui()
