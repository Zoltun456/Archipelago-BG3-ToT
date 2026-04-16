Creation = {}

---@param tab ExtuiTabBar
function Creation.Main(tab)
    ---@type ExtuiTree
    local root = tab:AddTabItem(TL("h20c028a6g7595g47dfgb13fg31b9531d139b"))

    do
        ---@type ExtuiInputText
        local posBox = root:AddInputText(TL("h37371a7eg6262g44f2gb040g4294d26260b6"))
        posBox.Multiline = true

        local pb = root:AddButton(TL("h31b2227eg64e7g4772gb028g1114d20a3336"))
        pb.SameLine = true

        local pi = root:AddInputText(TL("h31b2227eg64e7g4772gb028g1114d20a3336"))
        pi.IDContext = U.RandomId()
        pi.Text = "0, 0, 0"
        local ping = root:AddButton(TL("h37333c06g6266g4695gb040g00f3526222d1"))
        ping.SameLine = true
        local tp = root:AddButton(TL("h097e26aeg5c2bg473fgb3a4gd159d186f37b"))
        tp.SameLine = true

        pb.OnClick = function()
            local host = GE.GetHost()
            local region = host.Level.LevelName
            L.Dump("Host", host.CustomName)
            Net.RCE("return Osi.GetPosition(RCE:Character())"):After(function(ok, x, y, z)
                if not ok then
                    return
                end

                Net.RCE('Osi.RequestPing(%s, %s, %s, "", "")', x, y, z)
                posBox.Text = posBox.Text .. string.format("%s: %s, %s, %s", region, x, y, z) .. "\n"
                pi.Text = string.format("%s, %s, %s", x, y, z)
            end)
        end

        ping.OnClick = function()
            local x, y, z = table.unpack(string.split(pi.Text, ","))
            x = x:match("[-]?%d+")
            y = y:match("[-]?%d+")
            z = z:match("[-]?%d+")
            Net.RCE('Osi.RequestPing(%d, %d, %d, "", "")', x, y, z):After(function(ok, err)
                if not ok then
                    Event.Trigger("Error", err)
                end
            end)
        end

        tp.OnClick = function()
            local x, y, z = table.unpack(string.split(pi.Text, ","))
            x = x:match("[-]?%d+")
            y = y:match("[-]?%d+")
            z = z:match("[-]?%d+")
            Net.RCE("Osi.TeleportToPosition(RCE:Character(), %d, %d, %d)", x, y, z):After(function(ok, err)
                if not ok then
                    Event.Trigger("Error", err)
                end
            end)
        end
    end

    do
        local uwp = root:AddButton(TL("h2c5a29c3g790fg47c9ga1f6g91af03d4b38d"))
        uwp.OnClick = function()
            Net.RCE("Osi.PROC_Debug_UnlockAllWP()")
        end
        local wp = root:AddCollapsingHeader(TL("h273eb1cag726bg4e49gb140gd82f9362fa0d"))
        wp.SameLine = true
        Components.Layout(wp, 1, 1, function(layout)
            layout.Table.ScrollY = true
            local wp = layout.Cells[1][1]

            local acts = table.keys(C.Waypoints)
            table.sort(acts)
            for _, act in ipairs(acts) do
                wp:AddSeparatorText(act .. " - " .. C.Regions[act])
                for short, waypoint in pairs(C.Waypoints[act]) do
                    local label = waypoint:gsub(string.escape(U.UUID.Extract(waypoint)), short)
                    local b = wp:AddButton(label)
                    b.OnClick = function()
                        Net.RCE("TeleportToWaypoint(RCE:Character(), '%s')", waypoint):After(function(ok, err)
                            if not ok then
                                Event.Trigger("Error", err)
                            end
                        end)
                    end
                end
            end
        end)
    end

    return root
end
