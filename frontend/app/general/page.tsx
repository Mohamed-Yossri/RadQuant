'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  general as generalApi,
  explainer as explApi,
  worklist as wlApi,
  GeneralAnalyzeOut,
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

export default function GeneralPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
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

  const analyze = async (f: File) => {
    setFile(f);
    setResult(null);
    setChat([]);
    setPlain(null);
    setError(null);
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
    setQuestion('');
    setAsking(true);
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
    try {
      setPlain(await explApi.explain(result.description));
    } finally {
      setExplaining(false);
    }
  };

  const openInWorkstation = async () => {
    if (!file) return;
    setRouting(true);
    try {
      const c = await wlApi.upload(file);
      router.push(`/case/${c.case_id}`);
    } catch (e) {
      setError(`Could not open in workstation: ${e}`);
      setRouting(false);
    }
  };

  const ModIcon = result ? MODALITY_ICON[result.modality] ?? Brain : Brain;

  return (
    <div className="p-8 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div className="w-11 h-11 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center">
          <Brain className="w-5 h-5 text-accent-purple" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">General Medical</h1>
          <p className="text-sm text-slate-500">
            Any modality — CT, MRI, dermatology, fundus, histopathology. Powered by MedGemma alone.
          </p>
        </div>
      </div>

      {/* Scope banner */}
      <div className="flex items-start gap-2.5 bg-accent-purple/5 border border-accent-purple/20 rounded-xl px-4 py-3 mb-6 text-xs text-slate-400 leading-relaxed">
        <AlertTriangle className="w-4 h-4 text-accent-purple shrink-0 mt-0.5" />
        <span>
          <strong className="text-slate-300">MedGemma-only — no specialist verification.</strong> The CXR
          classifier, grounding, and segmentation are deliberately <em>not</em> run here (they are
          chest-X-ray models). Treat results as exploratory; uncertainty is higher off-CXR. Research demo,
          not diagnostic.
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
        <div className="text-sm text-slate-300 font-medium">
          {file ? `Selected: ${file.name}` : 'Drop a medical image, or click to choose'}
        </div>
        <div className="text-xs text-slate-500 mt-1">PNG / JPG / DICOM — any modality</div>
        <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.dcm,.dicom" className="hidden"
          onChange={(e) => e.target.files?.[0] && analyze(e.target.files[0])} />
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-critical/10 border border-critical/30 text-critical text-sm">{error}</div>
      )}

      {analyzing && (
        <div className="flex items-center gap-3 text-slate-400 text-sm py-10 justify-center">
          <Sparkles className="w-5 h-5 animate-pulse text-accent-purple" />
          MedGemma is identifying the modality and describing the image…
        </div>
      )}

      {result && !analyzing && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up">
          {/* Image + modality */}
          <div className="space-y-4">
            <div className="card overflow-hidden">
              <div className="film flex items-center justify-center min-h-[340px]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={result.image_url} alt="uploaded" className="max-w-full max-h-[440px] object-contain" />
              </div>
            </div>
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
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-surface-1
                           bg-gradient-to-r from-accent-teal to-accent-sky shadow-glow hover:brightness-110 transition disabled:opacity-60"
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
              <button
                onClick={explain}
                disabled={explaining}
                className="mt-4 inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-2 border border-border
                           text-xs font-semibold text-slate-300 hover:text-slate-100 hover:border-accent-sky/40 transition disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" /> {explaining ? 'Translating…' : 'Explain in plain language'}
              </button>
              {plain && (
                <div className="mt-3 p-3 rounded-xl bg-accent-teal/5 border border-accent-teal/20 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {plain.plain}
                </div>
              )}
            </div>

            {/* VQA */}
            <div className="card p-5">
              <div className="text-xs font-bold text-slate-300 uppercase tracking-widest mb-3 flex items-center gap-2">
                <Brain className="w-4 h-4 text-accent-sky" /> Ask about this image
              </div>
              <div className="space-y-3 mb-3 max-h-72 overflow-auto">
                {chat.length === 0 && (
                  <div className="text-xs text-slate-500">e.g. “What is the main abnormality?” · “Which structures are visible?”</div>
                )}
                {chat.map((m, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="text-sm text-slate-300 bg-surface-2 rounded-lg px-3 py-2 border border-border">{m.q}</div>
                    <div className="text-sm text-slate-200 bg-surface-1 rounded-lg px-3 py-2 border border-surface-3 whitespace-pre-wrap">{m.a}</div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && ask()}
                  placeholder="Ask a question…"
                  className="flex-1 bg-surface-1 border border-border rounded-xl px-3 py-2.5 text-sm text-slate-200
                             placeholder:text-slate-600 focus:outline-none focus:border-accent-sky"
                />
                <button
                  onClick={ask}
                  disabled={asking || !question.trim()}
                  className="px-4 rounded-xl bg-accent-sky text-surface-1 font-bold hover:bg-accent-teal transition disabled:opacity-50"
                >
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
