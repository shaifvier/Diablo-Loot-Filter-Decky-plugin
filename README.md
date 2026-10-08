# Diablo Loot Filters Preview · 0.2.0-beta.1

This feature branch adds a full-screen Maxroll build reference viewer with
**Gear, Skills and Paragon** tabs and manual character checklists. It is based on
`v0.1.1`; the stable release and `main` remain available separately.

## Install the preview

1. Download `diablo-loot-filters-preview-v0.2.0-beta.1.zip` from the
   [beta release](https://github.com/shaifvier/Diablo-Loot-Filter-Decky-plugin/releases/tag/v0.2.0-beta.1).
2. Open Decky settings → Developer → **Install Plugin from ZIP** and select the
   downloaded local ZIP. Its URL is also available on the release page.
3. Open **Diablo Loot Filters Preview**. Keep **Diablo Loot Filters** installed
   for the stable loot-filter experience.

The preview has its own plugin identity, full-screen route, runtime cache and
character-progress files. On first start it copies public saved filters and
builds from the stable cache if available. Those copies become independent;
preview refreshes, generation and checklists never write to the stable cache.
Installing or uninstalling the preview does not replace the stable plugin.

## View a build

Open **Saved builds · full-screen viewer**, then choose a saved build. To add one,
use the existing Maxroll guide/planner loader, select a variant and press
**View build · full screen**. A Maxroll published filter's details also offer
**View source build**. English Maxroll references are supported in this beta.

- **Gear:** equipment by slot, item names, natural and implicit affixes, separate
  tempering, aspects, source rolls and sockets when the planner supplies them.
- **Skills:** equipped skill bar, source steps, allocated ranks and upgrades,
  zoomable connected tree and allocation list. Select a node to read its details.
- **Paragon:** one board at a time, source board order and clockwise rotation,
  allocated nodes, glyph and level, source steps and an allocation list.

| Controller | Action |
| --- | --- |
| LB / RB | Previous / next tab |
| D-pad | Move between native focus targets, including map nodes |
| LT / RT | Zoom out / in |
| Y | Fit map |
| A | Open node details / activate control |
| X | Mark an allocated paragon node completed, or undo the mark |
| B | Close details / return to the previous Steam screen |

Visible buttons, dropdowns and clickable map nodes provide mouse/touch controls.
Returning to the viewer preserves the selected build, variant, tab, source step,
board and zoom during the plugin session. Only the active diagram is rendered.
Steam's Back action returns to the previous screen; when opened over a running
game, close any remaining Steam overlay to resume playing.

## Character checklists and source changes

Use **Manage characters** to add, rename or delete named local profiles. Progress
is independent for each character, planner, variant and author-provided paragon
step. Completion counts show the current board and selected step's entire setup.
**Reset step checklist** affects only that scope and asks for confirmation.
Writes are queued and atomic. Save failures remain visible with a Retry action.

Refreshes retain completed nodes still allocated by the updated source, discard
removed allocations and flag changed board setups for review. No point-by-point
spending order is inferred from the author's allocations. This is a reference
viewer with manual tracking: no build editing, automatic character detection or
damage simulation is included.

Viewer game metadata refreshes after 24 hours in a separate cache. Previously
loaded references remain usable offline, with fetched/update dates and stale-data
messages. Unknown identifiers stay visible with mapping notes; missing geometry
falls back to the allocation list. Labels, ranks, rolls and levels come from
Maxroll; tooltip formulas are not evaluated. Seasonal changes can leave item or
affix names unmapped. Mapping does not certify a build or filter in-game.

Preview data lives in Decky's `data/diablo-loot-filters-preview/cache` and
`data/diablo-loot-filters-preview/viewer` directories. Removing a character deletes
only that character's local checklists. Back up `viewer/characters.json` and
`viewer/progress.json` if you want to keep them across removal of plugin data.

## Develop the preview

Use Node.js 22, pnpm 9.15.9, Python 3.11+, a C compiler and X11 development headers.

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build:preview
pnpm package:preview
```

The beta ZIP and SHA-256 checksum are written to `artifacts/`. Feature-branch CI
checks types, backend fixtures and progress persistence, frontend write queues,
packaging and clipboard ownership under Xvfb. See [VALIDATION.md](VALIDATION.md)
for the live Steam checks and remaining hardware/game checks.

---

# Loot-filter features inherited from v0.1.1

Browse published Diablo IV loot filters by class and build, preview their rules,
and copy an import code without leaving Steam game mode. You can also paste a
Maxroll guide or planner URL, choose a gear variant, and generate a native filter.

Designed first for **CachyOS + gamescope + Battle.net via NonSteamLaunchers**.
The same display-based clipboard path supports Diablo IV launched directly from
Steam on Linux/SteamOS. The backend requires no pip packages or browser runtime.

## Install

1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Download `diablo-loot-filters-v0.1.1.zip` from this repository's
   [Releases](https://github.com/shaifvier/Diablo-Loot-Filter-Decky-plugin/releases).
3. In game mode, open Decky settings → Developer, enable developer mode if
   needed, and choose **Install Plugin from ZIP**. Use the release asset's URL:
   `https://github.com/shaifvier/Diablo-Loot-Filter-Decky-plugin/releases/download/v0.1.1/diablo-loot-filters-v0.1.1.zip`.
4. Open **Diablo Loot Filters** in the Decky panel.

The ZIP contains a `diablo-loot-filters/` directory, the compiled frontend, Python
backend, licenses, versioned game identifier tables and an x86_64 Linux clipboard
helper. Its system dependency is `libX11.so.6`, supplied by gamescope systems.
No game files, Proton prefix files, Steam shortcuts, or launcher configuration
are modified.

## Browse and import

- Choose **Class** and **Build**, or search by name/creator. **More filters** adds
  stage, strictness and season selectors. General `All`-class filters remain
  available alongside the selected class's filters.
- Open a filter to inspect its source, season, checked date and ordered rules.
  Move down with the D-pad or left stick to focus each rule and scroll the preview.
  The first matching rule wins. Published codes retain their original rules.
- Press **Copy import code**, close Decky, and in Diablo open **Options →
  Gameplay → Loot Filter → New Filter → Import Loot Filter**. Paste with
  **Ctrl+V** or the Steam virtual keyboard's **Paste** key, then save and activate.

The plugin finds the running `Diablo IV.exe` process and copies to its actual X11
display, independently of Steam app IDs or Proton prefix names. It also copies
to Steam's display. This handles NonSteamLaunchers sessions where Steam uses
`:0` and the game uses `:1`. Clipboard ownership persists after the panel closes;
another copy operation or unloading the plugin ends ownership.

If copying fails, use **Show import code** and copy manually. Remote streaming
and a purely Wayland game without Xwayland are outside this release's clipboard
support. No keystrokes are injected into the game.

## Generate from Maxroll

Choose **Generate from a Maxroll build**, paste a Diablo IV build-guide or planner
URL, and load it. Published filters embedded in the planner are offered separately.
Malformed published codes are excluded and counted.

Choose a variant, optionally name the filter, and generate. The default
**Highlight** mode colors build matches, Codex upgrades and Greater Affixes while
keeping other loot visible. Unique equipment is matched by identifier, without
using its fixed affixes as legendary stat requirements. Only natural explicit
affixes are used; tempering, aspects and transfiguration effects are excluded.
Gear rules are scoped to the actual equipment types used in the variant.

**Strict hiding** is opt-in and requires complete item/affix mappings and fresh
affix data. Uniques and Mythics stay visible. Missing mappings are listed in the
preview; incomplete variants can still generate highlight-only filters. Current
runewords or new seasonal items may be unmapped until the bundled identifier
tables are updated. BiS rules are reduced first if needed to fit the game's
25-rule limit; generation refuses codes that still exceed it.

Source verification and seasonal compatibility are displayed as reported,
not inferred from valid encoding. Many catalogue entries are from older seasons.
Structural validation does **not** mean a code was tested in the current game.
Check the preview and the imported rules before using a filter for farming.

## Offline and provider changes

The catalogue refreshes on demand and after six hours. Successful catalogue,
planner and generated filters are cached in Decky's per-plugin runtime directory.
Failed refreshes retain the previous catalogue and show its fetched date and
error. Previously loaded planner and guide links work from cache when offline.
First-time generation needs network access for Maxroll's affix identifiers; those
identifiers are cached for 24 hours. Stale data is allowed only in Highlight mode.

The catalogue adapter parses public object literals from the site's discovered
content bundles. It never executes downloaded JavaScript. Maxroll's planner
endpoints are public but undocumented and may change. Provider failures appear
in the panel; generated and previously cached filters remain usable.

## Stable development

These commands apply to the `v0.1.1` checkout. On `feature/build-viewer`, use
the preview build/package commands above.

Use Node.js 22, pnpm 9.15.9, Python 3.11+, a C compiler and X11 development headers.
On Debian/Ubuntu the helper needs `libx11-dev`; on Arch/CachyOS use `libx11` and
`base-devel`. Python runtime compatibility is 3.9+.

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
pnpm package
```

The installation ZIP and SHA-256 checksum are written to `artifacts/`.
CI also tests clipboard persistence under Xvfb with `xclip` as an independent
clipboard reader. To run that check locally:

```sh
xvfb-run -a python3 tests/check_clipboard.py
```

No network access is needed for the unit tests. The fixtures preserve current
Maxroll gear/variant fields and a small catalogue excerpt, including a malformed
published code. See [VALIDATION.md](VALIDATION.md) for checks performed for this
release and remaining game-session acceptance checks.

`.credentials`, `.ccredentials`, environment files, caches, dependencies and
artifacts are excluded from Git. Packaging uses an explicit allowlist and does
not include any credential or development tool files.

## Attribution

MIT-licensed plugin, based on the Decky template and a pinned community native
filter encoder. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and included
licenses for upstream credit. Provider source URLs and creator metadata are
retained in the interface. Unofficial; not affiliated with Blizzard or Maxroll.
