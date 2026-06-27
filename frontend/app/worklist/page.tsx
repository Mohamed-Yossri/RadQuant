'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  worklist as wlApi,
  CaseOut,
  WorklistOut,
  urgencyColor,
  urgencyLabel,
  tierColor,
  caseImageUrl,
} from '@/lib/api';
import {
  UploadCloud,
  RefreshCw,
  Trash2,
  ChevronRight,
  Activity,
  Layers,
  Clock,
  Gauge,
  Cpu,
} from 'lucide-react';

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
      setData(await wlApi.list());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const seedDemo = async () => {
    setSeeding(true);
    try {
      setData(await wlApi.seedDemo(8));
    } finally {
      setSeeding(false);
    }
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
      try {
        await wlApi.upload(f);
      } catch (e) {
        console.error(e);
      }
    }
    await load();
    setUploading(false);
  };

  const cases = (data?.cases ?? []).filter((c) => (filter === 'all' ? true : c.status === filter));

  return (
    <div className="p-8 max-w-7xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">Active Worklist</h1>
          <p className="text-sm text-slate-500 mt-1.5">
            Chest radiograph triage queue · ranked by urgency · classified on-device
          </p>
        </div>
        <div className="flex gap-2.5">
          <button
            onClick={seedDemo}
            disabled={seeding}
            className="flex items-center gap-2 px-4 py-2.5 bg-surface-2 border border-border text-slate-300
                       rounded-xl text-sm font-semibold hover:bg-surface-3 hover:border-surface-4 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${seeding ? 'animate-spin' : ''}`} />
            {seeding ? 'Generating…' : 'Seed Cases'}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-surface-1
                       bg-gradient-to-r from-accent-teal to-accent-sky shadow-glow hover:brightness-110 transition-all disabled:opacity-50"
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
          <input
            ref={fileRef}
            type="file"
            accept=".png,.jpg,.jpeg,.dcm,.dicom"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      </div>

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard icon={Layers} label="Total Studies" value={String(data.total)} tone="text-slate-100" accent="#38BDF8" />
          <StatCard icon={Clock} label="Pending Review" value={String(data.pending)} tone="text-urgent" accent="#F59E0B" />
          <StatCard
            icon={Gauge}
            label="Highest Acuity"
            value={(data.cases[0]?.urgency_score ?? 0).toFixed(2)}
            tone="text-critical"
            accent="#F4536B"
          />
          <StatCard icon={Cpu} label="Engine" value="Local" sub="MedGemma 4B" tone="text-chronic" accent="#34D399" />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {(['all', 'pending', 'in_review', 'finalized'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              filter === f
                ? 'bg-accent-teal/15 text-accent-teal border border-accent-teal/30'
                : 'bg-surface-2 text-slate-400 hover:text-slate-200 hover:bg-surface-3 border border-border'
            }`}
          >
            {f === 'all' ? 'All Studies' : f === 'in_review' ? 'In Review' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`mb-6 border-2 border-dashed rounded-2xl p-6 text-center text-sm transition-all ${
          dragging
            ? 'border-accent-teal bg-accent-teal/10 text-accent-teal scale-[1.01]'
            : 'border-border text-slate-500 bg-surface-1/40 hover:border-surface-4'
        }`}
      >
        <UploadCloud className="w-7 h-7 mx-auto mb-2 opacity-50" />
        <span className="font-medium">Drag &amp; drop a chest X-ray</span> (PNG / JPG / DICOM)
      </div>

      {/* Cases */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-28 rounded-2xl shimmer" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div className="text-center py-24 card border-dashed">
          <Activity className="w-14 h-14 mx-auto mb-4 text-surface-4" />
          <div className="text-xl font-bold text-slate-300">Worklist clear</div>
          <div className="text-sm text-slate-500 mt-2">
            No studies in this view. Seed demo cases or upload a chest X-ray.
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {cases.map((c) => (
            <CaseCard key={c.case_id} case_={c} onRefresh={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  tone: string;
  accent: string;
}) {
  return (
    <div className="card card-hover p-5 relative overflow-hidden">
      <div className="absolute left-0 top-0 h-full w-1" style={{ background: accent, opacity: 0.7 }} />
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</div>
        <Icon className="w-4 h-4" style={{ color: accent }} />
      </div>
      <div className={`text-3xl font-extrabold tracking-tight mt-2 tabular ${tone}`}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5 font-mono">{sub}</div>}
    </div>
  );
}

function CaseCard({ case_: c, onRefresh }: { case_: CaseOut; onRefresh: () => void }) {
  const color = urgencyColor(c.urgency_score);
  const label = urgencyLabel(c.urgency_score);

  return (
    <a
      href={`/case/${c.case_id}`}
      className="group block card card-hover p-4 animate-slide-up"
    >
      <div className="flex items-center gap-4">
        {/* Thumbnail in a film frame, acuity ribbon */}
        <div className="relative shrink-0 w-20 h-20 rounded-xl overflow-hidden film border border-border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={caseImageUrl(c.case_id)}
            alt={c.case_id}
            loading="lazy"
            className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.visibility = 'hidden';
            }}
          />
          <div className="absolute left-0 bottom-0 right-0 h-1.5" style={{ background: color }} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 mb-2 flex-wrap">
            <span className="text-base font-bold text-slate-100 tracking-tight">{c.case_id}</span>
            <span
              className="text-[11px] px-2.5 py-1 rounded-md font-bold uppercase tracking-wider"
              style={{ background: `${color}1A`, color, border: `1px solid ${color}40` }}
            >
              {label} {c.urgency_score.toFixed(2)}
            </span>
            <StatusChip status={c.status} />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {c.top_findings.map((f) => (
              <span
                key={f.label}
                className="text-[11px] px-2 py-0.5 rounded-md border font-semibold"
                style={{
                  borderColor: `${tierColor(f.tier)}40`,
                  color: tierColor(f.tier),
                  background: `${tierColor(f.tier)}12`,
                }}
              >
                {f.label} {(f.probability * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="shrink-0 flex items-center gap-1.5">
          <button
            onClick={async (e) => {
              e.preventDefault();
              await wlApi.deleteCase(c.case_id);
              onRefresh();
            }}
            className="p-2.5 text-slate-500 rounded-xl hover:text-critical hover:bg-critical/10 transition-colors opacity-0 group-hover:opacity-100"
            title="Remove case"
          >
            <Trash2 className="w-5 h-5" />
          </button>
          <span className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-bold rounded-xl text-slate-300 bg-surface-3 group-hover:bg-gradient-to-r group-hover:from-accent-teal group-hover:to-accent-sky group-hover:text-surface-1 transition-all">
            Open
            <ChevronRight className="w-4 h-4" />
          </span>
        </div>
      </div>
    </a>
  );
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: 'PENDING', cls: 'bg-urgent/10 text-urgent border-urgent/20' },
    in_review: { label: 'IN REVIEW', cls: 'bg-accent-sky/10 text-accent-sky border-accent-sky/20' },
    finalized: { label: 'FINALIZED', cls: 'bg-chronic/10 text-chronic border-chronic/20' },
  };
  const s = map[status] ?? { label: status.toUpperCase(), cls: 'bg-surface-3 text-slate-400 border-border' };
  return <span className={`text-[10px] px-2 py-1 rounded-md border font-bold tracking-wider ${s.cls}`}>{s.label}</span>;
}
