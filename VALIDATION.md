# Release 0.1.1 validation

Checked on 2026-10-08, CachyOS, gamescope, Decky Loader v3.2.9, Steam React 19.1.1.

## Completed

- TypeScript type check and production Rollup build.
- 21 offline backend tests: literal catalogue parsing without execution, exact
  provider URL validation, the current Maxroll schema, eight variant generation,
  embedded malformed-code rejection, tempering exclusion, strict-mode mapping
  checks, rule budget/order, original-code preservation and offline caches.
- Live catalogue: 71 records discovered, 68 with usable public import codes.
- Live Maxroll Rain of Arrows planner: eight variants, two valid published codes;
  one malformed concatenated code excluded. Highlight generation succeeds and
  reports unmapped seasonal items rather than hiding them.
- Installed backend starts in Decky's embedded Python. Catalogue, planner
  loading and generation succeed through the real Decky frontend/backend RPC.
- Actual Steam UI rendering: browse view, filter detail view and Copy button.
  The panel stays responsive and does not trigger its error boundary.
- Native dropdown regression: choose Necromancer in Steam's popup, return to
  Decky and confirm 17 matching/class-independent filters; choose Minion
  Necromancer and confirm one matching filter. Both selections survive closing
  and reopening the quick-access panel.
- Search-clear regression: enter a query with no matches, press Clear search,
  and confirm the textbox empties and results return. The button is disabled
  when the query is empty.
- Rule scrolling regression: Blood Wave Maxroll Medium has nine rule cards,
  all registered as native focusable nodes. Steam's directional navigation can
  focus rules below the initial viewport; focusing the last card scrolls it fully
  into view. The user confirmed controller scrolling reaches all nine rules.
  The existing Decky scroll container remains in use.
- Persistent X11 transfer on live `:0` (Steam) and `:1` (Diablo IV through the
  NonSteamLaunchers Proton prefix), with independent UTF8_STRING and STRING reads.
- The real Copy button places the exact selected 1,324-character code on both
  CLIPBOARD selections, where it remains after closing Decky. The read-back code
  decodes to the same 17 rules as the selected catalogue entry.
- Installation ZIP contents are allowlisted; helper is executable and credentials,
  caches, tests and development dependencies are absent.

## Compatibility corrections during validation

The initial installation exposed two embedded-Python differences: `html.parser`
was absent, and Python did not discover CachyOS's system CA bundle. Script-source
extraction now uses a bounded same-origin pattern, and HTTPS explicitly uses the
system trust store with certificate verification enabled.

The user reported a Steam/Decky UI hang during the initial test. Steam's web UI
was recovered without terminating Diablo, and the user confirmed controls returned.
A React boundary now contains panel rendering failures. The corrected panel was
then exercised in the live Steam UI, including selection, preview, copy and closure.
This does not establish that TLS was the sole cause of the earlier UI hang.

The user then found that native dropdown choices reverted to Any. Steam closes
and remounts the quick-access panel while showing its native selection menu.
Panel state now survives that remount, including callbacks from the open menu;
the class and build regression above uses the real native menu options.

Rule previews initially contained static text after the final button, so
controller navigation had no further focus target to scroll to. Release 0.1.1
makes each rule a native focusable card and reveals it when focused.

## Not yet established

- Diablo's acceptance and activation of the import code inside its game dialog
  require the user's in-game confirmation. Clipboard transport and structural
  encoding are independently verified; they do not prove game acceptance.
- The directly installed Steam edition and a physical Steam Deck have not been
  tested. Display discovery covers both launcher paths without hardcoded app IDs.
- CI includes an isolated Xvfb/xclip test; its remote result is recorded separately
  by GitHub Actions.
- Codes from older seasons may not represent current build priorities. Unmapped
  new seasonal items keep strict generation disabled for those variants.
