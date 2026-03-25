# Archipelago BG3 Trials

This repo builds a Trials of Tav focused Archipelago integration for Baldur's Gate 3.

Instead of using the normal BG3 quest pool, this world treats Trials activity as the main progression path. Clears, kills, perfect runs, RogueScore milestones, and randomized tav shop purchases become Archipelago checks.

## Core Gameplay Model

Supported victory goals:

- Buy `NG+` / `Quick Start`
- Clear `X` Trials stages
- Reach `X` RogueScore

Supported check groups:

- Clear thresholds
- Kill thresholds
- Perfect clear thresholds
- RogueScore thresholds
- Shop purchase checks

Shop behavior:

- A configured number of Trials shop entries are replaced with Archipelago shop checks.
- Buying one of those entries sends a `TOT-SHOP-*` location check.
- The original reward is removed from the local purchase.
- That reward instead becomes an Archipelago item and is granted when received from the multiworld.
- `NG+ / Quick Start` stays local so it can still act as a win condition.

## Tester Setup

Most testers do not need the source repo. Just download the [[latest release]([url](https://github.com/Zoltun456/Archipelago-BG3-ToT/releases))](https://github.com/Zoltun456/Archipelago-BG3-ToT/releases) zip from GitHub and install the files it contains.

### 1. Download and extract the latest release

Download:

- `Archipelago-BG3-Trials-test-bundle.zip`

from the latest GitHub Release and extract it somewhere convenient.

The archive contains:

- `bg3tot.apworld`
- `CombatMod.pak`
- `Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5.pak`
- `ArchipelagoTrials.pak`
- `bg3_trials_test.yaml`
- `INSTALL.txt`

### 2. Install the AP world

Copy:

- `bg3tot.apworld`

into your Archipelago `custom_worlds` folder.

### 3. Install the BG3 mods

Copy these three paks into:

`%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods`

- `CombatMod.pak`
- `Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5.pak`
- `ArchipelagoTrials.pak`

### 4. Set BG3 Mod Manager load order

Use this order in BG3MM:

1. `Trials of Tav - Reloaded`
2. `Archipelago`
3. `Archipelago Trials Bridge`

Then:

1. Save Load Order
2. Export Order to Game
3. Launch BG3 from BG3MM

### 5. Generate a seed

Use the included sample YAML:

- `bg3_trials_test.yaml`

or edit your own YAML with the BG3 Trials options.

In Archipelago, this world appears in the game list as:

- `Baldur's Gate 3 - ToT`

This keeps it separate from the original BG3 Archipelago world.

### 6. Play and connect

Recommended test flow:

1. Launch BG3 with the three mods active.
2. Load into camp or tav mode.
3. Connect the BG3 Archipelago client.
4. Start Trials and play normally to earn checks.

## Important Files To Edit

### `trials_unlock_catalog.json`

Main gameplay tuning file for Trials reward items.

Use it to control:

- which Trials rewards can appear in the AP pool
- their AP classification
- how many copies of each reward exist
- optional reference metadata like vanilla `base_cost`

### `build_config.json`

Main build and sample-config file.

Use it to control:

- sample YAML defaults
- goal defaults
- check counts and intervals
- default shop price range
- trap defaults
- mod metadata and dependency versions

### `apworld_templates/bg3/options.py`

Defines the AP-side player options and their descriptions.

### `combatmod_patch/`

Contains the Trials-side patch that rewires the shop UI, reward handling, icon usage, and AP synchronization.

### `compat_mod/`

Contains the lightweight Archipelago bridge mod source.

## Option Notes

Key options that affect balance the most:

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
- `traps_percentage`
- `enabled_traps`

Shop prices are currently seeded pure-random values, rounded to multiples of `10`, within the configured min/max range.

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

## Build

Build the full bundle:

```powershell
.\build.ps1 -Clean
```

Or use Python directly:

```powershell
python tools\build_release.py build --clean
```

If you only changed configuration or source files and want to refresh outputs without clearing everything first:

```powershell
.\build.ps1
```

If you want to force fresh upstream clones:

```powershell
.\build.ps1 -Clean -RefreshCache
```

## What The Build Produces

Running the build creates a ready-to-test bundle in `dist/`:

- `dist/apworlds/bg3tot.apworld`
- `dist/bg3_mods/CombatMod.pak`
- `dist/bg3_mods/Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5.pak`
- `dist/bg3_mods/ArchipelagoTrials.pak`
- `dist/release/Archipelago-BG3-Trials-test-bundle.zip`
- `dist/player_yaml/bg3_trials_test.yaml`
- `dist/INSTALL.txt`
- `dist/build_manifest.json`

`CombatMod.pak` is the patched Trials of Tav - Reloaded mod used by this integration. The Archipelago pak and bridge pak are also rebuilt as part of the bundle.
The release zip contains the 4 required test files plus `INSTALL.txt` and the sample YAML, so it is the easiest file to upload to a GitHub Release.

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

## Repo Notes

- `tools/` bundles Norbyte ExportTool and the supporting files needed to package BG3 mods.
- `.cache/`, `dist/`, and `tmp/` are local build output and are safe to ignore in git.
- The release layout is intentionally three BG3 paks plus one `bg3tot.apworld`; collapsing everything into one BG3 mod would currently be a much riskier structural merge.
