Control = {}

function Control.Events()
    Event.On("Start", function(scenarioName, mapName, difficultyName)
        Net.Request("Start", {
            Scenario = scenarioName,
            Map = mapName,
			Difficulty = difficultyName,
        }):After(DisplayResponse)
    end)

    Event.On("Stop", function()
        Net.Request("Stop"):After(DisplayResponse)
    end)

    Event.On("MarkSpawns", function(data)
        Net.Request("MarkSpawns", data):After(DisplayResponse)
    end)

    Event.On("PingSpawns", function(data)
        Net.Request("PingSpawns", data):After(DisplayResponse)
    end)

    Event.On("Teleport", function(data)
        Net.Request("Teleport", data):After(DisplayResponse)
    end)

    Event.On("ToCamp", function()
        Net.Request("ToCamp"):After(DisplayResponse)
    end)

    Event.On("ForwardCombat", function()
        Net.Request("ForwardCombat"):After(DisplayResponse)
    end)
end

---@param tab ExtuiTabBar
function Control.Main(tab)
    Control.Events()

    local root = tab:AddTabItem(TL("h307360eeg6526g435bgb034g053dd216271f"))

    local header = root:AddSeparatorText("")
    Components.Layout(root, 1, 2, function(layout)
        local cellStart, cellStop = layout.Cells[1][1], layout.Cells[2][1]

        local startLayout = Control.StartPanel(cellStart)

        local stopLayout = Control.RunningPanel(cellStop)

        Event.On("StateChange", function(state)
            if state and state.Scenario then
                startLayout.Table.Visible = false
                stopLayout.Table.Visible = true
                header.Label = TL("h21780c4eg742dg4591gb124gb3f7d30691d5")
            else
                startLayout.Table.Visible = true
                stopLayout.Table.Visible = false
                header.Label = TL("h3166c60eg6433g4935gb025g5f53d2077d71")
            end

            if state and state.RogueModeActive then
                header.Label = TL("hab6c1c62gfe39g4493gb985gf2f51ba7d0d7", header.Label, tonumber(state.RogueScore or 0) or 0)
            end
        end):Exec()
    end)

    root:AddSeparator()
    root:AddText(__(""))
    root:AddText(TL("h1a239f49g4f76g4ca1g8291g0ac7a0b328e5"))
    root:AddText(__(""))
    root:AddText(TL("hbeac8647gebf9g4d31ga8d9gfb574afbd975"))
    root:AddText(__(""))
    root:AddText(TL("h214532ddg7410g4678g8127g601ee305423c"))
    root:AddText(__(""))
	root:AddText(TL("hb495ade9ge1c0g4f8bg887ag69edaa584bcf"))
    root:AddText(__(""))
    root:AddSeparator()

    root:AddSeparatorText(TL("h31b714deg64e2g4418gb028g427ed20a605c"))

    local scrollable = root:AddChildWindow(U.RandomId())

    ---@type ExtuiInputText
    local textBox = scrollable:AddText("")

    Event.On("Start", function()
        textBox.Label = ""
    end)
    Components.Computed(textBox, function(_, event)
        return string.format("[%d]: %s\n%s", Ext.Utils.MonotonicTime(), event.Payload[1], textBox.Label)
    end, Net.EventName("PlayerNotify"), "Label")
end

function Control.StartPanel(root)
    return Components.Layout(root, 3, 1, function(startLayout)
        startLayout.Cells[1][1]:AddText(TL("h2553979eg7006g4c2cgb166g0a4ad3442868"))
		startLayout.Cells[1][2]:AddText(TL("h2c9ee446g79cbg4b11gb1fagdd7753d8ff55"))
        startLayout.Cells[1][3]:AddText(TL("h35341416g6061g4414gb060g727252425050"))
        local listCols = startLayout.Cells[1]

        local scenarioSelection = Components.Selection(listCols[1])
        local scenarioSelPagination = Components.Pagination(scenarioSelection.Root, {}, 5)
		local difficultySelection = Components.Selection(listCols[2])
        local difficultySelPagination = Components.Pagination(difficultySelection.Root, {}, 5)
        local mapSelection = Components.Selection(listCols[3])
        local mapSelPagination = Components.Pagination(mapSelection.Root, {}, 5)

        Net.On("GetSelection", function(event)
            scenarioSelection.Reset()
            mapSelection.Reset()
			difficultySelection.Reset()

            for i, item in ipairs(event.Payload.Scenarios) do
                local label = item.Name
                scenarioSelection.AddItem(label, item.Name)
            end
            scenarioSelPagination.UpdateItems(scenarioSelection.Selectables)

			difficultySelection.AddItem(TL("hda5a3f21g8f0fg46a7g8e96g90c12cb4b2e3"), 0)
			difficultySelection.AddItem(TL("heac966ffgbf9cg433agad9fga55ccfbd877e"), 1)
			difficultySelection.AddItem(TL("h82b49961gd7e1g4cc3g8b18g7aa5293a5887"), 2)
			difficultySelPagination.UpdateItems(difficultySelection.Selectables)

            mapSelection.AddItem(TL("h279d3a06g72c8g46f5gb14age0935368c2b1"), nil)
            if not State.RogueModeActive then
                for i, item in ipairs(event.Payload.Maps) do
                    local label = item.Name
                    if item.Author then
                        label = TL("h3b4890a6g6e1dg4c5fgb087gba3952a5981b", item.Author, label)
                    end

                    mapSelection.AddItem(label, item.Name)
                end
            end

            mapSelPagination.UpdateItems(mapSelection.Selectables)
        end)

        local startButton = listCols[1]:AddButton(TL("h323096eeg6765g4c3bgb010g3a5dd232187f"))
        startButton.IDContext = U.RandomId()

        local pressed = false
        Event.On("StateChange", function()
            Net.Send("GetSelection")
            pressed = false
            startButton:SetStyle("Alpha", 1)
        end)

        startButton.OnClick = function(button)
            if pressed then
                return
            end
            pressed = true
            startButton:SetStyle("Alpha", 0.5)
            Event.Trigger("Start", scenarioSelection.Value, mapSelection.Value, difficultySelection.Value)
        end

        Components.Conditional(listCols[3], function(cond)
            local grp = cond.Root:AddGroup(TL("h366718e6g6332g44dbgb055g42bd5277609f"))

            grp:AddButton(TL("h25531a42g7006g44f1gb166g0297134420b5")).OnClick = function(button)
                Event.Trigger("Teleport", { Map = mapSelection.Value })
            end

            local b2 = grp:AddButton(TL("h315e322eg640bg4677gb026gd011d204f233"))
            b2.SameLine = true
            b2.OnClick = function(button)
                Event.Trigger("PingSpawns", { Map = mapSelection.Value })
            end

            local b3 = grp:AddButton(TL("h2d5b4e72g780eg41b2gb1e6g87d413c4a5f6"))
            b3.OnClick = function()
                Net.Send("KillSpawned")
            end

            return grp
        end, "ToggleDebug").Update(Mod.Debug)

        listCols[1]:AddButton(TL("h3160102eg6435g4457gb025g3231d2071013")).OnClick = function(button)
            Event.Trigger("ToCamp")
        end
    end)
end

function Control.RunningPanel(root)
    return Components.Layout(root, 3, 2, function(layout)
        local scenarioName = layout.Cells[1][1]:AddText("")
		local difficultyName = layout.Cells[1][2]:AddText("")
        local mapName = layout.Cells[1][3]:AddText("")

        Components.Computed(scenarioName, function(box, state)
            if state.Scenario then
                local text = {
                    TL("h218206b6g74d7g453egb12bg13585309317a", tostring(state.Scenario.Name)),
                    TL("h3d5fde62g680ag48b3gb0e6gced512c4ecf7", tostring(state.Scenario.Round)),
                    TL("h33c0b3bcg6695g4e6eg900fg3808f22d1a2a", tostring(#state.Scenario.Timeline)),
                    TL("h8528df02gd07dg48a5gbb61gbec319439ce1", tostring(#(state.Scenario.Enemies[state.Scenario.Round + 1] or {}))),
                    TL("h2cb5c7a2g79e0g492fgb1f8g6f4913da4d6b", tostring(#state.Scenario.KilledEnemies)),
                }
                return table.concat(text, "\n")
            end
        end, "StateChange")
		
		
		Components.Computed(difficultyName, function(box, state)
            if state.Scenario then
                if state.HardMode then
				    return TL("hcb371950g9e62g44c0g9f80g42a63da26084")
				elseif state.SuperHardMode then
				    return TL("h8c24778bgd971g422dgabf1g744b89d35669")
				else 
				    return TL("hcdb6a75eg98e3g4f20gbfe8g5946ddca7b64")
				end
            end
        end, "StateChange")


        Components.Computed(mapName, function(box, state)
            if state.Scenario then
                local _, act = table.find(C.Regions, function(region)
                    return region == state.Scenario.Map.Region
                end)

                local mapName = state.Scenario.Map.Name
                if state.Scenario.Map.Author then
                    mapName = TL("h3b4890a6g6e1dg4c5fgb087gba3952a5981b", state.Scenario.Map.Author, mapName)
                end

                return TL("h3cf1646eg69a4g4313gb0fcg2575d2de0757", string.format("%s - %s", mapName, act))
            end
        end, "StateChange")

        layout.Cells[1][1]:AddButton(TL("h327e121eg672bg4474gb014gd212d236f030")).OnClick = function()
            Event.Trigger("Stop")
        end

        layout.Cells[1][1]:AddButton(TL("h3160102eg6435g4457gb025g3231d2071013")).OnClick = function()
            Event.Trigger("ToCamp")
        end

        Components.Conditional(layout.Cells[1][1], function(cond)
            local btn = cond.Root:AddButton(TL("h3097f93eg65c2g4ac6gb03ag4ca0d2186e82"))

            local t = btn:Tooltip()
            t:SetStyle("WindowPadding", 30, 10)
            t:AddText(TL("hf7517eadga204g42bfg8c46g24d9ee6406fb"))

            btn.SameLine = true
            btn.OnClick = function(button)
                Event.Trigger("ForwardCombat")
            end

            cond.OnEvent = function(state)
                return state.Scenario and state.Scenario.OnMap
            end

            return btn
        end, "StateChange")

        layout.Cells[1][3]:AddButton(TL("h25531a42g7006g44f1gb166g0297134420b5")).OnClick = function()
            Event.Trigger("Teleport", { Map = State.Scenario.Map.Name, Restrict = true })
        end

        -- layout.Cells[1][2]:AddButton(TL("h315e322eg640bg4677gb026gd011d204f233")).OnClick = function()
        --     Event.Trigger("PingSpawns", { Map = State.Scenario.Map.Name })
        -- end

        layout.Cells[1][3]:AddButton(TL("h24936cf3g71c6g439aga17ag05fc035827de")).OnClick = function()
            Event.Trigger("MarkSpawns", { Map = State.Scenario.Map.Name })
        end

        Components.Conditional(layout.Cells[1][3], function(cond)
            local grp = cond.Root:AddGroup(TL("h366718e6g6332g44dbgb055g42bd5277609f"))

            grp:AddButton(TL("h2d5b4e72g780eg41b2gb1e6g87d413c4a5f6")).OnClick = function()
                Net.Send("KillSpawned")
            end

            grp:AddButton(TL("h315e322eg640bg4677gb026gd011d204f233")).OnClick = function()
                Event.Trigger("PingSpawns", { Map = State.Scenario.Map.Name })
            end

            return grp
        end, "ToggleDebug").Update(Mod.Debug)
    end)
end
