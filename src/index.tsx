import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, TextField, ToggleField, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { Component, useEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode, type ErrorInfo } from "react";
import { FaGem } from "react-icons/fa";
import type { Build, Catalogue, CopyResult, FilterDetail, FilterSummary, Reply } from "./types";

const listFilters = callable<[refresh: boolean], Reply<Catalogue>>("list_filters");
const getFilter = callable<[id: string], Reply<FilterDetail>>("get_filter");
const loadBuild = callable<[url: string], Reply<Build>>("load_build");
const generateFilter = callable<[id: string, variant: number, strict: boolean, name: string | null], Reply<FilterDetail>>("generate_filter");
const copyFilter = callable<[id: string], Reply<CopyResult>>("copy_filter");

const gold = "#dfb878";
const small: CSSProperties = { fontSize: 12, lineHeight: 1.5, color: "#b9c2cf", overflowWrap: "anywhere" };
const card: CSSProperties = { padding: "10px 12px", margin: "6px 0", border: "1px solid #39414e", borderRadius: 6, background: "#18202b" };
function unwrap<T>(reply: Reply<T>): T {
  if (!reply.ok) throw new Error(reply.error);
  return reply.data;
}
function date(value: string | null): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}
function Note({ children }: { children: ReactNode }) {
  return <PanelSectionRow><div style={small}>{children}</div></PanelSectionRow>;
}
function Select({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return <PanelSectionRow><DropdownItem label={label} selectedOption={value}
    rgOptions={values.map(data => ({ label: data, data }))}
    onChange={option => onChange(String(option.data))} /></PanelSectionRow>;
}
function unique(values: string[]): string[] {
  return ["Any", ...Array.from(new Set(values)).filter(v => v && v !== "Any").sort()];
}

// Steam can unmount the quick-access panel while its native dropdown menu is
// open. Keep selections outside that panel so the menu's callback still updates
// the next mounted view, rather than a discarded React component.
const panelState = {
  tab: "browse" as "browse" | "generate", catalogue: null as Catalogue | null,
  detail: null as FilterDetail | null, query: "", className: "Any", buildName: "Any",
  stage: "Any", strictness: "Any", season: "Any", advanced: false, limit: 12,
  url: "", build: null as Build | null, variant: 0, strict: false, name: "",
  showCode: false, copyStatus: null as string | null,
};
const panelListeners = new Set<() => void>();
function subscribePanel(listener: () => void) {
  panelListeners.add(listener);
  return () => { panelListeners.delete(listener); };
}
function usePanelState<K extends keyof typeof panelState>(key: K): [typeof panelState[K], (value: typeof panelState[K]) => void] {
  const value = useSyncExternalStore(subscribePanel, () => panelState[key]);
  return [value, next => {
    if (Object.is(panelState[key], next)) return;
    panelState[key] = next;
    panelListeners.forEach(listener => listener());
  }];
}

class PanelBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state: { error: string | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[Diablo Loot Filters] Panel rendering failed", error.message, info.componentStack);
  }
  render() {
    if (this.state.error) {
      return <div style={{ padding: 16, ...small }}><strong style={{ color: gold }}>The filter panel could not open.</strong>
        <p>{this.state.error}</p><p>Return to Decky. Your game and other plugins remain available.</p>
        <button onClick={() => this.setState({ error: null })}>Retry panel</button>
      </div>;
    }
    return this.props.children;
  }
}

function Content() {
  const [tab, setTab] = usePanelState("tab");
  const [catalogue, setCatalogue] = usePanelState("catalogue");
  const [detail, setDetail] = usePanelState("detail");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = usePanelState("query");
  const [className, setClass] = usePanelState("className");
  const [buildName, setBuildName] = usePanelState("buildName");
  const [stage, setStage] = usePanelState("stage");
  const [strictness, setStrictness] = usePanelState("strictness");
  const [season, setSeason] = usePanelState("season");
  const [advanced, setAdvanced] = usePanelState("advanced");
  const [limit, setLimit] = usePanelState("limit");
  const [url, setUrl] = usePanelState("url");
  const [build, setBuild] = usePanelState("build");
  const [variant, setVariant] = usePanelState("variant");
  const [strict, setStrict] = usePanelState("strict");
  const [name, setName] = usePanelState("name");
  const [showCode, setShowCode] = usePanelState("showCode");
  const [copyStatus, setCopyStatus] = usePanelState("copyStatus");
  const mounted = useRef(true);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await action(); }
    catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Request failed. Please retry."); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function refresh(force: boolean) {
    const result = unwrap(await listFilters(force));
    if (mounted.current) setCatalogue(result);
  }
  useEffect(() => {
    mounted.current = true;
    void run(() => refresh(false));
    return () => { mounted.current = false; };
  }, []);

  async function open(item: FilterSummary) {
    await run(async () => {
      const result = unwrap(await getFilter(item.id));
      if (mounted.current) { setDetail(result); setShowCode(false); setCopyStatus(null); }
    });
  }
  async function copy() {
    if (!detail) return;
    await run(async () => {
      let browserCopied = false;
      try { await navigator.clipboard.writeText(detail.code); browserCopied = true; } catch { /* Xwayland helper below. */ }
      const reply = await copyFilter(detail.id);
      let result: CopyResult | null = null;
      if (reply.ok) result = reply.data;
      if (!result?.copied && !browserCopied) throw new Error(result?.error ?? (!reply.ok ? reply.error : "Clipboard unavailable. Show the code to copy manually."));
      if (result?.gameDetected && !result.gameCopied) throw new Error("Copied to Steam, but Diablo’s clipboard could not be reached. " + (result.error ?? ""));
      const status = result?.gameCopied ? "Copied to Diablo’s clipboard. Close Decky and paste into Import Loot Filter." : "Copied. Open Diablo’s Import Loot Filter dialog and paste the code.";
      setCopyStatus(status);
      toaster.toast({ title: "Loot filter copied", body: status });
    });
  }
  const filters = catalogue?.filters ?? [];
  const classFilters = filters.filter(f => className === "Any" || f.className === className || f.className === "All");
  const matches = classFilters.filter(f => (buildName === "Any" || f.buildName === buildName)
    && (stage === "Any" || f.stage === stage) && (strictness === "Any" || f.strictness === strictness)
    && (season === "Any" || f.season === season)
    && `${f.title} ${f.buildName} ${f.creator}`.toLowerCase().includes(query.toLowerCase().trim()));
  function filterButton(item: FilterSummary) {
    return <PanelSectionRow key={item.id}><ButtonItem layout="below" disabled={busy} onClick={() => void open(item)}
      description={`${item.className} · ${item.season} · ${item.strictness} · ${item.origin}`}>
      {item.title}
    </ButtonItem></PanelSectionRow>;
  }

  return <>
    <PanelSection>
      <Note><span style={{ color: gold }}>DIABLO IV</span> · Native loot filters</Note>
      {detail ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => { setDetail(null); setCopyStatus(null); }}>← Back to {tab === "browse" ? "filters" : "build"}</ButtonItem></PanelSectionRow>
        : <PanelSectionRow><ButtonItem disabled={busy} onClick={() => { setTab(tab === "browse" ? "generate" : "browse"); setError(null); }}>
          {tab === "browse" ? "Generate from a Maxroll build →" : "← Browse published filters"}
        </ButtonItem></PanelSectionRow>}
      {busy && <Note>Working…</Note>}
      {error && <Note><span style={{ color: "#ffb5a8" }}>{error}</span></Note>}
    </PanelSection>

    {detail ? <>
      <PanelSection title="Selected filter">
        <Note><div style={{ color: gold, fontSize: 16, fontWeight: 600 }}>{detail.title}</div>
          {detail.className} · {detail.season} · {detail.strictness}<br />
          {detail.origin} · {detail.preview.ruleCount}/25 rules<br />
          Source: {detail.sourceName} · {detail.creator}<br />
          Updated/checked: {date(detail.updatedAt)}<br />
          {detail.verification}<br />
          {detail.sourceUrl}
        </Note>
        {detail.diagnostics.length > 0 && <Note><div style={card}><strong style={{ color: gold }}>Mapping notes</strong>
          {detail.diagnostics.map((message, i) => <div key={i}>{message}</div>)}
          <div>Unmapped gear remains visible in Highlight mode.</div>
        </div></Note>}
        <PanelSectionRow><ButtonItem disabled={busy} layout="below" onClick={() => void copy()}>Copy import code</ButtonItem></PanelSectionRow>
        {copyStatus && <Note><span style={{ color: gold }}>{copyStatus}</span></Note>}
        <Note>In Diablo: Options → Gameplay → Loot Filter → New Filter → Import Loot Filter. Paste with Ctrl+V or the Steam keyboard’s Paste key, then save and activate the filter.</Note>
        <PanelSectionRow><ButtonItem onClick={() => setShowCode(!showCode)}>{showCode ? "Hide import code" : "Show import code"}</ButtonItem></PanelSectionRow>
        {showCode && <Note><div style={{ ...card, fontFamily: "monospace", wordBreak: "break-all", userSelect: "text" }}>{detail.code}</div></Note>}
      </PanelSection>
      <PanelSection title="Rules · first match wins">
        {detail.preview.rules.map((rule, index) => <Note key={index}><div style={{ ...card, borderLeft: `3px solid ${rule.color ?? "#6f7b8c"}` }}>
          <strong style={{ color: "#e5e9ef" }}>{index + 1}. {rule.name}</strong>
          <div>{rule.action}{rule.enabled ? "" : " · Disabled"}</div>
          {rule.conditions.map((condition, i) => <div key={i}>{condition}</div>)}
        </div></Note>)}
      </PanelSection>
    </> : tab === "browse" ? <>
      <PanelSection title="Find your filter">
        <Select label="Class" value={className} values={unique(filters.map(f => f.className))} onChange={value => { setClass(value); setBuildName("Any"); setLimit(12); }} />
        <Select label="Build" value={buildName} values={unique(classFilters.map(f => f.buildName))} onChange={value => { setBuildName(value); setLimit(12); }} />
        <PanelSectionRow><TextField label="Search" description="Build or creator" value={query} onChange={e => { setQuery(e.target.value); setLimit(12); }} /></PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={!query} onClick={() => { setQuery(""); setLimit(12); }}>Clear search</ButtonItem></PanelSectionRow>
        <PanelSectionRow><ToggleField label="More filters" checked={advanced} onChange={setAdvanced} /></PanelSectionRow>
        {advanced && <>
          <Select label="Stage" value={stage} values={unique(filters.map(f => f.stage))} onChange={setStage} />
          <Select label="Strictness" value={strictness} values={unique(filters.map(f => f.strictness))} onChange={setStrictness} />
          <Select label="Season" value={season} values={unique(filters.map(f => f.season))} onChange={setSeason} />
        </>}
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void run(() => refresh(true))}>Refresh catalogue</ButtonItem></PanelSectionRow>
        <Note>{catalogue?.stale ? "Cached catalogue" : "Catalogue"} · fetched {date(catalogue?.fetchedAt ?? null)}<br />
          Seasonal compatibility and verification are reported by the source. Preview the rules before importing.</Note>
        {catalogue?.error && <Note>{catalogue.error}</Note>}
        {!!catalogue?.rejected && <Note>{catalogue.rejected} invalid codes were excluded.</Note>}
      </PanelSection>
      <PanelSection title={`${matches.length} filters`}>
        {matches.slice(0, limit).map(filterButton)}
        {!busy && matches.length === 0 && <Note>No matches. Change your selections or generate from a Maxroll build.</Note>}
        {matches.length > limit && <PanelSectionRow><ButtonItem onClick={() => setLimit(limit + 12)}>Show more filters</ButtonItem></PanelSectionRow>}
      </PanelSection>
    </> : <>
      <PanelSection title="Maxroll build">
        <Note>Paste a Diablo IV guide or planner link. Choose its published filter or generate one for a specific gear variant.</Note>
        <PanelSectionRow><TextField label="Build URL" description="https://maxroll.gg/d4/build-guides/… or /d4/planner/…" value={url} onChange={e => { setUrl(e.target.value); setBuild(null); }} /></PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={busy || !url.trim()} onClick={() => void run(async () => {
          const result = unwrap(await loadBuild(url));
          setBuild(result); setVariant(result.activeVariant); setStrict(false); setName("");
        })}>Load build</ButtonItem></PanelSectionRow>
        {build && <>
          <Note><strong style={{ color: gold }}>{build.name}</strong><br />{build.className} · {build.season} · fetched {date(build.fetchedAt)}{build.stale ? " · Cached" : ""}</Note>
          {build.error && <Note>{build.error}</Note>}
          <PanelSectionRow><DropdownItem label="Variant" selectedOption={variant} rgOptions={build.variants.map(v => ({ label: v.name, data: v.id }))} onChange={option => setVariant(Number(option.data))} /></PanelSectionRow>
          <PanelSectionRow><TextField label="Filter name" description="Optional · up to 30 characters" value={name} onChange={e => setName(e.target.value.slice(0, 30))} /></PanelSectionRow>
          <PanelSectionRow><ToggleField label="Strict hiding" description={strict ? "Hide gear outside this build. Requires complete mappings." : "Highlight matches; keep other gear visible."} checked={strict} onChange={setStrict} /></PanelSectionRow>
          <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void run(async () => {
            const result = unwrap(await generateFilter(build.id, variant, strict, name.trim() || null));
            setDetail(result); setShowCode(false); setCopyStatus(null);
          })}>{strict ? "Generate strict filter" : "Generate highlight filter"}</ButtonItem></PanelSectionRow>
        </>}
      </PanelSection>
      {build && <PanelSection title="Published in this planner">
        {build.publishedFilters.map(filterButton)}
        {build.rejectedFilters > 0 && <Note>{build.rejectedFilters} invalid published code(s) were excluded.</Note>}
        {build.publishedFilters.length === 0 && <Note>This planner has no published filter codes. Generate from a variant above.</Note>}
        <Note>Published filters retain their author’s rules and may hide gear.</Note>
      </PanelSection>}
    </>}
  </>;
}

export default definePlugin(() => ({
  name: "Diablo Loot Filters",
  titleView: <div className={staticClasses.Title}>Diablo Loot Filters</div>,
  content: <PanelBoundary><Content /></PanelBoundary>,
  icon: <FaGem />,
  onDismount() { /* Backend owners survive panel closure and stop on plugin unload. */ },
}));
