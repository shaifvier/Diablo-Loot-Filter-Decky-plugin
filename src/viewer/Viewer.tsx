import { DialogButton, Dropdown, Focusable, GamepadButton, ModalRoot, Navigation, showModal, TextField, type FocusableProps, type GamepadEvent, type ShowModalResult } from "@decky/ui";
import { callable, routerHook } from "@decky/api";
import manifest from "@decky/manifest";
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ComponentType, type ReactNode, type RefAttributes } from "react";
import type { Build, Reply } from "../types";
import type { Affix, Allocation, Board, Connection, GearItem, MapNode, SavedBuild } from "./types";
import { characters, deleteCharacter, lastVariant, loadCharacters, loadProgress, loadReference, preference, saveCharacter, savedBuilds,
  saveProgress, scope, snapshot, toggleNode, unwrap, update, useViewer, type Tab } from "./store";
import { styles } from "./styles";

const route = manifest.name.endsWith(" Preview") ? "/diablo-loot-filters-preview/build-viewer" : "/diablo-loot-filters/build-viewer";
const loadBuild = callable<[string], Reply<Build>>("load_build");
const NativeFocus = Focusable as ComponentType<FocusableProps & RefAttributes<HTMLDivElement> & { focusable?: boolean }>;
const tabs: Tab[] = ["gear", "skills", "paragon"];
const prettyDate = (value: string | null) => value ? new Date(value).toLocaleDateString() : "Unknown";
export function registerViewer() { routerHook.addRoute(route, ViewerBoundary); }
export function removeViewer() { routerHook.removeRoute(route); }
export async function openBuildViewer(id: string, variant: number) {
  Navigation.CloseSideMenus();
  Navigation.Navigate(route);
  await loadReference(id, variant);
}

function Sheet({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const modal = useRef<ShowModalResult | null>(null);
  const render = () => <ModalRoot onCancel={onClose} closeModal={onClose} bHideCloseIcon bAllowFullSize>
    <div className="d4-sheet">{children}</div>
  </ModalRoot>;
  useEffect(() => {
    modal.current = showModal(render(), undefined, { bNeverPopOut: true, strTitle: "Diablo build viewer" });
    return () => { modal.current?.Close(); modal.current = null; };
  }, []);
  useEffect(() => { modal.current?.Update(render()); });
  return null;
}

function Button({ children, onClick, disabled, active }: { children: ReactNode; onClick: () => void; disabled?: boolean; active?: boolean }) {
  return <DialogButton className={`d4-button${active ? " d4-tab-active" : ""}`} disabled={disabled} onClick={e => { e.stopPropagation(); onClick(); }}>{children}</DialogButton>;
}
function Readable({ children, selected, onActivate, onFocus, onSecondary, label }: {
  children: ReactNode; selected?: boolean; onActivate?: () => void; onFocus?: () => void; onSecondary?: () => void; label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reveal = () => { ref.current?.scrollIntoView({ block: "nearest", inline: "nearest" }); onFocus?.(); };
  return <NativeFocus ref={ref} focusable tabIndex={0} className={`d4-card d4-focus${selected ? " d4-card-selected" : ""}`}
    focusClassName="d4-native-focus" onFocus={reveal} onGamepadFocus={reveal} onActivate={onActivate}
    onSecondaryButton={onSecondary ? e => { e.stopPropagation(); onSecondary(); } : undefined}
    onSecondaryActionDescription={onSecondary ? "Mark copied / undo" : undefined} aria-label={label}>{children}</NativeFocus>;
}
function Select<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: { label: string; data: T }[]; onChange: (value: T) => void;
}) {
  return <div className="d4-control"><label>{label}</label>{options.length ? <Dropdown selectedOption={value} rgOptions={options}
    menuLabel={label} onChange={option => onChange(option.data as T)} /> : <div className="d4-muted">No {label.toLowerCase()} supplied.</div>}</div>;
}

export function SavedBuilds() {
  const [builds, setBuilds] = useState<SavedBuild[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { let alive = true; void savedBuilds().then(r => { if (alive) setBuilds(unwrap(r)); }).catch(e => { if (alive) setError(String(e)); }); return () => { alive = false; }; }, []);
  return <div style={{ margin: "8px 0" }}>
    {builds.map(b => <DialogButton key={b.id} style={{ width: "100%", margin: "0 0 8px", fontSize: 14 }} onClick={() => void openBuildViewer(b.id, lastVariant(b.id, b.activeVariant))}>
      {b.name}<div style={{ fontSize: 11 }}>{b.className} · {b.season}</div>
    </DialogButton>)}
    {error && <div>{error}</div>}
    {!error && !builds.length && <div>Load a Maxroll guide or planner link to save a build here.</div>}
  </div>;
}

function MapButton({ node, paragon, completed, selected, scale, size, x, y, onSelect, onOpen }: {
  node: MapNode; paragon: boolean; completed: boolean; selected: boolean; scale: number; size: number; x: number; y: number;
  onSelect: (node: MapNode) => void; onOpen: (node: MapNode) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const focus = () => { onSelect(node); ref.current?.scrollIntoView({ block: "nearest", inline: "nearest" }); };
  useEffect(() => { if (selected) ref.current?.scrollIntoView({ block: "nearest", inline: "nearest" }); }, [selected, scale]);
  const mark = () => { if (paragon && node.allocated && node.key) toggleNode(node.key); };
  const symbol = completed ? "✓" : paragon ? node.socket ? "◆" : node.gate ? "+" : node.rarity === 4 ? "★" : node.rarity === 3 ? "R" : "•" : node.rank || "•";
  return <NativeFocus ref={ref} focusable tabIndex={0} role="button" aria-label={`${node.name}${node.allocated ? ", allocated" : ""}${completed ? ", completed" : ""}`}
    data-node-id={node.id} data-node-key={node.key} className={`d4-node${node.allocated ? " allocated" : ""}${completed ? " completed" : ""}${selected ? " selected" : ""}`}
    focusClassName="d4-native-focus" onGamepadFocus={focus} onFocus={focus} onActivate={() => { onSelect(node); onOpen(node); }}
    onOKActionDescription="Node details" onSecondaryActionDescription={paragon && node.allocated ? "Mark copied / undo" : undefined}
    onSecondaryButton={paragon && node.allocated ? e => { e.stopPropagation(); mark(); } : undefined}
    style={{ width: size, height: size, left: x - size / 2, top: y - size / 2, fontSize: size * 0.55 }}>
    {symbol}
  </NativeFocus>;
}

function Diagram({ nodes, connections, paragon, zoom, completed, selectedId, onSelect, onOpen }: {
  nodes: MapNode[]; connections: Connection[]; paragon: boolean; zoom: number; completed: Set<string>; selectedId?: string;
  onSelect: (node: MapNode) => void; onOpen: (node: MapNode) => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ width: 640, height: 420 });
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const observer = new ResizeObserver(entries => { const b = entries[0].contentRect; if (b.width && b.height) setBox({ width: b.width, height: b.height }); });
    observer.observe(el); return () => observer.disconnect();
  }, []);
  const geometry = useMemo(() => {
    const pad = paragon ? 24 : 8;
    const points = [...nodes, ...connections.flatMap(e => e.corners)];
    const minX = points.length ? Math.min(...points.map(n => n.x)) : 0, minY = points.length ? Math.min(...points.map(n => n.y)) : 0;
    const width = (points.length ? Math.max(...points.map(n => n.x)) : 1) - minX + 2 * pad;
    const height = (points.length ? Math.max(...points.map(n => n.y)) : 1) - minY + 2 * pad;
    return { pad, minX, minY, width, height, byId: new Map(nodes.map(n => [n.id, n])) };
  }, [nodes, connections, paragon]);
  const fit = Math.min((box.width - 14) / geometry.width, (box.height - 14) / geometry.height);
  const scale = Math.max(0.05, fit * zoom);
  const x = (v: number) => v - geometry.minX + geometry.pad;
  const y = (v: number) => v - geometry.minY + geometry.pad;
  if (!nodes.length) return <Readable>No diagram is available. Use the allocation list.</Readable>;
  return <NativeFocus ref={viewport} className="d4-map" flow-children="grid" data-zoom={zoom}>
    <div style={{ width: Math.max(box.width - 4, geometry.width * scale), height: Math.max(box.height - 4, geometry.height * scale), position: "relative" }}>
      <div className="d4-map-layer" style={{ width: geometry.width, height: geometry.height, transform: `scale(${scale})`, marginLeft: Math.max(0, (box.width - geometry.width * scale) / 2) }}>
        <svg width={geometry.width} height={geometry.height} aria-hidden="true">
          {connections.map((edge, i) => {
            const a = geometry.byId.get(edge.from), b = geometry.byId.get(edge.to);
            if (!a || !b) return null;
            const points = [a, ...edge.corners, b].map(p => `${x(p.x)},${y(p.y)}`).join(" ");
            return <polyline key={i} points={points} fill="none" stroke={a.allocated && b.allocated ? "#d0a566" : "#425269"} strokeWidth={paragon ? 1.2 : 0.4} />;
          })}
          {nodes.filter(n => n.selectable === false).map(n => <circle key={n.id} cx={x(n.x)} cy={y(n.y)} r={1} fill="#8190a4" />)}
        </svg>
        {nodes.filter(n => n.selectable !== false).map(n => <MapButton key={n.id} node={n} paragon={paragon} completed={!!n.key && completed.has(n.key)} selected={selectedId === n.id} scale={scale}
          size={paragon ? 15 : n.allocated ? 5 : 3.5} x={x(n.x)} y={y(n.y)} onSelect={onSelect} onOpen={onOpen} />)}
      </div>
    </div>
  </NativeFocus>;
}

function Affixes({ title, rows }: { title: string; rows: Affix[] }) {
  if (!rows.length) return null;
  return <><h2>{title}</h2>{rows.map((r, i) => <Readable key={i}><strong>{r.greater ? "★ " : ""}{r.name}</strong>
    {!!r.rolls.length && <div className="d4-muted">Source rolls: {r.rolls.join(" / ")}</div>}
    {r.description && <div className="d4-muted">{r.description}</div>}
  </Readable>)}</>;
}
function GearDetails({ item }: { item: GearItem }) {
  return <><h2>{item.slot} · {item.name}</h2><p className="d4-muted">{item.mythic ? "Mythic · " : ""}Item power: {item.power ?? "Unknown"}</p>
    <Affixes title="Natural affixes" rows={item.natural} /><Affixes title="Implicit affixes" rows={item.implicit} />
    <Affixes title="Tempering" rows={item.tempered} /><Affixes title="Aspects" rows={item.aspects} />
    {!!item.sockets.length && <><h2>Sockets</h2>{item.sockets.map((s, i) => <Readable key={i}>{s}</Readable>)}</>}
  </>;
}

function NodeInfo({ node, board, completed }: { node: Allocation; board?: Board; completed: boolean }) {
  return <><h2>{node.name}</h2>
    <p>{node.rank !== undefined ? `Rank ${node.rank}${node.maxRank ? ` / ${node.maxRank}` : ""} · ${node.kind ?? "Skill"}` : node.allocated ? "Allocated by this build" : "Not allocated by this build"}</p>
    {node.description && <Readable>{node.description}</Readable>}
    {board && <p className="d4-muted">Board {board.order}: {board.name}<br />Glyph: {board.glyph.name} · level {board.glyph.level ?? "Unknown"}<br />Node {node.id}</p>}
    {board && node.allocated && node.key && <Button onClick={() => toggleNode(node.key!)}>{completed ? "Undo completed node" : "Mark copied to character"}</Button>}
  </>;
}

function CharacterSheet({ onClose }: { onClose: () => void }) {
  const s = useViewer();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const selected = s.characters.find(c => c.id === s.characterId);
  const perform = async (operation: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await operation(); const list = unwrap(await characters()); update({ characters: list }); setName(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save character."); }
    finally { setBusy(false); }
  };
  return <Sheet onClose={onClose}>
    <h2>Character checklists</h2><p className="d4-muted">Local profiles keep your characters’ paragon progress separate. Mark nodes manually as you copy them in Diablo.</p>
    <TextField label="Character name" value={name} onChange={e => setName(e.target.value.slice(0, 40))} />
    <div className="d4-row" style={{ marginTop: 15 }}>
      <Button disabled={busy || !name.trim()} onClick={() => void perform(async () => { const c = unwrap(await saveCharacter(null, name)); update({ characterId: c.id }); })}>Add character</Button>
      <Button disabled={busy || !name.trim() || !selected} onClick={() => void perform(async () => { unwrap(await saveCharacter(selected!.id, name)); })}>Rename {selected?.name ?? "character"}</Button>
    </div>
    <div style={{ marginTop: 15 }}><Select label="Active character" value={s.characterId ?? ""} options={s.characters.map(c => ({ label: c.name, data: c.id }))} onChange={id => { update({ characterId: id }); setConfirmDelete(false); }} /></div>
    {error && <p className="d4-error">{error}</p>}
    {confirmDelete ? <Readable><p>Delete {selected?.name} and all their checklists?</p><div className="d4-row">
      <Button disabled={busy} onClick={() => void perform(async () => { unwrap(await deleteCharacter(selected!.id)); update({ characterId: null }); await loadCharacters(); setConfirmDelete(false); })}>Delete character</Button>
      <Button onClick={() => setConfirmDelete(false)}>Keep character</Button>
    </div></Readable> : <div style={{ margin: "16px 0" }}><Button disabled={busy || !selected} onClick={() => setConfirmDelete(true)}>Delete selected character…</Button></div>}
    <Button onClick={onClose}>Done</Button>
  </Sheet>;
}

function Viewer() {
  const s = useViewer(), r = s.reference, p = s.preferences;
  const [characterSheet, setCharacterSheet] = useState(false);
  const [details, setDetails] = useState<MapNode | null>(null);
  const [diagnostics, setDiagnostics] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  useEffect(() => { void loadCharacters().catch(e => update({ error: String(e) })); }, []);
  useEffect(() => { if (r && s.characterId && !s.loading && p.tab === "paragon") void loadProgress(); }, [r, s.characterId, s.loading, p.tab, p.paragonStep]);
  const board = r?.paragon.steps[p.paragonStep]?.boards[p.board];
  const skill = r?.skills.steps[p.skillStep];
  const paragon = p.tab === "paragon";
  const nodes = paragon ? board?.nodes ?? [] : skill?.nodes ?? [];
  const allocations = paragon ? board?.allocations ?? [] : skill?.allocations ?? [];
  const prefix = `${p.tab}:${paragon ? p.paragonStep : p.skillStep}:${paragon ? p.board : 0}:`;
  const selected = nodes.find(n => prefix + n.id === p.selected) ?? allocations.find(n => prefix + n.id === p.selected);
  const completed = useMemo(() => new Set(s.progressScope === scope() ? s.progress?.completed ?? [] : []), [s.progress, s.progressScope, s.characterId, r, p.paragonStep]);
  const choose = useCallback((n: MapNode) => preference({ selected: `${snapshot().preferences.tab}:${snapshot().preferences.tab === "paragon" ? snapshot().preferences.paragonStep : snapshot().preferences.skillStep}:${snapshot().preferences.tab === "paragon" ? snapshot().preferences.board : 0}:${n.id}` }), []);
  const openDetails = useCallback((n: MapNode) => setDetails(n), []);
  const zoom = paragon ? p.paragonZoom : p.skillZoom;
  const setZoom = (value: number) => preference(paragon ? { paragonZoom: Math.max(0.5, Math.min(8, value)) } : { skillZoom: Math.max(0.5, Math.min(8, value)) });
  const back = () => {
    if (details) setDetails(null);
    else if (characterSheet) setCharacterSheet(false);
    else if (diagnostics) setDiagnostics(false);
    else if (confirmReset) setConfirmReset(false);
    else Navigation.NavigateBack();
  };
  const buttons = (e: GamepadEvent) => {
    if (details || characterSheet || diagnostics || confirmReset) return;
    let handled = true;
    switch (e.detail.button) {
      case GamepadButton.BUMPER_LEFT: preference({ tab: tabs[(tabs.indexOf(p.tab) + 2) % 3] }); break;
      case GamepadButton.BUMPER_RIGHT: preference({ tab: tabs[(tabs.indexOf(p.tab) + 1) % 3] }); break;
      case GamepadButton.TRIGGER_LEFT: if (p.tab !== "gear") setZoom(zoom / 1.4); break;
      case GamepadButton.TRIGGER_RIGHT: if (p.tab !== "gear") setZoom(zoom * 1.4); break;
      case GamepadButton.OPTIONS: if (p.tab !== "gear") setZoom(1); break;
      default: handled = false;
    }
    if (handled) e.stopPropagation();
  };
  const refresh = async () => {
    if (!r) return;
    update({ loading: true, error: null });
    try {
      const b = unwrap(await loadBuild(r.sourceUrl ?? `https://maxroll.gg/d4/planner/${r.id}`));
      await loadReference(r.id, r.variantId);
      if (b.stale) update({ error: "Using cached build. " + (b.error ?? "Provider unavailable.") });
    } catch (e) { update({ loading: false, error: e instanceof Error ? e.message : "Refresh failed." }); }
  };
  return <NativeFocus className="d4-viewer" flow-children="column" onButtonDown={buttons} onCancelButton={e => { e.stopPropagation(); back(); }}>
    <style>{styles}</style>
    <div className="d4-row" style={{ justifyContent: "space-between" }}>
      <div><h1>{r?.name ?? "Maxroll build viewer"}</h1><div className="d4-muted">{r ? `${r.className} · ${r.season} · ${r.variantName} · Maxroll` : "Load a saved build from Decky"}</div></div>
      <div className="d4-row"><Button disabled={s.loading || !r} onClick={() => void refresh()}>Refresh build</Button><Button onClick={back}>Back to game</Button></div>
    </div>
    {s.error && <Readable><span className="d4-error">{s.error}</span></Readable>}
    {s.loading && <div className="d4-note">Loading build reference…</div>}
    {r && <>
      <div className="d4-controls">
        <Select label="Variant" value={r.variantId} options={r.variants.map(v => ({ label: v.name, data: v.id }))} onChange={v => { setDetails(null); void loadReference(r.id, v); }} />
        <Select label="Character checklist" value={s.characterId ?? ""} options={s.characters.map(c => ({ label: c.name, data: c.id }))} onChange={id => update({ characterId: id })} />
        <Button onClick={() => setCharacterSheet(true)}>Manage characters</Button>
        <div className="d4-muted" style={{ marginLeft: "auto" }}>Updated {prettyDate(r.updatedAt)} · fetched {prettyDate(r.fetchedAt)}<br />
          {r.stale ? "Cached reference · " : ""}{r.diagnostics.length ? <Button onClick={() => setDiagnostics(true)}>{r.diagnostics.length} mapping notes</Button> : "Source allocations"}</div>
      </div>
      {r.error && <div className="d4-note">{r.error}</div>}
      <div className="d4-toolbar">
        {tabs.map(t => <Button key={t} active={p.tab === t} onClick={() => preference({ tab: t })}>{t[0].toUpperCase() + t.slice(1)}</Button>)}
        {p.tab !== "gear" && <>
          <Button onClick={() => preference({ list: !p.list })}>{p.list ? "Show diagram" : "Allocation list"}</Button>
          <Button onClick={() => setZoom(zoom / 1.4)}>Zoom −</Button><Button onClick={() => setZoom(zoom * 1.4)}>Zoom +</Button>
          <Button onClick={() => setZoom(1)}>Fit map</Button>
          <span className="d4-muted">{Math.round(zoom * 100)}%</span>
        </>}
      </div>
      {p.tab === "gear" ? <div className="d4-workspace">
        <div className="d4-main d4-scroll">{r.gear.map((g, i) => <Readable key={i} selected={i === p.gear} onActivate={() => preference({ gear: i })} onFocus={() => preference({ gear: i })}>
          <strong>{g.slot}</strong><div>{g.name}</div><div className="d4-muted">{g.mythic ? "Mythic · " : ""}Power {g.power ?? "Unknown"} · {g.natural.length} natural affixes · {g.tempered.length} tempered</div>
        </Readable>)}{!r.gear.length && <Readable>This variant has no equipment.</Readable>}</div>
        <div className="d4-side">{r.gear[p.gear] && <GearDetails item={r.gear[p.gear]} />}</div>
      </div> : <>
        <div className="d4-controls" style={{ marginTop: 0 }}>
          <Select label={paragon ? "Paragon step" : "Skill step"} value={paragon ? p.paragonStep : p.skillStep}
            options={(paragon ? r.paragon.steps : r.skills.steps).map(step => ({ label: step.name, data: step.id }))}
            onChange={id => { setDetails(null); preference(paragon ? { paragonStep: id, board: 0, selected: null } : { skillStep: id, selected: null }); }} />
          {paragon && <Select label="Board" value={p.board} options={(r.paragon.steps[p.paragonStep]?.boards ?? []).map((b, i) => ({ label: `${b.order}. ${b.name}`, data: i }))}
            onChange={id => { setDetails(null); preference({ board: id, selected: null }); }} />}
          {paragon && <div className="d4-muted">{completed.size} / {s.progress?.total ?? "…"} nodes copied for this step<br />
            {board && `${board.allocations.filter(n => n.key && completed.has(n.key)).length} / ${board.allocations.length} on this board`}
            {s.progressSaving ? " · Saving…" : s.progressLoading ? " · Loading checklist…" : ""}</div>}
          {paragon && <Button disabled={!s.progress || s.progressLoading || s.loading} onClick={() => setConfirmReset(true)}>Reset step checklist…</Button>}
        </div>
        {s.progressError && paragon && <div className="d4-note d4-error">Checklist not saved: {s.progressError} <Button onClick={() => s.progress ? saveProgress(s.progress.completed) : void loadProgress()}>Retry</Button></div>}
        {s.progress?.needsReview && paragon && <div className="d4-note">The source allocation changed. Shared completed nodes were kept; review this setup. <Button onClick={() => saveProgress(s.progress!.completed)}>Reviewed changes</Button></div>}
        <div className="d4-workspace">
          <div className="d4-main">
            {paragon && board && <div className="d4-muted" style={{ marginBottom: 8 }}>Board {board.order} · rotation {board.rotation * 90}° clockwise · {board.glyph.name} · glyph level {board.glyph.level ?? "Unknown"}</div>}
            {!paragon && <div className="d4-muted" style={{ marginBottom: 8 }}>{r.skills.bar.map(b => b.name).join(" · ")}</div>}
            {p.list ? <div className="d4-scroll">{allocations.map(n => <Readable key={n.id} selected={prefix + n.id === p.selected} onActivate={() => { preference({ selected: prefix + n.id }); if (n.x !== undefined && n.y !== undefined) setDetails(n as MapNode); }}
              onFocus={() => preference({ selected: prefix + n.id })} onSecondary={paragon && n.key ? () => toggleNode(n.key!) : undefined}>
              <strong>{n.key && completed.has(n.key) ? "✓ " : ""}{n.name}</strong><div className="d4-muted">{n.rank !== undefined ? `Rank ${n.rank}${n.maxRank ? ` / ${n.maxRank}` : ""}` : `Node ${n.id}`}</div>
              {paragon && n.key && <Button disabled={s.progressLoading || !s.progress || s.loading} onClick={() => toggleNode(n.key!)}>{completed.has(n.key) ? "Undo mark" : "Mark copied"}</Button>}
            </Readable>)}{!allocations.length && <Readable>No allocations in this step.</Readable>}</div>
              : <Diagram nodes={nodes} connections={paragon ? board?.connections ?? [] : skill?.connections ?? []} paragon={paragon} zoom={zoom} completed={completed} selectedId={selected?.id} onSelect={choose} onOpen={openDetails} />}
          </div>
          <div className="d4-side">
            {selected ? <NodeInfo node={selected} board={paragon ? board : undefined} completed={!!selected.key && completed.has(selected.key)} />
              : <Readable><h2>{paragon ? "Follow the board" : "Skill allocations"}</h2>Choose a node to see its name and allocation. Gold nodes are selected by the build; green nodes are marked copied.</Readable>}
            {!paragon && !!r.skills.mechanics.length && <Readable>{r.skills.mechanics.map((m, i) => <p key={i}>{m}</p>)}</Readable>}
            <Readable><strong>{allocations.length} allocated nodes</strong><p className="d4-muted">These are the author’s recorded allocations. Numeric effects depend on your character; this viewer does not calculate damage or bonuses.</p></Readable>
          </div>
        </div>
      </>}
      <div className="d4-footer">LB/RB Tabs · D-pad Select · LT/RT Zoom · Y Fit · A Details · X Mark paragon · B Back<br />
        <span style={{ fontSize: 11 }}>{r.sourceUrl} · Game data {r.gameVersion ?? "Unknown"}</span></div>
    </>}
    {characterSheet && <CharacterSheet onClose={() => setCharacterSheet(false)} />}
    {details && <Sheet onClose={() => setDetails(null)}>
      <NodeInfo node={details} board={paragon ? board : undefined} completed={!!details.key && completed.has(details.key)} /><div style={{ marginTop: 15 }}><Button onClick={() => setDetails(null)}>Back to map</Button></div>
    </Sheet>}
    {diagnostics && <Sheet onClose={() => setDiagnostics(false)}>
      <h2>Source mapping notes</h2><div className="d4-scroll">{r?.diagnostics.map((d, i) => <Readable key={i}>{d}</Readable>)}</div><Button onClick={() => setDiagnostics(false)}>Close notes</Button>
    </Sheet>}
    {confirmReset && <Sheet onClose={() => setConfirmReset(false)}>
      <h2>Reset this step’s checklist?</h2><p>Clear completed nodes for {s.characters.find(c => c.id === s.characterId)?.name}, {r?.variantName}, {r?.paragon.steps[p.paragonStep]?.name}. Other characters and steps keep their progress.</p>
      <div className="d4-row"><Button onClick={() => { saveProgress([]); setConfirmReset(false); }}>Reset checklist</Button><Button onClick={() => setConfirmReset(false)}>Keep progress</Button></div>
    </Sheet>}
  </NativeFocus>;
}

class ViewerBoundary extends Component<Record<string, never>, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  componentDidCatch(error: Error) { console.error("[Diablo build viewer]", error); }
  render() {
    if (this.state.error) return <NativeFocus className="d4-viewer" onCancelButton={() => Navigation.NavigateBack()}><style>{styles}</style>
      <h1>Build viewer unavailable</h1><p>{this.state.error}</p><Button onClick={() => this.setState({ error: null })}>Retry viewer</Button><Button onClick={() => Navigation.NavigateBack()}>Back to game</Button>
    </NativeFocus>;
    return <Viewer />;
  }
}
