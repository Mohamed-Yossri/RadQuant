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

// ── Helpers ───────────────────────────────────────────────────────────────────

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
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
