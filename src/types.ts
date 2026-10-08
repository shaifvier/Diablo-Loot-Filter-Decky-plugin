export type Reply<T> = { ok: true; data: T } | { ok: false; error: string };
export interface FilterSummary {
  id: string;
  title: string;
  className: string;
  buildName: string;
  stage: string;
  strictness: string;
  season: string;
  updatedAt: string | null;
  sourceName: string;
  sourceUrl: string;
  creator: string;
  verification: string;
  origin: "Published" | "Generated";
}
export interface RulePreview {
  name: string;
  action: string;
  enabled: boolean;
  color: string | null;
  conditions: string[];
}
export interface FilterDetail extends FilterSummary {
  code: string;
  preview: { name: string; rules: RulePreview[]; ruleCount: number };
  diagnostics: string[];
}
export interface Catalogue {
  filters: FilterSummary[];
  fetchedAt: string | null;
  stale: boolean;
  error: string | null;
  rejected: number;
}
export interface Build {
  id: string;
  name: string;
  className: string;
  season: string;
  updatedAt: string | null;
  fetchedAt: string;
  variants: { id: number; name: string }[];
  activeVariant: number;
  publishedFilters: FilterSummary[];
  rejectedFilters: number;
  stale: boolean;
  error: string | null;
}
export interface CopyResult {
  copied: boolean;
  gameDetected: boolean;
  gameCopied: boolean;
  displays: string[];
  error: string | null;
}
