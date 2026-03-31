## BG3 Trials Setup

This world replaces the normal BG3 progression flow with a Trials of Tav focused Archipelago mode.

Checks come from Trials activity such as clears, kills, perfect clears, RogueScore milestones, and randomized tav shop purchases.

### Required Files

Install the generated AP world:

- `bg3tot.apworld`

Install this BG3 mod:

- `ArchipelagoToT.pak`

### BG3 Mod Manager Order

Enable:

1. `Archipelago - Trials of Tav`

After setting the order, save and export it to the game before launching.

### Archipelago Connection

Use the in-game `Archipelago Client` tab in the Trials GUI for:

1. room connection
2. disconnect
3. resync
4. log viewing

### Goals

- `buy_ng_plus`
  Buy the local `NG+ / Quick Start` shop unlock.
- `clear_stages`
  Complete the configured number of Trials clears.
- `reach_rogue_score`
  Reach the configured RogueScore total.

### Key Options

- `death_link`
  Enables Archipelago DeathLink for this slot.
- `death_link_trigger`
  Choose whether local DeathLinks send on a full party wipe, any party member death, or any party member down.
- `clear_check_count`, `kill_check_count`, `perfect_check_count`, `roguescore_check_count`
  Total number of checks available from each activity group.
- `*_check_interval`
  How often each activity awards a check.
- `shop_check_count`
  How many catalog entries are turned into AP shop checks.
- `shop_price_minimum`, `shop_price_maximum`
  Seeded random price range for AP shop entries, rounded to multiples of `10`.
- `vanilla_pixie_blessing_in_shop`
  Keeps Pixie Blessing as the normal local 30-cost shop unlock and removes it from the randomized AP shop pool.
- `permanent_buff_target`
  Character-bound useful AP unlocks can go to the receiving player, a random party member, or the whole party.
  Progression rewards keep their whole-party or global behavior, and the Roll Loot rewards ignore this setting.
- `traps_percentage`
  Percent of filler items that become traps.
- `enabled_traps`
  Trap types allowed in the filler pool.

### Shop Behavior

AP shop entries do not grant their original reward when purchased.

Instead:

1. Buying the entry sends a shop location check.
2. The original reward exists in the Archipelago item pool.
3. The reward is granted only when that AP item is received.

`NG+ / Quick Start` remains a normal local shop unlock.
If `vanilla_pixie_blessing_in_shop` is enabled, `Pixie Blessing` also stays as its normal local shop unlock.

### DeathLink Behavior

If DeathLink is enabled:

1. Local Trials deaths send a DeathLink based on the selected trigger mode.
2. Received DeathLinks wipe the active party.
3. The player then reloads their most recent save as normal.

### World Name

In Archipelago, this world appears as:

- `Baldur's Gate 3 - ToT`

This keeps it separate from the original BG3 Archipelago world.

### Validation

While playing, the merged mod writes progress to:

`%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\ap_out.json`

Working runs should produce entries like:

- `TOT-CLEAR-001`
- `TOT-KILLS-001`
- `TOT-PERFECT-001`
- `TOT-SHOP-001`
- `TOT-GOAL-001`
