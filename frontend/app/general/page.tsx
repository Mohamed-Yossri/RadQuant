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
  UploadCloud, Sparkles, Send, ArrowRight, Microscope, ScanLine, Brain,
  AlertTriangle, Stethoscope, Eye, Activity, Crop, Ruler, X,
} from 'lucide-react';

const MODALITY_ICON: Record<string, React.ElementType> = {
  'Chest X-ray': Activity, 'Other X-ray': ScanLine, CT: ScanLine, MRI: ScanLine,
  Ultrasound: Activity, 'Dermatology photo': Stethoscope, 'Fundus photo': Eye,
  Histopathology: Microscope, Other: Brain,
};

interface Draw { x0: number; y0: number; x1: number; y1: number; }
type Mode = 'none' | 'segment' | 'calibrate';

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

  const [mode, setMode] = useState<Mode>('none');
  const [draw, setDraw] = useState<Draw | null>(null);
  const [seg, setSeg] = useState<GeneralSegmentOut | null>(null);
  const [viewSeg, setViewSeg] = useState(false);
  const [segLoading, setSegLoading] = useState(false);
  const [mmPerPx, setMmPerPx] = useState<number | null>(null);
  const [calSource, setCalSource] = useState<string | null>(null);

  const resetAll = () => {
    setMode('none'); setDraw(null); setSeg(null); setViewSeg(false);
    setMmPerPx(null); setCalSource(null);
  };

  const analyze = async (f: File) => {
    setFile(f); setResult(null); setChat([]); setPlain(null); setError(null); resetAll();
    setAnalyzing(true);
    try {
      const r = await generalApi.analyze(f);
      setResult(r);
      if (r.pixel_spacing_mm) { setMmPerPx(r.pixel_spacing_mm); setCalSource('DICOM'); }
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
    } finally { setAsking(false); }
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
    try { const c = await wlApi.upload(file); router.push(`/case/${c.case_id}`); }
    catch (e) { setError(`Could not open in workstation: ${e}`); setRouting(false); }
  };

  // ── Drawing (box for segment, line for calibrate) ───────────────────────────
  const localXY = (e: React.PointerEvent) => {
    const r = imgRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const scaleX = () => {
    const img = imgRef.current!;
    return img.naturalWidth / img.getBoundingClientRect().width;
  };
  const onDown = (e: React.PointerEvent) => {
    if (mode === 'none' || !imgRef.current) return;
    const p = localXY(e); startRef.current = p;
    setDraw({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  };
  const onMove = (e: React.PointerEvent) => {
    if (!startRef.current) return;
    const p = localXY(e);
    setDraw({ x0: startRef.current.x, y0: startRef.current.y, x1: p.x, y1: p.y });
  };
  const onUp = async () => {
    const d = draw; const img = imgRef.current; const m = mode;
    if (!startRef.current || !d || !img || !result) { startRef.current = null; return; }
    startRef.current = null; setDraw(null);
    const s = scaleX();

    if (m === 'calibrate') {
      const lenPx = Math.hypot(d.x1 - d.x0, d.y1 - d.y0) * s;
      if (lenPx < 4) return;
      const ans = window.prompt('Real length of the line you drew, in millimetres?');
      const mm = ans ? parseFloat(ans) : NaN;
      if (!isNaN(mm) && mm > 0) { setMmPerPx(mm / lenPx); setCalSource('manual'); }
      setMode('none');
      return;
    }
    // segment
    const box = [
      Math.min(d.x0, d.x1) * s, Math.min(d.y0, d.y1) * s,
      Math.max(d.x0, d.x1) * s, Math.max(d.y0, d.y1) * s,
    ];
    if (box[2] - box[0] < 8 || box[3] - box[1] < 8) return;
    setSegLoading(true);
    try {
      const r = await generalApi.segment(result.image_id, box);
      setSeg(r); setViewSeg(true); setMode('none');
    } catch (e) { setError(`Segmentation failed: ${e}`); }
    finally { setSegLoading(false); }
  };

  const fmtLen = (px: number) => (mmPerPx ? `${(px * mmPerPx).toFixed(1)} mm` : `${Math.round(px)} px`);
  const fmtArea = (px: number) => (mmPerPx ? `${(px * mmPerPx * mmPerPx / 100).toFixed(2)} cm²` : `${px.toLocaleString()} px²`);

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
          <p className="text-sm text-slate-500">Any modality — MedGemma reading + MedSAM measurement (RECIST diameter, area).</p>
        </div>
      </div>

      <div className="flex items-start gap-2.5 bg-accent-purple/5 border border-accent-purple/20 rounded-xl px-4 py-3 mb-6 text-xs text-slate-400 leading-relaxed">
        <AlertTriangle className="w-4 h-4 text-accent-purple shrink-0 mt-0.5" />
        <span><strong className="text-slate-300">MedGemma + MedSAM — no specialist verification.</strong> CXR classifier / grounding / triage are not run here. Exploratory; uncertainty is higher off-CXR. Research demo, not diagnostic.</span>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) analyze(e.dataTransfer.files[0]); }}
        onClick={() => fileRef.current?.click()}
        className={`mb-6 border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${dragging ? 'border-accent-purple bg-accent-purple/10 scale-[1.01]' : 'border-border hover:border-surface-4 bg-surface-1/40'}`}
      >
        <UploadCloud className="w-8 h-8 mx-auto mb-2 text-slate-500" />
        <div className="text-sm text-slate-300 font-medium">{file ? `Selected: ${file.name}` : 'Drop a medical image, or click to choose'}</div>
        <div className="text-xs text-slate-500 mt-1">PNG / JPG / DICOM — DICOM auto-calibrates measurements to mm</div>
        <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.dcm,.dicom" className="hidden" onChange={(e) => e.target.files?.[0] && analyze(e.target.files[0])} />
      </div>

      {error && <div className="mb-6 p-4 rounded-xl bg-critical/10 border border-critical/30 text-critical text-sm">{error}</div>}
      {analyzing && <div className="flex items-center gap-3 text-slate-400 text-sm py-10 justify-center"><Sparkles className="w-5 h-5 animate-pulse text-accent-purple" /> MedGemma is identifying the modality and describing the image…</div>}

      {result && !analyzing && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up">
          <div className="space-y-4">
            <div className="card p-2">
              <div className="flex items-center flex-wrap gap-2 px-1 py-1.5">
                <button onClick={() => { setMode(mode === 'segment' ? 'none' : 'segment'); setDraw(null); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${mode === 'segment' ? 'bg-accent-teal/20 text-accent-teal border border-accent-teal/40' : 'bg-surface-2 text-slate-300 border border-border hover:bg-surface-3'}`}>
                  <Crop className="w-3.5 h-3.5" /> {mode === 'segment' ? 'Draw a box…' : 'Measure a lesion'}
                </button>
                <button onClick={() => { setMode(mode === 'calibrate' ? 'none' : 'calibrate'); setDraw(null); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${mode === 'calibrate' ? 'bg-urgent/20 text-urgent border border-urgent/40' : 'bg-surface-2 text-slate-300 border border-border hover:bg-surface-3'}`}>
                  <Ruler className="w-3.5 h-3.5" /> {mode === 'calibrate' ? 'Draw a known line…' : 'Set scale'}
                </button>
                {segLoading && <span className="text-xs text-accent-teal flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 animate-pulse" /> Segmenting…</span>}
                {seg && !segLoading && (
                  <>
                    <button onClick={() => setViewSeg((v) => !v)} className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded-lg hover:bg-surface-3">{viewSeg ? 'Original' : 'Mask'}</button>
                    <button onClick={() => { setSeg(null); setViewSeg(false); }} className="text-slate-500 hover:text-critical p-1" title="Clear"><X className="w-3.5 h-3.5" /></button>
                  </>
                )}
              </div>

              <div className="relative film rounded-lg overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img ref={imgRef} src={imgSrc} alt="uploaded" draggable={false} className="block w-full h-auto select-none" />
                {mode !== 'none' && (
                  <svg className="absolute inset-0 w-full h-full cursor-crosshair" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}>
                    {draw && mode === 'segment' && (
                      <rect x={Math.min(draw.x0, draw.x1)} y={Math.min(draw.y0, draw.y1)} width={Math.abs(draw.x1 - draw.x0)} height={Math.abs(draw.y1 - draw.y0)} fill="rgba(45,212,191,0.12)" stroke="#2DD4BF" strokeWidth={2} />
                    )}
                    {draw && mode === 'calibrate' && (
                      <line x1={draw.x0} y1={draw.y0} x2={draw.x1} y2={draw.y1} stroke="#F59E0B" strokeWidth={2.5} />
                    )}
                  </svg>
                )}
              </div>
              {mode === 'segment' && <div className="px-1 pt-1.5 text-[11px] text-slate-500">Drag a box around a lesion/structure — MedSAM segments it and measures the RECIST longest diameter.</div>}
              {mode === 'calibrate' && <div className="px-1 pt-1.5 text-[11px] text-slate-500">Draw a line over a known distance (e.g. a scale bar), then enter its length in mm.</div>}
            </div>

            {/* Measurements */}
            {seg && (
              <div className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">MedSAM measurement</div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold border ${mmPerPx ? 'bg-chronic/10 text-chronic border-chronic/20' : 'bg-urgent/10 text-urgent border-urgent/20'}`}>
                    {mmPerPx ? `calibrated · ${calSource}` : 'uncalibrated (px)'}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div><div className="text-lg font-bold text-accent-teal tabular">{fmtLen(seg.longest_diameter_px)}</div><div className="text-[10px] text-slate-500 uppercase">RECIST long axis</div></div>
                  <div><div className="text-lg font-bold text-slate-100 tabular">{fmtLen(seg.short_axis_px)}</div><div className="text-[10px] text-slate-500 uppercase">short axis</div></div>
                  <div><div className="text-lg font-bold text-slate-100 tabular">{fmtArea(seg.area_px)}</div><div className="text-[10px] text-slate-500 uppercase">area</div></div>
                </div>
                {!mmPerPx && <div className="text-[11px] text-urgent/80 mt-3">Pixels only — upload DICOM, or use <strong>Set scale</strong> to get mm/cm.</div>}
              </div>
            )}

            <div className="card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center shrink-0"><ModIcon className="w-5 h-5 text-accent-purple" /></div>
              <div className="min-w-0">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Detected</div>
                <div className="text-slate-100 font-bold">{result.modality}{result.region ? ` · ${result.region}` : ''}{mmPerPx && calSource === 'DICOM' ? ` · ${result.pixel_spacing_mm} mm/px` : ''}</div>
              </div>
            </div>

            {result.is_cxr && (
              <button onClick={openInWorkstation} disabled={routing}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-surface-1 bg-gradient-to-r from-accent-teal to-accent-sky shadow-glow hover:brightness-110 transition disabled:opacity-60">
                {routing ? 'Opening…' : (<>This is a chest X-ray — open in the CXR Workstation <ArrowRight className="w-4 h-4" /></>)}
              </button>
            )}
          </div>

          <div className="space-y-4">
            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2"><Sparkles className="w-4 h-4 text-accent-purple" /> Description</div>
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{result.description}</div>
              <button onClick={explain} disabled={explaining} className="mt-4 inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-2 border border-border text-xs font-semibold text-slate-300 hover:text-slate-100 hover:border-accent-sky/40 transition disabled:opacity-50">
                <Sparkles className="w-3.5 h-3.5" /> {explaining ? 'Translating…' : 'Explain in plain language'}
              </button>
              {plain && <div className="mt-3 p-3 rounded-xl bg-accent-teal/5 border border-accent-teal/20 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{plain.plain}</div>}
            </div>

            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2"><Brain className="w-4 h-4 text-accent-sky" /> Ask about this image</div>
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
                <input value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask()} placeholder="Ask a question…"
                  className="flex-1 bg-surface-1 border border-border rounded-xl px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-accent-sky" />
                <button onClick={ask} disabled={asking || !question.trim()} className="px-4 rounded-xl bg-accent-sky text-surface-1 font-bold hover:bg-accent-teal transition disabled:opacity-50"><Send className="w-4 h-4" /></button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
