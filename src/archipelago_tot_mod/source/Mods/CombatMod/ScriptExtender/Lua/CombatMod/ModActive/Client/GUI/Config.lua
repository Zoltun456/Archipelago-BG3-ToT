Config = {}

---@param tab ExtuiTabBar
function Config.Main(tab)
    ---@type ExtuiTabItem
    local root = tab:AddTabItem(TL("h23c73e06g7692g46b5gb10fg40d3532d62f1")):AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }

    Net.Send("Config")

    Config.Client(root)

    root:AddSeparatorText(TL("h501f8202g054ag4d75gb632gcb131410e931"))

    Config.Checkbox(
        root,
        "hac065c23gf953g4097ga9f3g56f10bd174d3",
        "hd27c8442g8729g4d11gbe14gfb771c36d955",
        "RoguelikeMode"
    )

    Config.Checkbox(
        root,
        "h26aa74f2g73ffg421agb159g947c137bb65e",
        "he5e0d749gb0b5g4821g8d6dg3e47af4f1c65",
        "HardMode"
    )

    Config.Checkbox(
        root,
        "h38cb985eg6d9eg4cd0gb0bfg8ab6d29da894",
        "hd3a90714g86fcg4524g9e09ga3427c2b8160",
        "SuperHardMode"
    )

    Config.Checkbox(
        root,
        "h21dd0d16g7488g4584gb12ege3e2530cc1c0",
        "h7db9022eg28ecg4577gb4e8ga311d6ca8133",
        "LoneWolfMode"
    )
	
	Config.Checkbox(
        root,
        "h37f1aaabg62a4g4fffga04cg2999826e0bbb",
        "h38b88b07g6dedg4de5ga0b8gbb83429a99a1",
        "GMMode"
    )

    Config.Checkbox(
        root,
        "h868cae89gd3d9g4fbdg8b5bgf9dba979dbf9",
        "hb77766a4ge222g433fg9844g45597a66677b",
        "SpawnItemsAtPlayer"
    )

    ---@type ExtuiCheckbox
    Config.Checkbox(
        root,
        "h29375bf8g7c62g40eag91a0g468cb38264ae",
        "h908239a1gc5d7g46cfg8a3bg10a92819328b",
        "BypassStory"
    )

    ---@type ExtuiCheckbox
    Config.Checkbox(
        root,
        "h3bc40171g6e91g4542g808fg732422ad5106",
        "hffb9fd3egaaecg4a86gbcc8gace0deea8ec2",
        "ClearAllEntities"
    )

    Config.Checkbox(root, "h9dc524a2gc890g471fgbaefg617918cd435b", "hf95a1c84gac0fg449dg9ca6g92fb7e84b0d9", "TurnOffNotifications")

    Config.Checkbox(
        root,
        "hfadaa9bfgaf8fg4fcegac9eg99a8cebcbb8a",
        "h7b7406d7g2e21g4538ga484g735e46a6517c",
        "MulitplayerRestrictUnlocks"
    )

    Config.Slider(
        root,
        "he699ae7dgb3ccg4fb2g8d5aga9d4ef788bf6",
        "ha4163608gf143g4635g9972g5053bb507271",
        "AutoTeleport",
        0,
        120
    )

    Config.Slider(
        root,
        "h1cd23d77g4987g4682ga2feg10e440dc32c6",
        "hf099a598ga5ccg4f0cg9c3aga96abe188b48",
        "ScalingModifier",
        0,
        100
    )

    Config.Slider(
        root,
        "hb823bf93ged76g4eacga8b1g08ca0a932ae8",
        "h004f93edg551ag4c6bg8337gca0de115e82f",
        "RandomizeSpawnOffset",
        0,
        30
    )

    Config.Slider(
        root,
        "h2c411dfcg7914g448ag91f7g22ecf3d500ce",
        "hc2671d37g9732g4486gaf15g42e04d3760c2",
        "ExpMultiplier",
        1,
        10
    )

    local c1 = Config.Checkbox(root, "h29620d0ag7c37g4585gb1a5g13e3938731c1", "h07417422g5214g4217gb347g247111650653", "Debug")
    c1.Checked = Mod.Debug

    local text = ""
    local function showStatus(msg, append)
        if append then
            if not text:match(msg) then
                text = text .. " " .. msg
            end
        else
            text = msg
        end

        Event.Trigger("Success", text)
    end

    Net.On("Config", function(event)
        Event.Trigger("ConfigChange", event.Payload)
    end)

    Event.On("ConfigChange", function(config)
        showStatus(TL("h2e624d0ag7b37g4185gb1d5g17e393f735c1"), true)

        Mod.Debug = config.Debug

        Event.Trigger("ToggleDebug", config.Debug)
    end)

    if not IsHost then
        return
    end

    -- buttons
    root:AddSeparator()
    local btn = root:AddButton(TL("h28cd5020g7d98g4057g91bfge631339dc413"))
    btn.OnClick = function()
        showStatus(TL("h4d21e11dg1874g4b44g87e1g2d22e5c30f00"))

        Net.Send("Config", {
            Persist = true,
        })
    end

    local btn = root:AddButton(TL("h3659a876g630cg4fd2gb056ga9b452748b96"))
    btn.SameLine = true
    btn.OnClick = function()
        showStatus(TL("h413f98d6g146ag4cd8gb720gcabe5502e89c"))

        Net.Send("Config", { Reset = true })
    end

    local btn = root:AddButton(TL("h29b77480g7ce2g421dg91a8g447b338a6659"))
    btn.SameLine = true
    btn.OnClick = function()
        showStatus(TL("h29895c61g7cdcg4093g81abga6f5238984d7"))

        Net.Send("Config", { Default = true })
    end

    Event.On("UpdateConfig", function(config)
        Net.Send("Config", config)

        showStatus(TL("h2f0de7b4g7a58g4b2eg91c3ged4873e1cf6a"))
    end)

    root:AddSeparator()
    local btn = root:AddButton(TL("h32554192g6700g414cgb016g672a12344508"))
    btn.OnClick = function()
        showStatus(TL("h8ccc2af7gd999g47fagabffgf19c49ddd3be"))
        Net.Request("ResetTemplates", { Maps = true, Scenarios = true, Enemies = true, LootRates = true })
            :After(function(event)
                Net.Send("GetTemplates")
                Net.Send("GetSelection")

                showStatus(TL("h2771ca17g7224g49f4ga144g2f9243660db0"), true)
            end)
    end
    root:AddText(TL("h7c764b2dg2923g41e7g84f4g5781e6d675a3")).SameLine = true

    root:AddDummy(1, 2)
end

function Config.Client(root)
    root:AddSeparatorText(TL("h2d89694ag78dcg43c1gb1ebga5a793c98785"))

    local c = root:AddCheckbox(TL("h3c609e26g6935g4cb7gb0f5g3ad152d718f3"))
    c.OnChange = function(ckb)
        Settings.AutoHide = ckb.Checked
    end
    c.Checked = Settings.AutoHide
    root:AddText(TL("h193979fag4c6cg42cagb2a0ga4ac9082868e"))

    local c = root:AddCheckbox(TL("h34411c36g6114g4496gb077g22f0525500d2"))
    c.OnChange = function(ckb)
        Settings.AutoOpen = ckb.Checked
    end
    c.Checked = Settings.AutoOpen
    root:AddText(TL("hd9d18c01g8c84g4d95g8eaeg2bf32c8c09d1"))

    local k = root:AddInputText(TL("h28a9d2d8g7dfcg4878g91b9gae1eb39b8c3c") .. " [A-Z]")
    k.OnChange = function(input)
        input.Text = input.Text:upper():sub(1, 1)
        if not input.Text:match("[A-Z]") then
            input.Text = "U"
        end

        Settings.ToggleKey = input.Text
    end
    k.Text = Settings.ToggleKey
    k.CharsNoBlank = true
    k.CharsUppercase = true
    k.AutoSelectAll = true
    k.AlwaysOverwrite = true
    k.ItemWidth = 25
end

function Config.Checkbox(root, label, desc, field, onChange)
    root:AddSeparator()
    local checkbox = root:AddCheckbox(TL(label))
    checkbox.IDContext = U.RandomId()
    root:AddText(TL(desc))

    local hostValue

    checkbox.OnChange = function(ckb)
        if not IsHost then
            ckb.Checked = hostValue
            return
        end

        if onChange then
            onChange(ckb)
        end

        Event.Trigger("UpdateConfig", { [field] = ckb.Checked })
    end

    Event.On("ConfigChange", function(config)
        checkbox.Checked = config[field]
        hostValue = config[field]
    end)

    return checkbox
end

function Config.Slider(root, label, desc, field, min, max, onChange)
    root:AddSeparator()
    local slider = root:AddSliderInt(TL(label), 0, min, max)
    root:AddText(TL(desc))

    local hostValue

    slider.OnChange = Debounce(500, function(sld)
        if not IsHost then
            sld.Value = { hostValue, 0, 0, 0 }
            return
        end

        if onChange then
            onChange(sld)
        end

        Event.Trigger("UpdateConfig", { [field] = sld.Value[1] })
    end)

    Event.On("ConfigChange", function(config)
        slider.Value = { config[field], 0, 0, 0 }
        hostValue = config[field]
    end)

    return slider
end
