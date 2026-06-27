'use client';

import { useState } from 'react';
import { explainer as explApi, ExplainOut } from '@/lib/api';
import { FileText, Sparkles, BookOpen, AlertTriangle, Search } from 'lucide-react';

const EXAMPLE = `EXAMINATION: CT abdomen/pelvis with contrast.
FINDINGS: A 3.5 cm hypodense lesion in the right hepatic lobe, indeterminate. Mild splenomegaly. No retroperitoneal lymphadenopathy. Cholelithiasis without cholecystitis.
IMPRESSION: Indeterminate hepatic lesion; recommend MRI for further characterization.`;

export default function ExplainerPage() {
  const [report, setReport] = useState(EXAMPLE);
  const [result, setResult] = useState<ExplainOut | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!report.trim()) return;
    setLoading(true);
    try {
      setResult(await explApi.explain(report));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100 tracking-tight flex items-center gap-3">
          Patient Explainer
          <span className="px-3 py-1 bg-accent-teal/10 text-accent-teal text-[10px] uppercase tracking-wider rounded-full border border-accent-teal/20">
            Beta
          </span>
        </h1>
        <p className="text-sm text-slate-500 mt-2 max-w-2xl leading-relaxed">
          A general report-translation utility bundled with the workstation: it turns a finished
          radiology report into plain language for patients. Text-only, so it works on any modality&apos;s
          report (X-ray, CT, MRI, ultrasound) — drafted for a radiologist to review before sharing.
        </p>
      </div>

      <div className="flex items-start gap-3 bg-urgent/10 border border-urgent/30 rounded-2xl p-5 mb-8 shadow-sm">
        <AlertTriangle className="w-5 h-5 text-urgent shrink-0 mt-0.5" />
        <div className="text-sm text-urgent/90 leading-relaxed font-medium">
          <strong className="text-urgent">Research Demo:</strong> Not for direct clinical use. Always have a qualified radiologist review the generated translation before sharing with patients.
        </div>
      </div>

      {/* Input */}
      <div className="bg-surface-2 border border-border rounded-2xl p-6 mb-8 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-slate-400" />
          <label className="text-xs font-bold text-slate-300 uppercase tracking-widest">
            Original Radiology Report
          </label>
        </div>
        <textarea
          value={report}
          onChange={e => setReport(e.target.value)}
          rows={7}
          className="w-full bg-surface-1 border border-border rounded-xl p-4 text-sm text-slate-200
                     placeholder:text-slate-600 focus:outline-none focus:border-accent-sky focus:ring-1 focus:ring-accent-sky/30 resize-none font-mono leading-relaxed"
          placeholder="Paste any radiology report here…"
        />
        <div className="mt-4 flex justify-end">
          <button
            onClick={run}
            disabled={loading || !report.trim()}
            className="flex items-center gap-2 px-6 py-2.5 bg-accent-sky text-surface-1 font-bold text-sm rounded-xl
                       hover:bg-accent-teal hover:shadow-lg hover:shadow-accent-teal/20 transition-all disabled:opacity-50"
          >
            {loading ? (
              <>
                <span className="typing-dot bg-surface-1" /><span className="typing-dot bg-surface-1" /><span className="typing-dot bg-surface-1" />
                <span className="ml-2">Translating…</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Explain Report
              </>
            )}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up">
          {/* Original with highlights */}
          <div className="bg-surface-2 border border-border rounded-2xl p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Search className="w-4 h-4 text-slate-400" />
              <div className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                Source Document
              </div>
              <div className="ml-auto text-[10px] font-medium text-slate-500 uppercase tracking-wider">
                Hover underlined terms
              </div>
            </div>
            <div
              className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-mono p-4 bg-surface-1 rounded-xl border border-surface-3"
              dangerouslySetInnerHTML={{ __html: result.highlighted_html }}
            />
          </div>

          {/* Plain language */}
          <div className="bg-surface-2 border border-accent-teal/30 rounded-2xl p-6 shadow-md shadow-accent-teal/5 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-accent-teal/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>
            <div className="flex items-center gap-2 mb-4 relative z-10">
              <Sparkles className="w-4 h-4 text-accent-teal" />
              <div className="text-xs font-bold text-accent-teal uppercase tracking-widest">
                Plain-Language Draft
              </div>
            </div>
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap relative z-10 p-4 bg-surface-1/50 rounded-xl border border-surface-3">
              {result.plain}
            </div>
          </div>

          {/* Glossary */}
          {result.glossary.length > 0 && (
            <div className="col-span-1 lg:col-span-2 bg-surface-2 border border-border rounded-2xl p-6 shadow-sm mt-2">
              <div className="flex items-center gap-2 mb-6">
                <BookOpen className="w-4 h-4 text-accent-sky" />
                <div className="text-xs font-bold text-slate-300 uppercase tracking-widest">
                  Medical Glossary
                </div>
                <div className="ml-2 px-2 py-0.5 bg-surface-3 rounded-md text-[10px] font-bold text-slate-400">
                  {result.glossary.length} TERMS
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-4">
                {result.glossary.map(g => (
                  <div key={g.term} className="text-sm p-3 bg-surface-1 rounded-xl border border-surface-3 flex flex-col gap-1">
                    <span className="font-bold text-accent-sky tracking-wide">{g.term}</span>
                    <span className="text-slate-400 leading-relaxed">{g.definition}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
