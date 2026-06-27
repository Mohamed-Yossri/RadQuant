'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  general as generalApi,
  explainer as explApi,
  worklist as wlApi,
  GeneralAnalyzeOut,
  GeneralSegmentOut,
  ExplainOut,
} from '@/lib/api';
import {
  UploadCloud,
  Sparkles,
  Send,
  ArrowRight,
  Microscope,
  ScanLine,
  Brain,
  AlertTriangle,
  Stethoscope,
  Eye,
  Activity,
  Crop,
  X,
} from 'lucide-react';

const MODALITY_ICON: Record<string, React.ElementType> = {
  'Chest X-ray': Activity,
  'Other X-ray': ScanLine,
  CT: ScanLine,
  MRI: ScanLine,
  Ultrasound: Activity,
  'Dermatology photo': Stethoscope,
  'Fundus photo': Eye,
  Histopathology: Microscope,
  Other: Brain,
};

interface Box { x0: number; y0: number; x1: number; y1: number; }

export default function GeneralPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<GeneralAnalyzeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chat, setChat] = useState<{ q: string; a: string }[]>([]);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [plain, setPlain] = useState<ExplainOut | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [routing, setRouting] = useState(false);
  const [dragging, setDragging] = useState(false);

  // MedSAM segmentation
  const [segMode, setSegMode] = useState(false);
  const [drawBox, setDrawBox] = useState<Box | null>(null);
  const [seg, setSeg] = useState<GeneralSegmentOut | null>(null);
  const [viewSeg, setViewSeg] = useState(false);
  const [segLoading, setSegLoading] = useState(false);

  const resetSeg = () => { setSegMode(false); setDrawBox(null); setSeg(null); setViewSeg(false); };

  const analyze = async (f: File) => {
    setFile(f); setResult(null); setChat([]); setPlain(null); setError(null); resetSeg();
    setAnalyzing(true);
    try {
      setResult(await generalApi.analyze(f));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const ask = async () => {
    if (!question.trim() || !result || asking) return;
    const q = question.trim();
    setQuestion(''); setAsking(true);
    setChat((c) => [...c, { q, a: '…' }]);
    try {
      const { answer } = await generalApi.vqa(result.image_id, q);
      setChat((c) => c.map((m, i) => (i === c.length - 1 ? { q, a: answer } : m)));
    } catch (e) {
      setChat((c) => c.map((m, i) => (i === c.length - 1 ? { q, a: `Error: ${e}` } : m)));
    } finally {
      setAsking(false);
    }
  };

  const explain = async () => {
    if (!result) return;
    setExplaining(true);
    try { setPlain(await explApi.explain(result.description)); }
    finally { setExplaining(false); }
  };

  const openInWorkstation = async () => {
    if (!file) return;
    setRouting(true);
    try {
      const c = await wlApi.upload(file);
      router.push(`/case/${c.case_id}`);
    } catch (e) { setError(`Could not open in workstation: ${e}`); setRouting(false); }
  };

  // ── Box drawing → MedSAM ────────────────────────────────────────────────────
  const localXY = (e: React.PointerEvent) => {
    const r = imgRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const onDown = (e: React.PointerEvent) => {
    if (!segMode || !imgRef.current) return;
    const p = localXY(e);
    startRef.current = p;
    setDrawBox({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  };
  const onMove = (e: React.PointerEvent) => {
    if (!startRef.current) return;
    const p = localXY(e);
    setDrawBox({ x0: startRef.current.x, y0: startRef.current.y, x1: p.x, y1: p.y });
  };
  const onUp = async () => {
    const img = imgRef.current;
    if (!startRef.current || !drawBox || !img || !result) { startRef.current = null; return; }
    startRef.current = null;
    const r = img.getBoundingClientRect();
    const sx = img.naturalWidth / r.width;
    const sy = img.naturalHeight / r.height;
    const box = [
      Math.min(drawBox.x0, drawBox.x1) * sx,
      Math.min(drawBox.y0, drawBox.y1) * sy,
      Math.max(drawBox.x0, drawBox.x1) * sx,
      Math.max(drawBox.y0, drawBox.y1) * sy,
    ];
    setDrawBox(null);
    if (box[2] - box[0] < 8 || box[3] - box[1] < 8) return; // ignore tiny boxes
    setSegLoading(true);
    try {
      const s = await generalApi.segment(result.image_id, box);
      setSeg(s); setViewSeg(true); setSegMode(false);
    } catch (e) { setError(`Segmentation failed: ${e}`); }
    finally { setSegLoading(false); }
  };

  const ModIcon = result ? MODALITY_ICON[result.modality] ?? Brain : Brain;
  const imgSrc = result ? (viewSeg && seg ? seg.overlay_url : result.image_url) : '';

  return (
    <div className="p-8 max-w-6xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-11 h-11 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center">
          <Brain className="w-5 h-5 text-accent-purple" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">General Medical</h1>
          <p className="text-sm text-slate-500">
            Any modality — CT, MRI, dermatology, fundus, histopathology. MedGemma reading + MedSAM segmentation.
          </p>
        </div>
      </div>

      <div className="flex items-start gap-2.5 bg-accent-purple/5 border border-accent-purple/20 rounded-xl px-4 py-3 mb-6 text-xs text-slate-400 leading-relaxed">
        <AlertTriangle className="w-4 h-4 text-accent-purple shrink-0 mt-0.5" />
        <span>
          <strong className="text-slate-300">MedGemma + MedSAM — no specialist verification.</strong> The CXR
          classifier / grounding / triage are deliberately <em>not</em> run here. Treat results as exploratory;
          uncertainty is higher off-CXR. Research demo, not diagnostic.
        </span>
      </div>

      {/* Upload */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) analyze(e.dataTransfer.files[0]); }}
        onClick={() => fileRef.current?.click()}
        className={`mb-6 border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
          dragging ? 'border-accent-purple bg-accent-purple/10 scale-[1.01]' : 'border-border hover:border-surface-4 bg-surface-1/40'
        }`}
      >
        <UploadCloud className="w-8 h-8 mx-auto mb-2 text-slate-500" />
        <div className="text-sm text-slate-300 font-medium">{file ? `Selected: ${file.name}` : 'Drop a medical image, or click to choose'}</div>
        <div className="text-xs text-slate-500 mt-1">PNG / JPG / DICOM — any modality</div>
        <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.dcm,.dicom" className="hidden"
          onChange={(e) => e.target.files?.[0] && analyze(e.target.files[0])} />
      </div>

      {error && <div className="mb-6 p-4 rounded-xl bg-critical/10 border border-critical/30 text-critical text-sm">{error}</div>}

      {analyzing && (
        <div className="flex items-center gap-3 text-slate-400 text-sm py-10 justify-center">
          <Sparkles className="w-5 h-5 animate-pulse text-accent-purple" /> MedGemma is identifying the modality and describing the image…
        </div>
      )}

      {result && !analyzing && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up">
          {/* Image + segmentation + modality */}
          <div className="space-y-4">
            <div className="card p-2">
              {/* Segment toolbar */}
              <div className="flex items-center gap-2 px-1 py-1.5">
                <button
                  onClick={() => { setSegMode((m) => !m); setDrawBox(null); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                    segMode ? 'bg-accent-teal/20 text-accent-teal border border-accent-teal/40' : 'bg-surface-2 text-slate-300 border border-border hover:bg-surface-3'
                  }`}
                >
                  <Crop className="w-3.5 h-3.5" /> {segMode ? 'Draw a box…' : 'Segment a region (MedSAM)'}
                </button>
                {segLoading && <span className="text-xs text-accent-teal flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 animate-pulse" /> Segmenting…</span>}
                {seg && !segLoading && (
                  <>
                    <button onClick={() => setViewSeg((v) => !v)} className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded-lg hover:bg-surface-3">
                      {viewSeg ? 'Show original' : 'Show mask'}
                    </button>
                    <button onClick={() => { setSeg(null); setViewSeg(false); }} className="text-slate-500 hover:text-critical p-1" title="Clear">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>

              {/* Image with draw overlay */}
              <div className="relative film rounded-lg overflow-hidden flex items-center justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={imgRef}
                  src={imgSrc}
                  alt="uploaded"
                  draggable={false}
                  className="max-w-full max-h-[460px] object-contain select-none"
                />
                {segMode && (
                  <div
                    className="absolute inset-0 cursor-crosshair"
                    onPointerDown={onDown}
                    onPointerMove={onMove}
                    onPointerUp={onUp}
                    onPointerLeave={onUp}
                  >
                    {drawBox && (
                      <div
                        className="absolute border-2 border-accent-teal bg-accent-teal/10 pointer-events-none"
                        style={{
                          left: Math.min(drawBox.x0, drawBox.x1),
                          top: Math.min(drawBox.y0, drawBox.y1),
                          width: Math.abs(drawBox.x1 - drawBox.x0),
                          height: Math.abs(drawBox.y1 - drawBox.y0),
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
              {segMode && (
                <div className="px-1 pt-1.5 text-[11px] text-slate-500">Drag a box around a structure — MedSAM segments it (any modality).</div>
              )}
            </div>

            {/* Measurements */}
            {seg && (
              <div className="card p-4">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-2">MedSAM measurement</div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div><div className="text-lg font-bold text-accent-teal tabular">{seg.area_px.toLocaleString()}</div><div className="text-[10px] text-slate-500 uppercase">px² area</div></div>
                  <div><div className="text-lg font-bold text-slate-100 tabular">{seg.width_px}×{seg.height_px}</div><div className="text-[10px] text-slate-500 uppercase">bbox px</div></div>
                  <div><div className="text-lg font-bold text-slate-100 tabular">{seg.area_pct}%</div><div className="text-[10px] text-slate-500 uppercase">of image</div></div>
                </div>
              </div>
            )}

            {/* Modality */}
            <div className="card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center shrink-0">
                <ModIcon className="w-5 h-5 text-accent-purple" />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Detected</div>
                <div className="text-slate-100 font-bold">{result.modality}{result.region ? ` · ${result.region}` : ''}</div>
              </div>
            </div>

            {result.is_cxr && (
              <button
                onClick={openInWorkstation}
                disabled={routing}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-surface-1 bg-gradient-to-r from-accent-teal to-accent-sky shadow-glow hover:brightness-110 transition disabled:opacity-60"
              >
                {routing ? 'Opening…' : (<>This is a chest X-ray — open in the CXR Workstation <ArrowRight className="w-4 h-4" /></>)}
              </button>
            )}
          </div>

          {/* Description + VQA + explainer */}
          <div className="space-y-4">
            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-accent-purple" /> Description
              </div>
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{result.description}</div>
              <button onClick={explain} disabled={explaining}
                className="mt-4 inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-2 border border-border text-xs font-semibold text-slate-300 hover:text-slate-100 hover:border-accent-sky/40 transition disabled:opacity-50">
                <Sparkles className="w-3.5 h-3.5" /> {explaining ? 'Translating…' : 'Explain in plain language'}
              </button>
              {plain && (
                <div className="mt-3 p-3 rounded-xl bg-accent-teal/5 border border-accent-teal/20 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{plain.plain}</div>
              )}
            </div>

            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4 text-accent-sky" /> Ask about this image
              </div>
              <div className="space-y-3 mb-3 max-h-72 overflow-auto">
                {chat.length === 0 && <div className="text-xs text-slate-500">e.g. “What is the main abnormality?” · “Which structures are visible?”</div>}
                {chat.map((m, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="text-sm text-slate-300 bg-surface-2 rounded-lg px-3 py-2 border border-border">{m.q}</div>
                    <div className="text-sm text-slate-200 bg-surface-1 rounded-lg px-3 py-2 border border-surface-3 whitespace-pre-wrap">{m.a}</div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask()}
                  placeholder="Ask a question…"
                  className="flex-1 bg-surface-1 border border-border rounded-xl px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-accent-sky" />
                <button onClick={ask} disabled={asking || !question.trim()} className="px-4 rounded-xl bg-accent-sky text-surface-1 font-bold hover:bg-accent-teal transition disabled:opacity-50">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
