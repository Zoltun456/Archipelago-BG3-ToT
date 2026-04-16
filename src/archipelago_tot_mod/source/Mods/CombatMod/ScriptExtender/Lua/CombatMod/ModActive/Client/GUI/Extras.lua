Extras = {}

function Extras.Main(tab)
    ---@type ExtuiTabItem
    local root = tab:AddTabItem(TL("h20891676g75dcg4432gb13bga25453198076")):AddChildWindow(""):AddGroup("")
    root.PositionOffset = { 5, 5 }
    root:AddSeparatorText(TL("h3550957ag6005g4c02gb066g3a6492441846"))

    Components.Conditional(root:AddGroup(U.RandomId()), function(c)
        return {
            Extras.Button(c.Root, TL("h3372643cg6627g4316g9004g1570f2263752"), "", function(btn)
                Net.Request("ClearSurfaces"):After(DisplayResponse)
            end),
            Extras.Button(c.Root, TL("h835e50a0gd60bg405fg9b06gd6393924f41b"), "", function(btn)
                Net.Request("RemoveAllEntities"):After(DisplayResponse)
            end),
        }
    end, "ToggleDebug")

    root:AddSeparator()
    Extras.Button(root, TL("h2af0133ag7fa5g4466gb19cg320093be1022"), TL("hf762a093ga237g4f5cgac45g193a0e673b18"), function(btn)
        Net.Request("CancelLongRest"):After(DisplayResponse)
    end)

    root:AddSeparator()
    Extras.Button(root, TL("h2f6f8b9cg7a3ag4decg91c5gcb8af3e7e9a8"), TL("h83573dd3gd602g4688gab06g40ee092462cc"), function(btn)
        Net.Request("CancelDialog"):After(DisplayResponse)
    end)

    root:AddSeparatorText(TL("hfafd2f0cgafa8g47a5g9c9cge1c3febec3e1"))
    root:AddDummy(1, 1)
    for name, char in pairs(C.OriginCharacters) do
        local desc = ""

        local b = Extras.Button(root, name, desc, function(btn)
            Net.Request("RecruitOrigin", name):After(DisplayResponse)
        end)

        b.SameLine = true
    end
    root:AddText(TL("h8810864dgdd45g4d31g8bb2g3b57e9901975"))
    root:AddText(TL("h5bd81560g0e8dg4403g968egb26534ac9047"))
    root:AddText(TL("h5d8139c8g08d4g46c9g96ebg20afb4c9028d"))

    root:AddSeparator()
    Extras.Button(root, TL("h2f8e40d4g7adbg4158g91cbgd73e73e9f51c"), TL("h0d1402fbg5841g457aga3e2g731c81c0513e"), function(btn)
        Net.Request("FixFactions"):After(DisplayResponse)
    end)

    root:AddSeparator()
    Extras.Button(root, TL("h2c31139ag7964g446cgb1f0g220a93d20028"), TL("h87eefe1cgd2bbg4ab4g9b4dgdcd2f96ffef0"), function(btn)
        Net.Request("FixLongRest"):After(DisplayResponse)
    end)

    root:AddSeparatorText(TL("h3720b0ceg6275g4e59gb041g383fd2631a1d"))
    root:AddInputInt(TL("h374141e6g6214g414bgb047g272d5265050f"), State.RogueScore or 0).OnChange = Debounce(1000, function(input)
        Net.RCE("PersistentVars.RogueScore = %d", input.Value[1]):After(function()
            Net.Send("SyncState")
        end)
    end)

    root:AddInputInt(TL("h2169b15eg743cg4e40gb125ga826d3078a04"), State.Currency or 0).OnChange = Debounce(1000, function(input)
        Net.RCE("PersistentVars.Currency = %d", input.Value[1]):After(function()
            Net.Send("SyncState")
        end)
    end)

    local input = root:AddInputInt(U.RandomId(), 0)
    input.Label = ""
    local btn = root:AddButton(TL("h2feb2fb2g7abeg47aegb1cdg81c813efa3ea"))
    btn.SameLine = true
    btn.OnClick = function(btn)
        Net.RCE("Player.GiveExperience(%d)", input.Value[1]):After(function()
            Net.Send("SyncState")
        end)
    end
end

function Extras.Button(root, text, desc, callback)
    local root = root:AddGroup("")

    local b = root:AddButton(text)
    b.IDContext = U.RandomId()
    b.OnClick = callback

    if desc then
        for i, s in ipairs(string.split(desc, "\n")) do
            if s ~= "" then
                root:AddText(s).SameLine = i == 1
            end
        end
    end

    return root
end
