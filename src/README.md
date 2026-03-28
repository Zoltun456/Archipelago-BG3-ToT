# Source Layout

`apworld/bg3tot/`

AP world and client source that gets staged into `bg3tot.apworld`.

`archipelago_tot_mod/overlay/`

Repo-owned BG3 mod overlay copied into the final `ArchipelagoToT.pak`.

The inner folder is still `Mods/CombatMod/...` on purpose. The final packaged mod keeps the original Trials module folder and UUID for compatibility, even though the visible mod name and pak file are now `Archipelago - Trials of Tav` and `ArchipelagoToT.pak`.
