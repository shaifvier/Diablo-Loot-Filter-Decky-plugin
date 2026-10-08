# Diablo Loot Filters for Decky

Browse published Diablo IV loot filters by class and build, preview their rules,
and copy an import code without leaving Steam game mode. You can also paste a
Maxroll guide or planner URL, choose a gear variant, and generate a native filter.

Designed first for **CachyOS + gamescope + Battle.net via NonSteamLaunchers**.
The same display-based clipboard path supports Diablo IV launched directly from
Steam on Linux/SteamOS. The backend requires no pip packages or browser runtime.

## Install

1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Download `diablo-loot-filters-v0.1.0.zip` from this repository's
   [Releases](https://github.com/shaifvier/Diablo-Loot-Filter-Decky-plugin/releases).
3. In game mode, open Decky settings → Developer, enable developer mode if
   needed, and choose **Install Plugin from ZIP**. Use the release asset's URL:
   `https://github.com/shaifvier/Diablo-Loot-Filter-Decky-plugin/releases/download/v0.1.0/diablo-loot-filters-v0.1.0.zip`.
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

## Development

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
