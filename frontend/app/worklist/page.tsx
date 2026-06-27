'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { worklist as wlApi, CaseOut, WorklistOut, urgencyColor, urgencyLabel, tierColor } from '@/lib/api';
import { UploadCloud, RefreshCw, Trash2, ChevronRight, Activity, AlertCircle } from 'lucide-react';

export default function WorklistPage() {
  const [data, setData] = useState<WorklistOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'pending' | 'in_review' | 'finalized'>('all');
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const d = await wlApi.list();
      setData(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const seedDemo = async () => {
    setSeeding(true);
    try { setData(await wlApi.seedDemo(8)); } finally { setSeeding(false); }
  };

  const clearAll = async () => {
    if (!confirm('Clear all cases?')) return;
    await wlApi.clear();
    setData(null);
    load();
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    for (const f of Array.from(files)) {
      try { await wlApi.upload(f); } catch (e) { console.error(e); }
    }
    await load();
    setUploading(false);
  };

  const cases = (data?.cases ?? []).filter(c =>
    filter === 'all' ? true : c.status === filter
  );

  return (
    <div className="p-8 max-w-7xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 tracking-tight">Active Worklist</h1>
          <p className="text-sm text-slate-500 mt-1 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4 text-urgent" />
            Urgency weights are literature-anchored defaults — not for clinical use.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={seedDemo}
            disabled={seeding}
            className="flex items-center gap-2 px-4 py-2.5 bg-surface-2 border border-border text-slate-300
                       rounded-xl text-sm font-semibold hover:bg-surface-3 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${seeding ? 'animate-spin' : ''}`} />
            {seeding ? 'Generating…' : 'Seed Cases'}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-5 py-2.5 bg-accent-sky text-surface-1 border border-accent-sky
                       rounded-xl text-sm font-bold hover:bg-accent-teal hover:border-accent-teal shadow-lg shadow-accent-sky/20 transition-all disabled:opacity-50"
          >
            <UploadCloud className={`w-4 h-4 ${uploading ? 'animate-bounce' : ''}`} />
            {uploading ? 'Uploading…' : 'Upload Study'}
          </button>
          <button
            onClick={clearAll}
            className="flex items-center gap-2 px-4 py-2.5 bg-critical/10 border border-critical/30 text-critical
                       rounded-xl text-sm font-semibold hover:bg-critical/20 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
          <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.dcm,.dicom"
            multiple className="hidden" onChange={e => handleFiles(e.target.files)} />
        </div>
      </div>

      {/* Stats Board */}
      {data && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Studies', value: data.total, color: 'text-slate-200' },
            { label: 'Pending Review', value: data.pending, color: 'text-urgent' },
            { label: 'Highest Acuity', value: (data.cases[0]?.urgency_score ?? 0).toFixed(2), color: 'text-critical' },
            { label: 'System Load', value: 'Nominal', color: 'text-chronic' },
          ].map(s => (
            <div key={s.label} className="glass rounded-2xl p-5 border-t-2 border-t-surface-4">
              <div className={`text-3xl font-bold tracking-tight ${s.color}`}>{s.value}</div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {(['all', 'pending', 'in_review', 'finalized'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              filter === f
                ? 'bg-accent-sky text-surface-1 shadow-md shadow-accent-sky/20'
                : 'bg-surface-2 text-slate-400 hover:text-slate-200 hover:bg-surface-3 border border-border'
            }`}>
            {f === 'all' ? 'All Studies' : f === 'in_review' ? 'In Review' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        className={`mb-6 border-2 border-dashed rounded-2xl p-6 text-center text-sm transition-all
          ${dragging ? 'border-accent-sky bg-accent-sky/10 text-accent-sky scale-[1.01]' : 'border-border text-slate-500 bg-surface-1/50'}`}
      >
        <UploadCloud className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <span className="font-medium">Drag & drop CXR studies here</span> (PNG / JPG / DICOM)
      </div>

      {/* Cases Grid */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 rounded-2xl shimmer" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div className="text-center py-24 glass rounded-3xl border-dashed">
          <Activity className="w-16 h-16 mx-auto mb-4 text-surface-4" />
          <div className="text-xl font-bold text-slate-300">Worklist Empty</div>
          <div className="text-sm text-slate-500 mt-2">No pending studies. You can rest.</div>
        </div>
      ) : (
        <div className="space-y-3">
          {cases.map(c => <CaseCard key={c.case_id} case_={c} onRefresh={load} />)}
        </div>
      )}
    </div>
  );
}

function CaseCard({ case_: c, onRefresh }: { case_: CaseOut; onRefresh: () => void }) {
  const color = urgencyColor(c.urgency_score);
  const label = urgencyLabel(c.urgency_score);

  return (
    <div className="group bg-surface-2 border border-border rounded-2xl p-4 hover:bg-surface-3
                    transition-all duration-200 animate-slide-up shadow-sm hover:shadow-md hover:border-surface-4">
      <div className="flex items-center gap-5">
        {/* Urgency indicator */}
        <div className="shrink-0 flex flex-col items-center justify-center w-12 h-14 rounded-xl bg-surface-1 border border-border">
          <div className="text-[10px] font-bold uppercase text-slate-500 tracking-widest mb-1">Acuity</div>
          <div className="w-6 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}80` }} />
        </div>

        {/* Case info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-base font-bold text-slate-100 truncate tracking-tight">{c.case_id}</span>
            <span className="text-xs px-2.5 py-1 rounded-md font-bold uppercase tracking-wider"
              style={{ background: `${color}15`, color, border: `1px solid ${color}30` }}>
              {label} {c.urgency_score.toFixed(2)}
            </span>
            <StatusChip status={c.status} />
          </div>
          <div className="flex flex-wrap gap-2">
            {c.top_findings.map(f => (
              <span key={f.label}
                className="text-[11px] px-2.5 py-1 rounded-md border font-semibold"
                style={{ borderColor: `${tierColor(f.tier)}40`, color: tierColor(f.tier),
                         background: `${tierColor(f.tier)}10` }}>
                {f.label} {(f.probability * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="shrink-0 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={async () => { await wlApi.deleteCase(c.case_id); onRefresh(); }}
            className="p-2.5 text-slate-500 rounded-xl hover:text-critical hover:bg-critical/10 transition-colors"
            title="Remove Case">
            <Trash2 className="w-5 h-5" />
          </button>
          <a href={`/case/${c.case_id}`}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-accent-sky text-surface-1 text-sm font-bold
                       rounded-xl hover:bg-accent-teal hover:shadow-lg hover:shadow-accent-teal/20 transition-all">
            Open Study
            <ChevronRight className="w-4 h-4" />
          </a>
        </div>
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: 'PENDING', cls: 'bg-urgent/10 text-urgent border-urgent/20' },
    in_review: { label: 'IN REVIEW', cls: 'bg-accent-sky/10 text-accent-sky border-accent-sky/20' },
    finalized: { label: 'FINALIZED', cls: 'bg-chronic/10 text-chronic border-chronic/20' },
  };
  const s = map[status] ?? { label: status.toUpperCase(), cls: 'bg-surface-3 text-slate-400 border-border' };
  return (
    <span className={`text-[10px] px-2 py-1 rounded-md border font-bold tracking-wider ${s.cls}`}>{s.label}</span>
  );
}
