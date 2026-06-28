/**
 * Typed API client — all calls go through Next.js rewrites → FastAPI at :8000
 */

const BASE = '/api';

// ── Types ────────────────────────────────────────────────────────────────────

export interface FindingItem {
  label: string;
  probability: number;
  tier: string;
}

export interface CaseOut {
  case_id: string;
  image_path: string;
  urgency_score: number;
  status: 'pending' | 'in_review' | 'finalized';
  findings: Record<string, number>;
  top_findings: FindingItem[];
}

export interface WorklistOut {
  cases: CaseOut[];
  total: number;
  pending: number;
}

export interface OmissionItem {
  finding: string;
  confidence: number;
  suggestion: string;
  method: string;
}

export interface QCOut {
  omissions: OmissionItem[];
}

export interface GlossaryItem {
  term: string;
  definition: string;
}

export interface ExplainOut {
  plain: string;
  glossary: GlossaryItem[];
  highlighted_html: string;
}

export interface LocalizationFinding {
  label: string;
  label_pretty: string;
  box: number[];
  confidence: number;
  zone: string;
}

export interface LocalizeOut {
  overlay_url: string;
  findings: LocalizationFinding[];
}

export interface SegmentOut {
  overlay_url: string;
  structures: string[];
  cardiothoracic_ratio: number | null;
  ctr_flag: string;
}

export interface GradCAMOut {
  overlay_url: string;
  top_finding: string;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: 'case' | 'hub';
  size: number;
  tier: string | null;
  urgency_score: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export interface InsightsGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  alerts: string[];
  hub_sizes: Record<string, number>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  // Never force a JSON content-type on FormData uploads — the browser must set
  // the multipart boundary itself, or the backend can't parse the file.
  const isForm = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  const headers = isForm
    ? { ...init?.headers }
    : { 'Content-Type': 'application/json', ...init?.headers };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Worklist ─────────────────────────────────────────────────────────────────

export const worklist = {
  list: () => api<WorklistOut>('/worklist'),
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api<CaseOut>('/worklist/upload', {
      method: 'POST',
      headers: {},
      body: form,
    });
  },
  seedDemo: (n = 8) =>
    api<WorklistOut>(`/worklist/seed-demo?n=${n}`, { method: 'POST' }),
  clear: () => api<{ cleared: boolean }>('/worklist/clear', { method: 'DELETE' }),
  getCase: (id: string) => api<CaseOut>(`/worklist/${id}`),
  updateStatus: (id: string, status: string) =>
    api<CaseOut>(`/worklist/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  deleteCase: (id: string) =>
    api<{ deleted: string }>(`/worklist/${id}`, { method: 'DELETE' }),
};

// ── Cases ────────────────────────────────────────────────────────────────────

export const cases = {
  /** Returns an EventSource; caller handles 'progress' and 'draft' events. */
  streamDraft: (caseId: string) =>
    new EventSource(`${BASE}/cases/${caseId}/draft`),

  gradcam: (caseId: string) =>
    api<GradCAMOut>(`/cases/${caseId}/gradcam`, { method: 'POST' }),

  localize: (caseId: string) =>
    api<LocalizeOut>(`/cases/${caseId}/localize`, { method: 'POST' }),

  segment: (caseId: string) =>
    api<SegmentOut>(`/cases/${caseId}/segment`, { method: 'POST' }),

  qc: (caseId: string, report: string) =>
    api<QCOut>(`/cases/${caseId}/qc`, {
      method: 'POST',
      body: JSON.stringify({ report }),
    }),

  finalize: (caseId: string, findings: string, impression: string) =>
    api<{ final_report: string; case_id: string }>(`/cases/${caseId}/finalize`, {
      method: 'POST',
      body: JSON.stringify({ findings, impression }),
    }),

  /** Returns an EventSource; caller handles 'thinking' and 'answer' events. */
  streamChat: (caseId: string, question: string) => {
    // POST-based SSE via fetch (EventSource doesn't support POST)
    return fetch(`${BASE}/cases/${caseId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
  },
};

// ── Explainer ─────────────────────────────────────────────────────────────────

export const explainer = {
  explain: (report: string) =>
    api<ExplainOut>('/explain', {
      method: 'POST',
      body: JSON.stringify({ report }),
    }),
};

// ── Insights (knowledge graph) ────────────────────────────────────────────────

export const insights = {
  graph: (findingThreshold = 0.35, minHubSize = 2) =>
    api<InsightsGraphData>(
      `/insights/graph?finding_threshold=${findingThreshold}&min_hub_size=${minHubSize}`,
    ),
};

// ── General Medical (any-modality, MedGemma-only) ─────────────────────────────

export interface GeneralAnalyzeOut {
  image_id: string;
  image_url: string;
  modality: string;
  region: string;
  is_cxr: boolean;
  description: string;
  pixel_spacing_mm: number | null;
}

export interface GeneralSegmentOut {
  overlay_url: string;
  area_px: number;
  area_pct: number;
  width_px: number;
  height_px: number;
  longest_diameter_px: number;
  short_axis_px: number;
  image_w: number;
  image_h: number;
}

export const general = {
  analyze: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api<GeneralAnalyzeOut>('/general/analyze', { method: 'POST', body: form });
  },
  vqa: (imageId: string, question: string) =>
    api<{ answer: string }>('/general/vqa', {
      method: 'POST',
      body: JSON.stringify({ image_id: imageId, question }),
    }),
  segment: (imageId: string, box: number[]) =>
    api<GeneralSegmentOut>('/general/segment', {
      method: 'POST',
      body: JSON.stringify({ image_id: imageId, box }),
    }),
};

// ── CT Reader (TotalSegmentator) ──────────────────────────────────────────────

export interface CtVolume {
  name: string;
  ml: number;
  flag: 'low' | 'normal' | 'high' | null;
  ref_low: number | null;
  ref_high: number | null;
}
export interface CtSlice { orig: string; overlay: string; }
export interface CtAnalyzeOut {
  study_id: string;
  n_slices: number;
  slices: CtSlice[];
  volumes: CtVolume[];
  report: string;
}

export const ct = {
  analyze: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api<CtAnalyzeOut>('/ct/analyze', { method: 'POST', body: form });
  },
  sample: () => api<CtAnalyzeOut>('/ct/sample', { method: 'POST' }),
};

// ── Urgency helpers ───────────────────────────────────────────────────────────

export function urgencyColor(score: number): string {
  if (score >= 0.7) return '#EF4444'; // critical
  if (score >= 0.4) return '#F97316'; // urgent
  if (score >= 0.2) return '#EAB308'; // important
  return '#22C55E';                   // chronic
}

export function urgencyLabel(score: number): string {
  if (score >= 0.7) return 'Critical';
  if (score >= 0.4) return 'Urgent';
  if (score >= 0.2) return 'Important';
  return 'Routine';
}

export function tierColor(tier: string): string {
  const map: Record<string, string> = {
    Critical: '#EF4444',
    Urgent: '#F97316',
    Important: '#EAB308',
    Chronic: '#22C55E',
    Unknown: '#6B7280',
  };
  return map[tier] ?? '#6B7280';
}

/** Original X-ray for a case — resolved server-side by case_id (basenames in
 *  the ChestAgentBench figure set collide, so we never resolve by filename). */
export function caseImageUrl(caseId: string): string {
  return `/api/cases/${caseId}/image`;
}

export function imageUrl(serverPath: string): string {
  if (serverPath.startsWith('/api/')) return serverPath;
  const name = serverPath.split(/[\\/]/).pop() ?? serverPath;
  
  if (serverPath.includes('data/images') || serverPath.includes('data\\images')) {
    return `/api/images/data/${name}`;
  }
  if (serverPath.includes('uploads')) {
    return `/api/images/uploads/${name}`;
  }
  return `/api/images/temp/${name}`;
}
