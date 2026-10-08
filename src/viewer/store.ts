import { callable } from "@decky/api";
import { useSyncExternalStore } from "react";
import type { Reply } from "../types";
import type { Character, Progress, Reference, SavedBuild } from "./types";

export const savedBuilds = callable<[], Reply<SavedBuild[]>>("list_saved_builds");
export const characters = callable<[], Reply<Character[]>>("list_characters");
export const saveCharacter = callable<[string | null, string], Reply<Character>>("save_character");
export const deleteCharacter = callable<[string], Reply<boolean>>("delete_character");
const getReference = callable<[string, number], Reply<Reference>>("get_build_reference");
const getProgress = callable<[string, string, number, number], Reply<Progress>>("get_paragon_progress");
const setProgress = callable<[string, string, number, number, string[]], Reply<Progress>>("set_paragon_progress");
export function unwrap<T>(reply: Reply<T>): T { if (!reply.ok) throw new Error(reply.error); return reply.data; }
export type Tab = "gear" | "skills" | "paragon";
export interface Preferences { tab: Tab; skillStep: number; paragonStep: number; board: number; gear: number; skillZoom: number; paragonZoom: number; selected: string | null; list: boolean }
const defaults: Preferences = { tab: "gear", skillStep: 0, paragonStep: 0, board: 0, gear: 0, skillZoom: 1, paragonZoom: 1, selected: null, list: false };
interface State {
  reference: Reference | null; loading: boolean; error: string | null; preferences: Preferences;
  characters: Character[]; characterId: string | null; progress: Progress | null;
  progressScope: string | null; progressLoading: boolean; progressSaving: boolean; progressError: string | null;
}
let state: State = { reference: null, loading: false, error: null, preferences: { ...defaults }, characters: [], characterId: null,
  progress: null, progressScope: null, progressLoading: false, progressSaving: false, progressError: null };
const listeners = new Set<() => void>();
const retained = new Map<string, Preferences>();
const viewedVariants = new Map<string, number>();
export function lastVariant(id: string, fallback: number) { return viewedVariants.get(id) ?? fallback; }
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function useViewer() { return useSyncExternalStore(subscribe, () => state); }
export function snapshot() { return state; }
export function update(change: Partial<State>) { state = { ...state, ...change }; listeners.forEach(l => l()); }
export function preference(change: Partial<Preferences>) {
  if (Object.entries(change).every(([key, value]) => Object.is(state.preferences[key as keyof Preferences], value))) return;
  update({ preferences: { ...state.preferences, ...change } });
  if (state.reference) retained.set(`${state.reference.id}:${state.reference.variantId}`, state.preferences);
}
let loadSequence = 0;
export async function loadReference(id: string, variant: number) {
  const seq = ++loadSequence;
  update({ loading: true, error: null, progress: null, progressScope: null, progressError: null });
  try {
    const reference = unwrap(await getReference(id, variant));
    if (seq !== loadSequence) return;
    viewedVariants.set(id, reference.variantId);
    const old = retained.get(`${id}:${variant}`);
    const prefs = old ? { ...old } : { ...defaults, skillStep: reference.skills.activeStep, paragonStep: reference.paragon.activeStep };
    prefs.skillStep = Math.min(prefs.skillStep, Math.max(0, reference.skills.steps.length - 1));
    prefs.paragonStep = Math.min(prefs.paragonStep, Math.max(0, reference.paragon.steps.length - 1));
    prefs.board = Math.min(prefs.board, Math.max(0, (reference.paragon.steps[prefs.paragonStep]?.boards.length ?? 1) - 1));
    prefs.gear = Math.min(prefs.gear, Math.max(0, reference.gear.length - 1));
    update({ reference, loading: false, preferences: prefs });
  } catch (e) { if (seq === loadSequence) update({ loading: false, error: e instanceof Error ? e.message : "Could not load this build." }); }
}
export async function loadCharacters() {
  let list = unwrap(await characters());
  if (!list.length) list = [unwrap(await saveCharacter(null, "My character"))];
  update({ characters: list, characterId: list.some(c => c.id === state.characterId) ? state.characterId : list[0].id });
}
export function scope() {
  const r = state.reference;
  return r && state.characterId ? `${state.characterId}:${r.id}:${r.variantId}:${state.preferences.paragonStep}` : null;
}
let progressSequence = 0;
let writes: Promise<void> = Promise.resolve();
const failedWrites = new Map<string, { completed: string[]; error: string }>();
export async function loadProgress() {
  const r = state.reference, character = state.characterId, key = scope(), step = state.preferences.paragonStep;
  if (!r || !character || !key || !r.paragon.steps[step]) return;
  const seq = ++progressSequence;
  update({ progressScope: key, progress: null, progressLoading: true, progressSaving: false, progressError: null });
  try {
    await writes.catch(() => {});
    const progress = unwrap(await getProgress(character, r.id, r.variantId, step));
    const failed = failedWrites.get(key);
    if (failed) {
      const allocated = new Set(r.paragon.steps[step].boards.flatMap(b => b.allocations.map(n => n.key)));
      progress.completed = failed.completed.filter(node => allocated.has(node));
    }
    if (key === scope() && seq === progressSequence) update({ progress, progressLoading: false, progressError: failed?.error ?? null });
  } catch (e) { if (key === scope() && seq === progressSequence) update({ progressLoading: false, progressError: e instanceof Error ? e.message : "Checklist unavailable." }); }
}
export function saveProgress(completed: string[]) {
  const r = state.reference, character = state.characterId, key = scope(), step = state.preferences.paragonStep;
  if (!r || !character || !key || !state.progress || state.progressScope !== key || state.loading) return;
  const seq = ++progressSequence;
  update({ progress: { ...state.progress, completed }, progressSaving: true, progressError: null });
  writes = writes.catch(() => {}).then(async () => {
    try {
      const progress = unwrap(await setProgress(character, r.id, r.variantId, step, completed));
      failedWrites.delete(key);
      if (key === scope() && seq === progressSequence) update({ progress, progressSaving: false });
    } catch (e) {
      const error = e instanceof Error ? e.message : "Checklist could not be saved.";
      failedWrites.set(key, { completed, error });
      if (key === scope() && seq === progressSequence) update({ progressSaving: false, progressError: error });
    }
  });
}
export function toggleNode(key: string) {
  const p = state.progress;
  if (!p || state.progressLoading || state.progressScope !== scope() || state.loading) return;
  const completed = new Set(p.completed);
  completed.has(key) ? completed.delete(key) : completed.add(key);
  saveProgress(Array.from(completed));
}
