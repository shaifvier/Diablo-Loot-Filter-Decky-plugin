export interface SavedBuild { id: string; name: string; className: string; season: string; fetchedAt: string | null; activeVariant: number }
export interface Character { id: string; name: string }
export interface Progress { completed: string[]; total: number; fingerprint: string; needsReview: boolean }
export interface MapNode {
  id: string; key?: string; name: string; x: number; y: number; allocated: boolean; description: string;
  rank?: number; maxRank?: number | null; kind?: string; selectable?: boolean; rarity?: number; gate?: boolean; socket?: boolean;
}
export interface Allocation extends Omit<MapNode, "x" | "y"> { x?: number; y?: number }
export interface Connection { from: string; to: string; corners: { x: number; y: number }[] }
export interface SkillStep { id: number; name: string; nodes: MapNode[]; connections: Connection[]; allocations: Allocation[] }
export interface Board {
  id: string; sourceId: string; name: string; order: number; width: number; rotation: number;
  position: { x: number; y: number } | null; nodes: MapNode[]; connections: Connection[]; allocations: Allocation[];
  glyph: { id: string | null; name: string; level: number | null };
}
export interface ParagonStep { id: number; name: string; boards: Board[] }
export interface Affix { name: string; rolls: number[]; greater: boolean; description: string }
export interface GearItem { slot: string; id: string; name: string; power: number | null; mythic: boolean; natural: Affix[]; implicit: Affix[]; tempered: Affix[]; aspects: Affix[]; sockets: string[] }
export interface Reference {
  id: string; name: string; className: string; season: string; variantId: number; variantName: string;
  variants: { id: number; name: string }[]; sourceUrl: string | null; updatedAt: string | null; fetchedAt: string | null;
  gameVersion: string | null; stale: boolean; error: string | null; diagnostics: string[]; gear: GearItem[];
  skills: { bar: { id: string; name: string }[]; mechanics: string[]; steps: SkillStep[]; activeStep: number };
  paragon: { steps: ParagonStep[]; activeStep: number };
}
