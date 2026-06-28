'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { ct as ctApi, CtAnalyzeOut, CtVolume } from '@/lib/api';
import {
  UploadCloud, Layers, Sparkles, AlertTriangle, ChevronLeft, ChevronRight, Boxes,
  ArrowUp, ArrowDown,
} from 'lucide-react';

// A few large organs we colour-flag if present (purely cosmetic grouping).
function volColor(name: string): string {
  if (/kidney|liver|spleen|lung|heart|bladder|aorta/.test(name)) return '#2DD4BF';
  if (/vertebrae|rib|sacrum|femur|hip|humerus|clavicula|scapula/.test(name)) return '#94A3B8';
  if (/gluteus|iliopsoas|muscle/.test(name)) return '#F59E0B';
  return '#64748B';
}

function VolRow({ v }: { v: CtVolume }) {
  const flagged = v.flag === 'high' || v.flag === 'low';
  return (
    <div
      className={`flex items-center gap-2.5 text-sm py-1.5 px-2 rounded-md border-b border-border/40 ${
        flagged ? 'bg-urgent/10' : ''
      }`}
      title={v.ref_low != null ? `reference ${v.ref_low}–${v.ref_high} ml` : undefined}
    >
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: volColor(v.name) }} />
      <span className={`truncate ${flagged ? 'text-slate-100 font-medium' : 'text-slate-300'}`}>
        {v.name.replace(/_/g, ' ')}
      </span>
      {v.flag === 'high' && (
        <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded bg-critical/15 text-critical border border-critical/30">
          <ArrowUp className="w-2.5 h-2.5" /> high
        </span>
      )}
      {v.flag === 'low' && (
        <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent-sky/15 text-accent-sky border border-accent-sky/30">
          <ArrowDown className="w-2.5 h-2.5" /> low
        </span>
      )}
      <span className="ml-auto text-slate-100 font-mono tabular font-semibold">{v.ml.toFixed(1)} ml</span>
    </div>
  );
}

export default function CtPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<CtAnalyzeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [overlay, setOverlay] = useState(true);
  const [dragging, setDragging] = useState(false);

  const analyze = async (f: File) => {
    setFile(f); setResult(null); setError(null); setAnalyzing(true);
    try {
      const r = await ctApi.analyze(f);
      setResult(r);
      setIdx(Math.floor(r.n_slices / 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const runSample = async () => {
    setFile(null); setResult(null); setError(null); setAnalyzing(true);
    try {
      const r = await ctApi.sample();
      setResult(r);
      setIdx(Math.floor(r.n_slices / 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const step = useCallback((d: number) => {
    if (!result) return;
    setIdx((i) => Math.max(0, Math.min(result.n_slices - 1, i + d)));
  }, [result]);

  // keyboard arrows scroll the stack
  useEffect(() => {
    if (!result) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); step(-1); }
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); step(1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [result, step]);

  const cur = result?.slices[idx];
  const src = cur ? (overlay ? cur.overlay : cur.orig) : '';
  const abnormal = result?.volumes.filter((v) => v.flag === 'high' || v.flag === 'low') ?? [];

  return (
    <div className="p-8 max-w-6xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-11 h-11 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center">
          <Boxes className="w-5 h-5 text-accent-sky" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">CT Reader</h1>
          <p className="text-sm text-slate-500">Upload a CT volume → automatic organ segmentation (TotalSegmentator) + volumes + report.</p>
        </div>
      </div>

      <div className="flex items-start gap-2.5 bg-accent-sky/5 border border-accent-sky/20 rounded-xl px-4 py-3 mb-6 text-xs text-slate-400 leading-relaxed">
        <AlertTriangle className="w-4 h-4 text-accent-sky shrink-0 mt-0.5" />
        <span><strong className="text-slate-300">Cross-sectional (3D) pipeline.</strong> TotalSegmentator segments 100+ structures and measures their volumes; MedGemma drafts the read. Research demo, not diagnostic.</span>
      </div>

      {!result && !analyzing && (
        <>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) analyze(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
            className={`mb-3 border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${dragging ? 'border-accent-sky bg-accent-sky/10 scale-[1.01]' : 'border-border hover:border-surface-4 bg-surface-1/40'}`}
          >
            <UploadCloud className="w-9 h-9 mx-auto mb-2 text-slate-500" />
            <div className="text-sm text-slate-300 font-medium">{file ? `Selected: ${file.name}` : 'Drop a CT scan, or click to choose'}</div>
            <div className="text-xs text-slate-500 mt-1">NIfTI <span className="font-mono">.nii.gz</span> — or a DICOM series as a <span className="font-mono">.zip</span> of <span className="font-mono">.dcm</span> slices (e.g. an NLST lung-screening series). A single <span className="font-mono">.dcm</span> is just one slice — zip the whole series.</div>
            <input ref={fileRef} type="file" accept=".nii,.nii.gz,.gz,.zip,.dcm" className="hidden" onChange={(e) => e.target.files?.[0] && analyze(e.target.files[0])} />
          </div>
          <div className="flex items-center justify-center gap-3 mb-6 text-xs text-slate-500">
            <span>Don&apos;t have a scan handy?</span>
            <button
              onClick={runSample}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-teal/15 text-accent-teal border border-accent-teal/30 font-bold hover:bg-accent-teal/25 transition"
            >
              <Sparkles className="w-3.5 h-3.5" /> Try a sample CT
            </button>
          </div>
        </>
      )}

      {error && <div className="mb-6 p-4 rounded-xl bg-critical/10 border border-critical/30 text-critical text-sm">{error}</div>}

      {analyzing && (
        <div className="flex flex-col items-center gap-3 text-slate-400 text-sm py-16">
          <Layers className="w-8 h-8 animate-pulse text-accent-sky" />
          <div>Segmenting 100+ anatomical structures with TotalSegmentator…</div>
          <div className="text-xs text-slate-600">~30–60 s — running the 3D model + drafting the report</div>
        </div>
      )}

      {result && !analyzing && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 animate-slide-up">
          {/* Slice viewer */}
          <div className="lg:col-span-3 space-y-3">
            <div className="card p-2">
              <div className="flex items-center justify-between px-1 py-1.5">
                <button onClick={() => setOverlay((o) => !o)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${overlay ? 'bg-accent-teal/20 text-accent-teal border border-accent-teal/40' : 'bg-surface-2 text-slate-300 border border-border hover:bg-surface-3'}`}>
                  <Layers className="w-3.5 h-3.5" /> {overlay ? 'Segmentation on' : 'Segmentation off'}
                </button>
                <div className="text-xs text-slate-500 font-mono">slice {idx + 1} / {result.n_slices}</div>
              </div>
              <div
                className="film rounded-lg overflow-hidden flex items-center justify-center min-h-[360px] cursor-ns-resize"
                onWheel={(e) => { e.preventDefault(); step(e.deltaY > 0 ? 1 : -1); }}
                title="Scroll to move through slices"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt={`slice ${idx}`} draggable={false} className="max-w-full max-h-[460px] object-contain select-none" />
              </div>
              {/* slider */}
              <div className="flex items-center gap-3 px-2 py-2">
                <button onClick={() => setIdx((i) => Math.max(0, i - 1))} className="p-1.5 rounded-lg hover:bg-surface-3 text-slate-400"><ChevronLeft className="w-4 h-4" /></button>
                <input type="range" min={0} max={result.n_slices - 1} value={idx} onChange={(e) => setIdx(parseInt(e.target.value))} className="flex-1 accent-accent-sky cursor-pointer" />
                <button onClick={() => setIdx((i) => Math.min(result.n_slices - 1, i + 1))} className="p-1.5 rounded-lg hover:bg-surface-3 text-slate-400"><ChevronRight className="w-4 h-4" /></button>
              </div>
              <div className="px-2 pb-1 text-[11px] text-slate-500">Scroll / arrow keys to move through the stack · toggle the colored organ segmentation.</div>
            </div>

            {/* Report */}
            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2"><Sparkles className="w-4 h-4 text-accent-purple" /> MedGemma CT read</div>
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{result.report}</div>
            </div>
          </div>

          {/* Volume table */}
          <div className="lg:col-span-2">
            <div className="card p-5 sticky top-6">
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-widest">Organ volumes</div>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-accent-teal/10 text-accent-teal border border-accent-teal/20 font-bold">{result.volumes.length} structures</span>
              </div>
              {abnormal.length > 0 && (
                <div className="mb-3 p-2.5 rounded-lg bg-urgent/10 border border-urgent/25 text-[11px] text-urgent flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{abnormal.length} structure{abnormal.length > 1 ? 's' : ''} outside the approximate adult reference range — review highlighted rows.</span>
                </div>
              )}
              <div className="space-y-0.5 max-h-[540px] overflow-auto pr-1">
                {result.volumes.map((v) => (
                  <VolRow key={v.name} v={v} />
                ))}
              </div>
              <div className="mt-2 text-[10px] text-slate-600">Reference ranges are approximate adult values — not calibrated for body size/age/sex.</div>
              <button onClick={() => { setResult(null); setFile(null); }} className="mt-4 w-full text-xs text-slate-400 hover:text-slate-200 py-2 rounded-lg bg-surface-2 hover:bg-surface-3 border border-border">
                Analyze another CT
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
