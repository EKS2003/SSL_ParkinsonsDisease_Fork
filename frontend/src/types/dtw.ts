// Canonical test ids we support
export const canonicalTests = [
  "stand-and-sit",
  "finger-tapping",
  "fist-open-close",
] as const;

export type CanonicalTest = (typeof canonicalTests)[number];

export const isCanonical = (t?: string | null): t is CanonicalTest =>
  !!t && (canonicalTests as readonly string[]).includes(t);

export const normalizeTestKey = (t?: string | null): CanonicalTest | null => {
  const s = (t ?? "").trim().toLowerCase();
  if (s === "finger-taping") return "finger-tapping"; // typo guard
  return isCanonical(s) ? (s as CanonicalTest) : null;
};

// ===== DTW REST payload types =====

export type DtwSessionMeta = {
  session_id: string;
  created_utc: string;
  model?: "hands" | "pose";
  live_len?: number;
  ref_len?: number;
  distance?: number;
  similarity?: number;
};

export type AxisAggResponse = {
  ok: boolean;
  axis: "x" | "y" | "z";
  reduce: "mean" | "median" | "pca1";
  landmarks: "all" | number[];
  live: { x: number[]; y: number[] };
  ref: { x: number[]; y: number[] };
  path: { i: number[]; j: number[] };
  warped: { k: number[]; live: number[]; ref: number[] };
};

export type DtwSeriesCurve = {
  local_cost_path: { x: number[]; y: number[] };
  cumulative_progress: { x: number[]; y: number[] };
  alignment_map: { x: number[]; y: number[] };
};

export type DtwSeriesMetrics = {
  ok: boolean;

  // New distance / similarity fields from backend
  distance_pos?: number;
  distance_amp?: number;
  distance_spd?: number;

  avg_step_pos?: number;

  similarity_overall?: number;
  similarity_pos?: number;
  similarity_amp?: number;
  similarity_spd?: number;

  // Backwards-compat (if backend still returns these)
  distance?: number;
  avg_step_cost?: number;
  similarity?: number;

  // Series for plotting DTW curves
  series?: {
    position: DtwSeriesCurve;
    amplitude: DtwSeriesCurve;
    speed: DtwSeriesCurve;
  };
};

