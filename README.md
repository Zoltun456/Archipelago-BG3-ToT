# Archipelago BG3 Trials

This repo builds a Trials of Tav focused Archipelago integration for Baldur's Gate 3.

## Core Gameplay Model

Supported victory goals:

- Buy `NG+`
- Clear `X` Trials stages
- Reach `X` RogueScore

Supported check groups:

- Clear thresholds
- Kill thresholds
- Perfect clear thresholds
- RogueScore thresholds
- Shop purchase checks

## Install Guide:

### 1. Downloads

Download apworld and mod zip:
- [Archipelago-BG3-Trials-test-bundle.zip](https://github.com/Zoltun456/Archipelago-BG3-ToT/releases)
- [bg3tot.apworld](https://github.com/Zoltun456/Archipelago-BG3-ToT/releases)

Download dependency mods from Nexus:
- [Mod Configuration Menu](https://www.nexusmods.com/baldursgate3/mods/9162)
- [Expansion](https://www.nexusmods.com/baldursgate3/mods/279)
- [AdvancedTTSpells](https://www.nexusmods.com/baldursgate3/mods/14429)

Download BG3 Mod Manager:
- [BG3 Mod Manager](https://github.com/LaughingLeader/BG3ModManager)
### 2. Install the AP world

- Move `bg3tot.apworld` into your Archipelago `custom_worlds` folder. Or `Install APWorld` using the Archipelago client.
### 3. Install the BG3 mods

- Move `.pak` files from mod downloads into your BG3 `Mods` folder usually located at: `%LocalAppData%\Larian Studios\Baldur's Gate 3\Mods`

In [BG3 Mod Manager](https://github.com/LaughingLeader/BG3ModManager), enable mods in order (BG3MM has a nice guide on GIT if you need help setting it up):
1. `Mod Configuration Menu`
2. `Expansion`
3. `AdvancedTTSpells`
4. `Archipelago - Trials of Tav`

Then:
1. Save Load Order
2. Export Order to Game
3. Launch BG3 from BG3MM
### 4. Generate a seed

Make your YAML with the `Baldur's Gate 3 - ToT` options in the Archipelago launcher `Options Creator`.
### 5. Connect Archipelago client

Open `Baldur's Gate 3 - ToT Client` from inside the Archipelago launcher and connect to the Archipelago room.
### 6. Play

With the mods active and the client connected, create a new save and opt into all the in-game pop-ups for Trials of Tav. If everything is set up correctly, the shop items should be randomized apworld items.
## Option Notes

Key options that affect balance the most:

- `death_link`
- `death_link_trigger`
- `goal`
- `goal_clear_target`
- `goal_rogue_score_target`
- `clear_check_count`
- `kill_check_count`
- `perfect_check_count`
- `roguescore_check_count`
- `shop_check_count`
- `shop_price_minimum`
- `shop_price_maximum`
- `vanilla_pixie_blessing_in_shop`
- `permanent_buff_target`
- `traps_percentage`
- `enabled_traps`

Shop prices are seeded per player and rounded to multiples of `10`.
Pixie Blessing can optionally stay as its vanilla local 30-cost shop unlock instead of being randomized into the AP pool.
Character-bound useful AP unlocks can target the receiving player, a random party member, or the whole party.
Progression rewards keep their whole-party or global behavior, and the Roll Loot rewards ignore that setting.

DeathLink is optional and off by default. When enabled, received DeathLinks wipe the active party so the player has to reload, and the trigger mode can be set to:

- full party wipe
- any party member fully killed
- any party member downed

## Validation / Troubleshooting

Useful local files while testing:

- `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\ap_out.json`
- `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\ap_in.json`
- `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\ap_options.json`

If things are working, `ap_out.json` should show progress tokens like:

- `TOT-CLEAR-001`
- `TOT-KILLS-001`
- `TOT-PERFECT-001`
- `TOT-SHOP-001`
- `TOT-GOAL-001`

## Repo Layout

The repo is organized around four main areas now:

- `config/`
  Build config and gameplay tuning files.
- `src/apworld/bg3tot/`
  The AP world and client source that gets staged into `bg3tot.apworld`.
- `src/archipelago_tot_mod/`
  The BG3 mod that gets merged into the final `ArchipelagoToT.pak`.
- `assets/archipelago_branding/`
  Archipelago art assets used for the merged mod branding and shop icons.

Support files:

- `scripts/build_release.py`
  Main build script.
- `build.ps1`
  Small PowerShell wrapper around the Python build script.
- `tools/`
  Bundled third-party packaging tools. This is basically the repo-local toolchain.

## Important Files

### `config/trials_unlock_catalog.json`

Main gameplay tuning file for Trials reward items.

Use it to control:

- which Trials rewards can appear in the AP pool
- their AP classification
- how many copies of each reward exist

### `config/build_config.json`

Main build and sample-config file.

Use it to control:

- merged mod metadata
- sample YAML defaults
- goal defaults
- check counts and intervals
- default shop price range
- trap defaults
- the source path for the base Trials of Tav mod used during packaging

### `src/archipelago_tot_mod/overlay/`

Repo-owned Lua and asset overrides copied into the merged BG3 mod during build.

### `src/apworld/bg3tot/`

Repo-owned Archipelago world and client overrides layered on top of the upstream BG3 Archipelago world template.

## Build

Build the full bundle:

```powershell
.\build.ps1 -Clean
```

Or use Python directly:

```powershell
python scripts\build_release.py build --clean
```

Set `config/build_config.json -> test_bundle -> trials_mod_source` to your local `CombatMod.pak` or unpacked Trials of Tav folder if the build script cannot find it automatically.

If you only changed config or source files and want to refresh outputs without clearing everything first:

```powershell
.\build.ps1
```

If you want to force a fresh upstream Archipelago world clone:

```powershell
.\build.ps1 -Clean -RefreshCache
```

## What The Build Produces

Running the build creates a ready-to-test bundle in `dist/`:

- `dist/apworlds/bg3tot.apworld`
- `dist/bg3_mods/ArchipelagoToT.pak`
- `dist/release/Archipelago-BG3-Trials-test-bundle.zip`
- `dist/release/bg3tot.apworld`
- `dist/player_yaml/bg3_trials_test.yaml`
- `dist/INSTALL.txt`
- `dist/build_manifest.json`

## Repo Notes

- `tools/` bundles Norbyte ExportTool and the supporting files needed to package BG3 mods.
- `.cache/`, `dist/`, and `%TEMP%/` are local build output and are ignored in git.
- The old standalone bridge mod source is gone from the active repo layout. The repo now ships one repo-built BG3 pak and expects external gameplay dependencies to be installed separately.

## Acknowledgements / Credits

This repo builds on a lot of work from other people in the BG3 and Archipelago communities.

- **Trials of Tav** by **Hippo0o**
  - The original roguelike game mode that made this entire Trials-first AP direction possible.
- **Trials of Tav - Reloaded** by **celerev**
  - The modern maintained Trials base that this repo patches and builds against.
- **Archipelago** by the **ArchipelagoMW team**
  - The core multiworld randomizer framework, server, generator, launcher, and web tooling this project depends on.
- **BG3 Archipelago world and mod work** by **Broney**
  - This repo stages and patches the upstream BG3 Archipelago world and BG3 Archipelago mod rather than reimplementing them from scratch.
- **Archipelago Trials Bridge** metadata and compatibility layer in this repo
  - Built here as the glue between Trials activity and Archipelago checks/items.
- **Norbyte's Script Extender / ExportTool**
  - Required for the BG3 mod runtime and for packaging parts of the generated build bundle.
- **Larian Studios**
  - For Baldur's Gate 3 itself and the underlying game content/modding ecosystem this project builds on.

Reference sources used while putting this project together:

- [Trials of Tav - a roguelike mode](https://www.nexusmods.com/baldursgate3/mods/9907)
- [Trials of Tav - Reloaded](https://www.nexusmods.com/baldursgate3/mods/14430)
- [Archipelago](https://archipelago.gg/)
- [Archipelago BG3 world source](https://github.com/zane31415/ArchipelagoBG3)
- [BG3 Archipelago mod source](https://github.com/zane31415/BG3ArchipelagoMod)
- [Norbyte tools](https://github.com/Norbyte/lslib)

## Third-Party Assets & Licensing

This project includes assets from the Archipelago asset pack. `assets/archipelago_branding/LICENSE.txt`

These assets are © 2022 by Krista Corkos and Christopher Wilson and are licensed under the Creative Commons Attribution-NonCommercial 4.0 International License:
http://creativecommons.org/licenses/by-nc/4.0/

## License Notice

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License.

Some included assets are licensed separately by their original authors and retain their original licensing terms.

Commercial use of this project is not permitted.
