// src/api/dtw.ts
import { getJSON } from "../base";
import type {
  AxisAggResponse,
  CanonicalTest,
  DtwSessionMeta,
  DtwSeriesMetrics,
} from "@/types/dtw";

// Resolve route param (testId or sessionId) -> { testName, sessionId }
export function resolveDtwRoute(
  idOrSession: string,
  signal?: AbortSignal
): Promise<{ testName: string; sessionId: string }> {
  return getJSON<{ testName: string; sessionId: string }>(
    `/dtw/sessions/lookup/${encodeURIComponent(idOrSession)}`,
    signal
  );
}

// List DTW sessions for a given test key
export function listDtwSessions(
  testKey: CanonicalTest,
  signal?: AbortSignal
): Promise<DtwSessionMeta[]> {
  return getJSON<DtwSessionMeta[]>(
    `/dtw/sessions/${encodeURIComponent(testKey)}`,
    signal
  );
}

// Fetch DTW KPI + series metrics
export function getDtwSeriesMetrics(
  testKey: CanonicalTest,
  sessionId: string,
  maxPoints = 200,
  signal?: AbortSignal
): Promise<DtwSeriesMetrics> {
  return getJSON<DtwSeriesMetrics>(
    `/dtw/sessions/${encodeURIComponent(
      testKey
    )}/${encodeURIComponent(sessionId)}/series?max_points=${maxPoints}`,
    signal
  );
}

// Axis-aggregated DTW series (for the big chart)
export function getAxisAggregate(
  params: {
    testKey: CanonicalTest;
    sessionId: string;
    axis?: "x" | "y" | "z";
    reduce?: "mean" | "median" | "pca1";
    landmarks?: string;
    maxPoints?: number;
  },
  signal?: AbortSignal
): Promise<AxisAggResponse> {
  const {
    testKey,
    sessionId,
    axis = "x",
    reduce = "mean",
    landmarks = "all",
    maxPoints = 600,
  } = params;

  const query =
    `?axis=${axis}` +
    `&reduce=${reduce}` +
    `&landmarks=${encodeURIComponent(landmarks)}` +
    `&max_points=${maxPoints}`;

  return getJSON<AxisAggResponse>(
    `/dtw/sessions/${encodeURIComponent(
      testKey
    )}/${encodeURIComponent(sessionId)}/axis_agg${query}`,
    signal
  );
}

// List recordings for a patient + test
export function listTestVideos(
  patientId: string,
  testKey: CanonicalTest,
  signal?: AbortSignal
): Promise<{ success: boolean; videos: string[] }> {
  return getJSON<{ success: boolean; videos: string[] }>(
    `/videos/${encodeURIComponent(patientId)}/${encodeURIComponent(testKey)}`,
    signal
  );
}

// Download DTW session payload ({npz, meta})
export function downloadDtwPayload(
  testKey: CanonicalTest,
  sessionId: string,
  signal?: AbortSignal
): Promise<{ npz: string; meta: string }> {
  return getJSON<{ npz: string; meta: string }>(
    `/dtw/sessions/${encodeURIComponent(
      testKey
    )}/${encodeURIComponent(sessionId)}/download`,
    signal
  );
}
