Debug = {}

---@param tab ExtuiTabBar
function Debug.Main(tab)
    Schedule(function()
        Event.Trigger("ToggleDebug", Mod.Debug)
    end)

    local tabRoot = tab:AddTabItem(TL("h366718e6g6332g44dbgb055g42bd5277609f"))
    local root = tabRoot:AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }

    local ca = root:AddButton(TL("h31b7af7eg64e2g4fa2gb028g49c4d20a6be6"))
    ca.OnClick = function()
        Net.Send("KillNearby")
    end

    -- section State
    local state = root:AddGroup(TL("h32391aeeg676cg44fbgb010ga29dd23280bf"))
    state:AddSeparatorText(TL("h32391aeeg676cg44fbgb010ga29dd23280bf"))
    state:AddButton(TL("h27b40c36g72e1g4596gb148g73f0536a51d2")).OnClick = function()
        Net.Send("SyncState")
        Net.Send("GetTemplates")
        Net.Send("GetItems")
    end

    local stateTree
    Event.On("StateChange", function()
        if stateTree then
            stateTree:Destroy()
        end

        stateTree = Components.Tree(state, State)
    end)

    -- section Templates
    local templates = root:AddGroup(TL("h273d0172g7268g4542gb140ge3241362c106"))
    templates:AddSeparatorText(TL("h273d0172g7268g4542gb140ge3241362c106"))

    local templatesTree
    Net.On("GetTemplates", function(event)
        if templatesTree then
            templatesTree:Destroy()
        end

        templatesTree = Components.Tree(templates, event.Payload)
    end)
    Net.Send("GetTemplates")

    -- section Enemies
    Debug.Enemies(root)

    -- section Items
    Debug.Items(root)

    root:AddDummy(1, 2)

    return tabRoot
end

function Debug.Enemies(root)
    local grp = root:AddGroup(TL("h20450ab6g7510g45fegb137g6398531541ba"))
    grp:AddSeparatorText(TL("h20450ab6g7510g45fegb137g6398531541ba"))

    local netEnemies
    Net.On("GetEnemies", function(event)
        netEnemies = event.Payload
        Event.Trigger("EnemiesChanged", netEnemies)
    end)

    local tree
    Event.On("EnemiesChanged", function(enemies)
        if tree then
            tree:Destroy()
        end

        tree = Components.Tree(grp, enemies, nil, function(node, key, value)
            if key == "TemplateId" then
                local nodeLoaded = false
                node:AddButton(TL("h31359ceeg6460g4c9bgb020g6afdd20248df")).OnClick = function()
                    Net.RCE("Enemy.Find('%s'):Spawn(Osi.GetPosition(RCE:Character()))", value):After(function(_, err)
                        L.Dump(err)
                    end)
                end

                node.OnClick = function(v)
                    if nodeLoaded then
                        return
                    end

                    local temp = Ext.Template.GetTemplate(value)
                    if temp then
                        Components.Tree(node, UT.Clean(temp), TL("h22c45432g7791g4016gb11fg7670133d5452", value))

                        node:AddText("   " .. TL("h2eeb5756g7bbeg4020gb1ddg864653ffa464") .. " = ")
                        node:AddText(Ext.Loca.GetTranslatedString(temp.DisplayName.Handle.Handle)).SameLine = true
                    end

                    nodeLoaded = true
                end

                return true -- replace node
            end
        end)
    end)

    local search = grp:AddInputText(TL("h243816eeg716dg443bgb170gb25dd352907f"))
    search.IDContext = U.RandomId()
    search.OnChange = Debounce(100, function(input)
        local list = {}
        for k, enemies in pairs(netEnemies) do
            list[k] = table.filter(enemies, function(item)
                local temp = Ext.Template.GetTemplate(item.TemplateId)
                if not temp then
                    L.Error("Template not found", item.TemplateId, item.Name)
                    return false
                end

                return string.contains(item.Name, input.Text, true, true)
                    or string.contains(Ext.Loca.GetTranslatedString(temp.DisplayName.Handle.Handle), input.Text, true, true)
            end)
        end

        Event.Trigger("EnemiesChanged", list)
    end)

    local combo = grp:AddCombo(TL("h373f16ceg626ag4439gb040gc25fd262e07d"))
    combo.IDContext = U.RandomId()
    combo.Options = C.EnemyTier
    combo.OnChange = function()
        search.Text = ""
        Net.Send("GetEnemies", { Tier = combo.Options[combo.SelectedIndex + 1] })
    end

    local btn = grp:AddButton(TL("h367fb87eg632ag4ed2gb054gc8b4d276ea96"))
    btn.IDContext = U.RandomId()
    btn.OnClick = function()
        combo.SelectedIndex = -1
        search.Text = ""
        Net.Send("GetEnemies")
    end
    btn.SameLine = true

    Net.Send("GetEnemies")
end
function Debug.Items(root)
    local grp = root:AddGroup(TL("h322608ceg6773g45d9gb011g53bfd233719d"))
    grp:AddSeparatorText(TL("h322608ceg6773g45d9gb011g53bfd233719d"))

    local netItems
    Net.On("GetItems", function(event)
        netItems = event.Payload
        Event.Trigger("ItemsChanged", netItems)
    end)

    local tree
    Event.On("ItemsChanged", function(items)
        if tree then
            tree:Destroy()
        end

        tree = Components.Tree(grp, items, nil, function(node, key, value)
            if key == "Name" then
                node:AddText("   " .. TL("h3535380eg6060g46d5gb060g60b3d2424291") .. " = ")
                local t = node:AddInputText("")
                t.SameLine = true
                t.Text = value

                node:AddButton(TL("h31359ceeg6460g4c9bgb020g6afdd20248df")).OnClick = function()
                    local rt = nil
                    for _, catItems in pairs(items) do
                        for _, item in pairs(catItems) do
                            if item.Name == value then
                                rt = item.RootTemplate
                                break
                            end
                        end
                    end
                    Net.RCE("Item.Create('%s', '', '%s'):Spawn(Osi.GetPosition(RCE:Character()))", value, rt)
                        :After(function(_, err)
                            L.Dump(err)
                        end)
                end

                return true
            end
            if key == "RootTemplate" then
                local nodeLoaded = false

                node.OnClick = function(v)
                    if nodeLoaded then
                        return
                    end

                    local temp = Ext.Template.GetTemplate(value)
                    if temp then
                        Components.Tree(node, UT.Clean(temp), TL("h34aa446dg61ffg4113g8079g9775e25bb557", value))

                        node:AddText("   " .. TL("h2eeb5756g7bbeg4020gb1ddg864653ffa464") .. " = ")
                        node:AddText(Ext.Loca.GetTranslatedString(temp.DisplayName.Handle.Handle)).SameLine = true

                        node:AddText("   " .. TL("h36a80e1eg63fdg45b4gb059gb3d2d27b91f0") .. " = ")
                        node:AddImage(temp.Icon).SameLine = true
                    end

                    nodeLoaded = true
                end

                return true -- replace node
            end
        end)
    end)

    local search = grp:AddInputText(TL("h243816eeg716dg443bgb170gb25dd352907f"))
    search.IDContext = U.RandomId()
    search.OnChange = Debounce(100, function(input)
        local list = {}
        for k, items in pairs(netItems) do
            list[k] = table.filter(items, function(item)
                local temp = Ext.Template.GetTemplate(item.RootTemplate)
                if not temp then
                    L.Error("Template not found", item.RootTemplate, item.Name)
                    return false
                end

                if input.Text:match("^#") then
                    return string.contains(item.Slot, input.Text:sub(2), true, true)
                        or string.contains(item.Tab, input.Text:sub(2), true, true)
                end

                return string.contains(item.Name, input.Text, true, true)
                    or string.contains(Ext.Loca.GetTranslatedString(temp.DisplayName.Handle.Handle), input.Text, true, true)
            end)
        end

        Event.Trigger("ItemsChanged", list)
    end)

    local combo = grp:AddCombo(TL("h211f8066g744ag4d53gb122gcb355300e917"))
    combo.IDContext = U.RandomId()
    combo.Options = C.ItemRarity
    combo.OnChange = function()
        search.Text = ""
        Net.Send("GetItems", { Rarity = combo.Options[combo.SelectedIndex + 1] })
    end

    local btn = grp:AddButton(TL("h367fb87eg632ag4ed2gb054gc8b4d276ea96"))
    btn.IDContext = U.RandomId()
    btn.OnClick = function()
        combo.SelectedIndex = -1
        search.Text = ""
        Net.Send("GetItems")
    end
    btn.SameLine = true

    Net.Send("GetItems")
end
