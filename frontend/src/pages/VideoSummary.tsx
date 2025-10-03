// frontend/src/pages/VideoSummary.tsx
import { useState, useEffect, useMemo, ReactNode } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Calendar, TrendingUp, FileText, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ComposedChart, Area, Label,
} from 'recharts';
import { Test } from '@/types/patient';

// ---------------- Types ----------------
type DtwSeries = {
  local_cost_path: { x: number[]; y: number[] };
  cumulative_progress: { x: number[]; y: number[] };
  alignment_map: { x: number[]; y: number[] };
};
type DtwSessionMeta = {
  session_id: string;
  created_utc: string;
  model?: string;
  live_len?: number;
  ref_len?: number;
  distance?: number;
  similarity?: number;
};
type DtwSeriesResponse = {
  ok: boolean;
  testName: string;
  sessionId: string;
  distance: number;
  avg_step_cost: number;
  similarity: number;
  series: DtwSeries;
};

// -------------- Mock (unchanged) --------------
const mockTestHistory: Test[] = [
  {
    id: 'stand-and-sit',
    patientId: '1',
    name: 'Stand and Sit Assessment',
    type: 'stand-and-sit',
    date: new Date('2024-01-20'),
    status: 'completed',
    results: { duration: 45, score: 78, keypoints: [], analysis: 'Moderate improvement in mobility' }
  },
  {
    id: 'palm-open',
    patientId: '1',
    name: 'Palm Open Evaluation',
    type: 'palm-open',
    date: new Date('2024-01-18'),
    status: 'completed',
    results: { duration: 30, score: 82, keypoints: [], analysis: 'Good hand dexterity maintained' }
  }
];

const mockStats = {
  averageScore: 77,
  improvement: '+8%',
  totalTests: 12,
  averageDuration: '42s',
  tremor: 'Mild',
  balance: 'Good',
  coordination: 'Moderate',
  mobility: 'Good'
};

// -------------- Helpers --------------
const canonicalTests = ['stand-and-sit','finger-tapping','fist-open-close'] as const;
type CanonicalTest = typeof canonicalTests[number];

const isCanonical = (t?: string | null): t is CanonicalTest =>
  !!t && (canonicalTests as readonly string[]).includes(t);

const normalizeTestKey = (t?: string | null): CanonicalTest | null => {
  const s = (t ?? '').trim().toLowerCase();
  if (s === 'finger-taping') return 'finger-tapping'; // typo guard
  return isCanonical(s) ? (s as CanonicalTest) : null;
};

async function fetchJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// ----- Formatting + Tooltips + Explainers -----
const fmt = {
  num: (v: number, d = 3) => (Number.isFinite(v) ? v.toFixed(d) : String(v)),
  pct: (v: number, d = 0) => `${(v * 100).toFixed(d)}%`,
};

const CostTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const cost = payload[0].value as number;
  return (
    <div className="rounded-md border bg-card p-2 text-xs">
      <div><b>Path step:</b> {label}</div>
      <div><b>Per-step cost:</b> {fmt.num(cost)}</div>
      <div className="text-muted-foreground mt-1">Lower = closer match at this moment</div>
    </div>
  );
};

const ProgressTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const progress = payload[0].value as number;
  return (
    <div className="rounded-md border bg-card p-2 text-xs">
      <div><b>Path step:</b> {label}</div>
      <div><b>Cumulative progress:</b> {fmt.pct(progress, 1)}</div>
      <div className="text-muted-foreground mt-1">Smooth rise = consistent matching</div>
    </div>
  );
};

const AlignTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const refIdx = payload[0].value as number;
  return (
    <div className="rounded-md border bg-card p-2 text-xs">
      <div><b>Live frame:</b> {label}</div>
      <div><b>Reference frame:</b> {refIdx}</div>
      <div className="text-muted-foreground mt-1">
        Near-diagonal line ≈ similar tempo; horizontal/vertical runs = tempo differences
      </div>
    </div>
  );
};

const Explainer = ({ title, children }: { title: string; children: ReactNode }) => (
  <details className="text-xs bg-muted/50 rounded-md p-2">
    <summary className="cursor-pointer select-none"><b>How to read • {title}</b></summary>
    <div className="pt-2 text-muted-foreground">{children}</div>
  </details>
);

// -------------- Component --------------
const VideoSummary = () => {
  const { id, testId } = useParams<{ id: string; testId: string }>();

  // tests & videos
  const [selectedHistoryFilter, setSelectedHistoryFilter] = useState('all');
  const [testHistory] = useState<Test[]>(mockTestHistory);
  const [videoList, setVideoList] = useState<string[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);

  // DTW REST
  const [testKey, setTestKey] = useState<CanonicalTest | null>(null);
  const [sessions, setSessions] = useState<DtwSessionMeta[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [dtw, setDtw] = useState<DtwSeriesResponse | null>(null);
  const [maxPoints, setMaxPoints] = useState<number>(400);
  const [loadingSeries, setLoadingSeries] = useState<boolean>(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [routeResolved, setRouteResolved] = useState<boolean>(false);

  const currentTest = testHistory.find(t => t.type === testId) || testHistory[0];
  const filteredHistory = testHistory.filter(test =>
    selectedHistoryFilter === 'all' || test.type === selectedHistoryFilter
  );

  // -------- Route resolution: testId may be a test type OR a session id --------
  useEffect(() => {
    setErrMsg(null);
    setRouteResolved(false);

    const norm = normalizeTestKey(testId);
    if (norm) {
      // URL contained a canonical test type
      setTestKey(norm);
      setSessionId(null);        // no preselected session from URL
      setRouteResolved(true);
      return;
    }

    // Otherwise treat as a session id and ask backend which test it belongs to
    if (!testId) {
      setRouteResolved(true);
      return;
    }

    const ctrl = new AbortController();
    (async () => {
      try {
        const data = await fetchJSON<{ testName: string; sessionId: string }>(
          `/api/dtw/sessions/lookup/${encodeURIComponent(testId)}`, ctrl.signal
        );
        const key = normalizeTestKey(data.testName);
        if (!key) throw new Error(`Unknown DTW test '${data.testName}' for session '${data.sessionId}'`);
        setTestKey(key);
        setSessionId(data.sessionId); // preselect the URL's session
      } catch (e: any) {
        setErrMsg(e?.message || 'Failed to resolve session from URL');
        setTestKey(null);
        setSessionId(null);
      } finally {
        setRouteResolved(true);
      }
    })();

    return () => ctrl.abort();
  }, [testId]);

  // Videos (optional; your existing endpoint) — wait until routeResolved & testKey present
  useEffect(() => {
    if (!routeResolved || !id || !testKey) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        const data = await fetchJSON<{ success: boolean; videos: string[] }>(
          `/api/videos/${encodeURIComponent(id)}/${encodeURIComponent(testKey)}`, ctrl.signal
        );
        if (data.success && data.videos?.length > 0) {
          setVideoList(data.videos);
          setSelectedVideo(data.videos[0]);
        } else {
          setVideoList([]);
          setSelectedVideo(null);
        }
      } catch (err) {
        console.error("Failed to fetch video list", err);
        setVideoList([]);
        setSelectedVideo(null);
      }
    })();
    return () => ctrl.abort();
  }, [routeResolved, id, testKey]);

  // List DTW sessions for resolved testKey
  useEffect(() => {
    if (!routeResolved || !testKey) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        const data = await fetchJSON<DtwSessionMeta[]>(
          `/api/dtw/sessions/${encodeURIComponent(testKey)}`, ctrl.signal
        );
        setSessions(data);
        // Only choose a default if we DON'T already have one from URL lookup
        setSessionId(prev => prev ?? data[0]?.session_id ?? null);
      } catch (e: any) {
        setSessions([]);
        setSessionId(null);
        setErrMsg(e?.message || "No DTW sessions found for this test.");
      }
    })();
    return () => ctrl.abort();
  }, [routeResolved, testKey]);

  // Series for selected session
  useEffect(() => {
    if (!routeResolved || !testKey || !sessionId) {
      setDtw(null);
      return;
    }
    const ctrl = new AbortController();
    (async () => {
      try {
        setLoadingSeries(true);
        setErrMsg(null);
        const data = await fetchJSON<DtwSeriesResponse>(
          `/api/dtw/sessions/${encodeURIComponent(testKey)}/${encodeURIComponent(sessionId)}/series?max_points=${maxPoints}`,
          ctrl.signal
        );
        setDtw(data);
      } catch (e: any) {
        setDtw(null);
        setErrMsg(e?.message || "Failed to load DTW series.");
      } finally {
        setLoadingSeries(false);
      }
    })();
    return () => ctrl.abort();
  }, [routeResolved, testKey, sessionId, maxPoints]);

  // Transform series to Recharts data
  const localCostData = useMemo(() => {
    if (!dtw) return [];
    const { x, y } = dtw.series.local_cost_path;
    return x.map((xi, i) => ({ step: xi, cost: y[i] }));
  }, [dtw]);

  const cumulativeData = useMemo(() => {
    if (!dtw) return [];
    const { x, y } = dtw.series.cumulative_progress;
    return x.map((xi, i) => ({ step: xi, progress: y[i] }));
  }, [dtw]);

  const alignmentData = useMemo(() => {
    if (!dtw) return [];
    const { x, y } = dtw.series.alignment_map;
    return x.map((xi, i) => ({ liveIdx: xi, refIdx: y[i] }));
  }, [dtw]);

  const onExport = async () => {
    if (!testKey || !sessionId) return;
    try {
      const payload = await fetchJSON<{ npz: string; meta: string }>(
        `/api/dtw/sessions/${encodeURIComponent(testKey)}/${encodeURIComponent(sessionId)}/download`
      );
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dtw_${testKey}_${sessionId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card shadow-card">
        <div className="container mx-auto px-6 py-6 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <Link to={`/patient/${id}`}>
              <Button variant="outline" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Patient
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold text-foreground">Video Processing Summary</h1>
              <p className="text-muted-foreground mt-1">Analysis and Results</p>
            </div>
          </div>
          <div className="flex space-x-3">
            <Button variant="outline" disabled={!testKey || !sessionId} onClick={onExport}>
              <Download className="mr-2 h-4 w-4" />
              Export DTW
            </Button>
            <Link to={`/patient/${id}/test-selection`}>
              <Button className="bg-gradient-primary hover:bg-primary-hover">New Test Session</Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8 grid grid-cols-2 gap-8">
        {/* Video */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                Recorded Video
                <Badge variant="secondary" className="bg-success text-success-foreground">Processed</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedVideo ? (
                <video controls className="w-full rounded-lg aspect-video mb-4">
                  <source src={`/api/recordings/${selectedVideo}`} type="video/mp4" />
                  Your browser does not support the video tag.
                </video>
              ) : (
                <div className="bg-gray-900 text-white text-center py-8 rounded-lg">
                  No video available.
                </div>
              )}
              {videoList.length > 1 && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-foreground mb-1">Select Recording:</label>
                  <select
                    value={selectedVideo || ''}
                    onChange={(e) => setSelectedVideo(e.target.value)}
                    className="border p-2 rounded-md text-sm"
                  >
                    {videoList.map((video, idx) => (
                      <option key={idx} value={video}>{video}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>Duration: {currentTest?.results?.duration || 0}s</span>
                <span>Resolution: 1920x1080</span>
                <span>Keypoints: Detected</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Performance Chart (DTW) */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between w-full">
                <span className="flex items-center">
                  <TrendingUp className="mr-2 h-5 w-5" />
                  Performance Trends (DTW)
                </span>
                <div className="flex items-center gap-2">
                  {/* Test picker */}
                  <Select value={testKey ?? ''} onValueChange={(v) => setTestKey(v as CanonicalTest)}>
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="Select test" />
                    </SelectTrigger>
                    <SelectContent>
                      {canonicalTests.map((t) => (
                        <SelectItem key={t} value={t}>{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {/* Session picker */}
                  <Select value={sessionId ?? ''} onValueChange={(v) => setSessionId(v)}>
                    <SelectTrigger className="w-56">
                      <SelectValue placeholder="Select Session" />
                    </SelectTrigger>
                    <SelectContent>
                      {sessions.map((s) => (
                        <SelectItem key={s.session_id} value={s.session_id}>
                          {s.created_utc} • sim {s.similarity?.toFixed(2) ?? '-'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {/* Downsample points */}
                  <Select value={String(maxPoints)} onValueChange={(v) => setMaxPoints(Number(v))}>
                    <SelectTrigger className="w-28">
                      <SelectValue placeholder="Points" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="200">200 pts</SelectItem>
                      <SelectItem value="400">400 pts</SelectItem>
                      <SelectItem value="800">800 pts</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardTitle>
            </CardHeader>

            <CardContent>
              {errMsg && <div className="text-sm text-red-600 mb-3 break-words">{errMsg}</div>}
              {!dtw && !loadingSeries && <p className="text-sm text-muted-foreground">No DTW data yet.</p>}
              {loadingSeries && <p className="text-sm text-muted-foreground">Loading DTW series…</p>}
              {dtw && (
                <div className="space-y-6">
                  {/* KPIs with hints */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-xs text-muted-foreground">Similarity (exp-scaled)</div>
                      <div className="text-xl font-semibold">{dtw.similarity.toFixed(3)}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">Closer to 1.0 = better</div>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-xs text-muted-foreground">Distance (total DTW)</div>
                      <div className="text-xl font-semibold">{dtw.distance.toFixed(3)}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">Lower = better</div>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="text-xs text-muted-foreground">Avg Step Cost</div>
                      <div className="text-xl font-semibold">{dtw.avg_step_cost.toFixed(3)}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">Lower = better</div>
                    </div>
                  </div>

                  {/* Local cost path */}
                  <Explainer title="Local Cost">
                    Each point is the distance between the live frame and its aligned reference frame.
                    Lower and flatter = closer moment-by-moment match. Spikes indicate mismatches.
                  </Explainer>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={localCostData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="step">
                          <Label value="Warping path step" offset={-5} position="insideBottom" />
                        </XAxis>
                        <YAxis>
                          <Label angle={-90} value="Per-step cost (↓ better)" position="insideLeft" offset={10} />
                        </YAxis>
                        <Tooltip content={<CostTooltip />} />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="cost"
                          name="Per-step cost"
                          fillOpacity={0.2}
                          strokeOpacity={0.9}
                        />
                        <Line type="monotone" dataKey="cost" name="Per-step cost" dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Cumulative progress */}
                  <Explainer title="Cumulative Progress">
                    Normalized cumulative cost (0→1). Smooth, steady growth suggests stable matching;
                    abrupt jumps/plateaus flag timing or pose inconsistencies.
                  </Explainer>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={cumulativeData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="step">
                          <Label value="Warping path step" offset={-5} position="insideBottom" />
                        </XAxis>
                        <YAxis domain={[0, 1]} tickFormatter={(v) => fmt.pct(v)}>
                          <Label angle={-90} value="Cumulative progress" position="insideLeft" offset={10} />
                        </YAxis>
                        <Tooltip content={<ProgressTooltip />} />
                        <Legend />
                        <Line type="monotone" dataKey="progress" name="Normalized cumulative cost" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Alignment map */}
                  <Explainer title="Alignment Map">
                    Shows which reference frame each live frame aligned to. A near-diagonal line ≈ similar tempo.
                    Long horizontal/vertical stretches indicate the live motion ran faster/slower than the template.
                  </Explainer>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={alignmentData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="liveIdx">
                          <Label value="Live frame index" offset={-5} position="insideBottom" />
                        </XAxis>
                        <YAxis>
                          <Label angle={-90} value="Matched reference index" position="insideLeft" offset={10} />
                        </YAxis>
                        <Tooltip content={<AlignTooltip />} />
                        <Legend />
                        <Line type="linear" dataKey="refIdx" name="Live → Reference index" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Test History */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex justify-between">
                <span className="flex items-center">
                  <Calendar className="mr-2 h-5 w-5" />
                  Test History
                </span>
                <Select value={selectedHistoryFilter} onValueChange={setSelectedHistoryFilter}>
                  <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Tests</SelectItem>
                    <SelectItem value="stand-and-sit">Stand & Sit</SelectItem>
                    <SelectItem value="palm-open">Palm Open</SelectItem>
                  </SelectContent>
                </Select>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {filteredHistory.map((test) => (
                <div key={test.id} className="border p-3 rounded-lg mb-2">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="font-medium text-sm">{test.name}</p>
                      <p className="text-xs text-muted-foreground">{test.date.toDateString()}</p>
                    </div>
                    <Badge variant="secondary" className="bg-success text-success-foreground">
                      Score: {test.results?.score}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{test.results?.analysis}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Statistics Table */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <BarChart3 className="mr-2 h-5 w-5" />
                Performance Statistics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    <TableHead>Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>Overall Score</TableCell>
                    <TableCell>{currentTest?.results?.score}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Duration</TableCell>
                    <TableCell>{mockStats.averageDuration}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Tremor</TableCell>
                    <TableCell>{mockStats.tremor}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <div className="mt-4 p-3 bg-muted rounded-lg">
                <FileText className="inline mr-2 text-primary" />
                <span className="text-sm">{currentTest?.results?.analysis}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default VideoSummary;
