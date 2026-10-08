# Preview 0.2.0-beta.1 validation

Checked on 2026-10-08, CachyOS, gamescope, Decky Loader v3.2.9, Steam React 19.1.1.
Branch: `feature/build-viewer`, based on `v0.1.1`. Stable installation retained.

## Automated checks

- TypeScript checking and production preview Rollup build.
- 34 offline Python tests, including the previous 21 loot-filter/clipboard tests.
  New tests compare every Blood Wave and Rain of Arrows variant's skill ranks,
  upgrades, connections and paragon allocation sets against current fixtures.
  Zero-based board indexing, all four rotations, board order, glyphs/levels,
  separate tempering, readable common-node names and missing-geometry/identifier
  fallbacks are covered.
- Independent character, planner, variant and source-step checklists; restart
  persistence, reset, deletion, atomic save failure and changed-build reconciliation.
  Removed nodes are discarded, common completed nodes retained and changes flagged
  until reviewed. Source step names are preserved without adding a spending order.
- Cached references work offline with expired game metadata or only a saved
  projection. Fresh viewer metadata is reused for 24 hours. Provider failures
  preserve the cached reference and carry a stale-data message.
- Three Node tests cover late variant responses, retained viewer preferences,
  queued rapid checklist writes, switching characters during writes and retrying
  failed saves. Failed intent and errors remain available when returning to a
  character during the same plugin session.
- Preview seed copies selected public cache files once, excludes character data
  and retains independent writes. Packaging checks its exact frontend identity.
- Feature-branch CI repeats these checks, builds the preview ZIP and tests the X11
  helper under Xvfb with independent UTF8_STRING/STRING reads.

## Live Steam and gamescope checks

- Both **Diablo Loot Filters** and **Diablo Loot Filters Preview** appear in Decky.
  SHA-256 comparison of all 26 tracked installed stable files shows no changes.
  The stable runtime cache also remains unchanged after preview load, generation,
  checklist writes and clipboard copying.
- Preview starts in Decky's embedded Python, seeds Blood Wave and Rain of Arrows
  from copies of the stable cache and loads their normalized references through
  Decky's real RPC. Viewer game metadata reports version `3.1.3.73224`.
- Saved build selection and the filter-detail **View source build** action open
  the independent full-screen route. Gear, Skills and Paragon render for both
  builds. Rain of Arrows shows its six source-equipped skills and Devious glyph;
  Blood Wave shows its source skill bar and Corporeal glyph at level 100.
- All three tabs checked at **1280×800** and **1920×1080** in Steam's real Chromium
  UI using viewport emulation. Header/footer fit clear of Steam's chrome. Only
  the active diagram renders; Gear contains no map nodes. Source steps and boards
  remain selectable through native Steam dropdowns.
- Native Steam focus targets and spatial navigation: geometric Down moves from
  Blood Wave's node 10 to node 31, updates the inspector and reveals the selection.
  Registered tab/zoom/fit/mark/return handlers were exercised programmatically.
  Node mouse clicks open native Steam detail modals, which receive focus; closing
  details retains the viewer. Zoom retains the selected node in view.
- An allocated paragon node was marked via the registered X handler, persisted
  and remained completed after preview reinstallation. Source-step switching
  shows independent counts. Automated tests cover other characters and resets.
- Preview regression: Necromancer remains selected; Blood Wave is offered and
  stays selected in Build. A search with no matches clears correctly. The ninth
  Blood Wave Medium rule becomes fully visible when its native target is focused.
- The real generation button creates a Rain of Arrows Endgame highlight filter
  with 15 rules, no Hide rules, and diagnostics for unmapped seasonal items.
- The real Copy button transfers the exact 1,520-character, nine-rule Blood Wave
  Medium code to `:0` (Steam) and `:1` (Battle.net/NonSteamLaunchers Diablo).
  Independent UTF8_STRING and STRING reads match after closing Decky.
- No game files, launcher configuration or Proton prefixes were changed.

## Remaining acceptance checks

- Physical controller completion of all viewer controls is awaiting the user's
  feedback. Scripted native focus/handler checks do not establish every hardware
  input path. A physical Steam Deck has not been tested.
- The directly installed Steam edition is unavailable for an in-game test here.
  Preview paste acceptance inside Diablo's dialog was not repeated; exact code
  transport is verified. Prior stable behavior was reported working by the user.
- Some current seasonal item and affix names remain unmapped and show identifiers
  with diagnostics. Tooltip formulas are not evaluated; this is a reference
  viewer, not a calculation of character bonuses or damage.

---

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
