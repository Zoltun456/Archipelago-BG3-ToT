# Baldur's Gate 3 - ToT

## Where is the options page?

The [player options page for this game](../player-options) contains the settings needed to export a YAML.

## What does randomization do in this world?

This world turns Trials of Tav activity into Archipelago progression.

Checks come from:

- Trial clear thresholds
- Kill thresholds
- Perfect clear thresholds
- RogueScore thresholds
- Randomized tav shop purchases

Buying an AP shop entry sends a location check. The original reward is moved into the Archipelago item pool and is
only granted when that AP item is received.

## What are the goals?

You can win by:

- Buying `NG+`
- Reaching a configured Trial clear target
- Reaching a configured RogueScore target

## How do traps work?

Trap items are filler that punish the current run instead of giving a normal reward.

Working trap types include direct status traps such as `Bleeding`, `Stun`, `Confusion`, `Bane`, `Blindness`,
`Slow`, `Poisoned`, `Faerie Fire`, `Ensnared`, `Frightened`, `Burning`, and `Hold Person`, a targeted polymorph
trap `Cheesed`, plus positional traps such as `Silence` and `Grease`.

Most status and targeted spell traps affect the full party, companions, and summons.

## What should players know before starting?

- This is a Trials of Tav focused world, not the standard Baldur's Gate 3 campaign Archipelago experience.
- You need the packaged BG3 mod alongside the AP world for checks, items, and notifications to function.
- DeathLink is optional and can be configured to send on full wipes, any party death, or any party down.

## What can appear in other players' worlds?

Trials unlocks, duplicated consumables, equipment fillers, currency-style fillers, RogueScore fillers, XP fillers,
and trap items can all be part of the Archipelago item pool.

## Is there anything else I should know?

- Shop prices are seeded per player and rounded to multiples of `10`.
- Trap shop entries are free.
- The first purchased `Get a Tadpole` works as the unlock, and later copies grant actual tadpoles.
- The in-game notification feed uses sequential counter labels like `Shop Check 1/50`.
