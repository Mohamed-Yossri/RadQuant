'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { cases as casesApi, worklist as wlApi, CaseOut, OmissionItem,
         LocalizationFinding, urgencyColor, urgencyLabel, tierColor, caseImageUrl } from '@/lib/api';
import { ArrowLeft, Cpu, Focus, Search, ShieldAlert, CheckCircle, Brain, Send, Flame, Zap, Layers, FileText } from 'lucide-react';

type ViewMode = 'original' | 'gradcam' | 'grounding' | 'segmentation';

export default function CasePage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [caseData, setCaseData] = useState<CaseOut | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('original');
  const [overlays, setOverlays] = useState<Record<string, string>>({});
  const [findings, setFindings] = useState('');
  const [impression, setImpression] = useState('');
  const [omissions, setOmissions] = useState<OmissionItem[]>([]);
  const [localFindings, setLocalFindings] = useState<LocalizationFinding[]>([]);
  const [structures, setStructures] = useState<string[]>([]);
  const [ctr, setCtr] = useState<number | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftProgress, setDraftProgress] = useState('');
  const [qcLoading, setQcLoading] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [finalized, setFinalized] = useState(false);
  // which vision action is running, + a status line for its result/errors
  const [busy, setBusy] = useState<null | 'gradcam' | 'localize' | 'segment'>(null);
  const [actionMsg, setActionMsg] = useState<{ kind: 'info' | 'success' | 'error'; text: string } | null>(null);
  const [chat, setChat] = useState<{ role: 'user' | 'ai'; text: string; tools?: string[] }[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    wlApi
      .getCase(caseId)
      .then((c) => {
        setCaseData(c);
        // remember this as the "active case" for the sidebar tab
        if (typeof window !== 'undefined') localStorage.setItem('radquant:lastCase', caseId);
      })
      .catch(() => {
        // stale/deleted id (e.g. worklist was cleared) — forget it and bail out
        if (typeof window !== 'undefined') localStorage.removeItem('radquant:lastCase');
        router.replace('/worklist');
      });
  }, [caseId, router]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat]);

  const generateDraft = () => {
    setDraftLoading(true);
    setDraftProgress('Connecting…');
    const es = casesApi.streamDraft(caseId);
    es.addEventListener('progress', (e: MessageEvent) => {
      const d = JSON.parse(e.data);
      setDraftProgress(d.message);
    });
    es.addEventListener('draft', (e: MessageEvent) => {
      const d = JSON.parse(e.data);
      setFindings(d.findings);
      setImpression(d.impression);
      setDraftLoading(false);
      setDraftProgress('');
      es.close();
    });
    es.onerror = () => { setDraftLoading(false); setDraftProgress(''); es.close(); };
  };

  const runGradCAM = async () => {
    setBusy('gradcam');
    setActionMsg(null);
    try {
      const r = await casesApi.gradcam(caseId);
      setOverlays(o => ({ ...o, gradcam: r.overlay_url }));
      setViewMode('gradcam');
      setActionMsg({ kind: 'success', text: `Grad-CAM ready — focused on ${r.top_finding}.` });
    } catch (e) {
      setActionMsg({ kind: 'error', text: `Grad-CAM failed: ${e instanceof Error ? e.message : e}` });
    } finally {
      setBusy(null);
    }
  };

  const runLocalize = async () => {
    setBusy('localize');
    setActionMsg(null);
    try {
      const r = await casesApi.localize(caseId);
      setLocalFindings(r.findings);
      if (r.findings.length > 0 && r.overlay_url) {
        setOverlays(o => ({ ...o, grounding: r.overlay_url }));
        setViewMode('grounding');
        setActionMsg({ kind: 'success', text: `Localized ${r.findings.length} finding${r.findings.length > 1 ? 's' : ''}.` });
      } else {
        setActionMsg({ kind: 'info', text: 'No focal findings to localize on this image — the grounding model found nothing to box.' });
      }
    } catch (e) {
      setActionMsg({ kind: 'error', text: `Localization failed: ${e instanceof Error ? e.message : e}` });
    } finally {
      setBusy(null);
    }
  };

  const runSegment = async () => {
    setBusy('segment');
    setActionMsg(null);
    try {
      const r = await casesApi.segment(caseId);
      if (r.overlay_url) {
        setOverlays(o => ({ ...o, segmentation: r.overlay_url }));
        setStructures(r.structures);
        setCtr(r.cardiothoracic_ratio);
        setViewMode('segmentation');
        const ctrTxt = r.cardiothoracic_ratio != null ? ` · CTR ${r.cardiothoracic_ratio.toFixed(2)} (${r.ctr_flag})` : '';
        setActionMsg({ kind: 'success', text: `Segmented ${r.structures.length} structure${r.structures.length > 1 ? 's' : ''}${ctrTxt}.` });
      } else {
        setActionMsg({ kind: 'info', text: 'Segmentation produced no anatomy mask for this image.' });
      }
    } catch (e) {
      setActionMsg({ kind: 'error', text: `Segmentation failed: ${e instanceof Error ? e.message : e}` });
    } finally {
      setBusy(null);
    }
  };

  const runQC = async () => {
    setQcLoading(true);
    const report = `FINDINGS: ${findings}\n\nIMPRESSION: ${impression}`;
    const r = await casesApi.qc(caseId, report);
    setOmissions(r.omissions);
    setQcLoading(false);
  };

  const finalizeCase = async () => {
    setFinalizing(true);
    await casesApi.finalize(caseId, findings, impression);
    await wlApi.updateStatus(caseId, 'finalized');
    setFinalized(true);
    setFinalizing(false);
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const q = chatInput.trim();
    setChatInput('');
    setChat(c => [...c, { role: 'user', text: q }]);
    setChatLoading(true);
    try {
      const res = await casesApi.streamChat(caseId, q);
      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split('\n\n');
        buf = parts.pop() ?? '';
        for (const part of parts) {
          const lines = part.split('\n');
          const evtLine = lines.find(l => l.startsWith('event:'));
          const dataLine = lines.find(l => l.startsWith('data:'));
          if (!evtLine || !dataLine) continue;
          const evt = evtLine.replace('event:', '').trim();
          const data = JSON.parse(dataLine.replace('data:', '').trim());
          if (evt === 'answer') {
            setChat(c => [...c, { role: 'ai', text: data.answer, tools: data.tools }]);
          }
        }
      }
    } catch (e) {
      setChat(c => [...c, { role: 'ai', text: `Error: ${e}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  if (!caseData) return <Loading />;

  const uColor = urgencyColor(caseData.urgency_score);
  const uLabel = urgencyLabel(caseData.urgency_score);
  const imgSrc = caseImageUrl(caseData.case_id);
  const views: ViewMode[] = ['original'];
  if (overlays.gradcam) views.push('gradcam');
  if (overlays.grounding) views.push('grounding');
  if (overlays.segmentation) views.push('segmentation');

  return (
    <div className="p-8 max-w-[1400px] mx-auto animate-fade-in flex flex-col min-h-screen">
      {/* Header Bar */}
      <div className="flex items-center gap-6 mb-8 bg-surface-2 p-4 rounded-2xl border border-border shadow-sm">
        <a href="/worklist" className="flex items-center gap-2 text-slate-400 hover:text-accent-sky transition font-semibold text-sm">
          <ArrowLeft className="w-4 h-4" /> Worklist
        </a>
        <div className="w-px h-8 bg-border"></div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">{caseData.case_id}</h1>
            <span className="text-[10px] px-2.5 py-1 rounded-md font-bold uppercase tracking-wider"
              style={{ background: `${uColor}15`, color: uColor, border: `1px solid ${uColor}30` }}>
              {uLabel} {caseData.urgency_score.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 mt-2">
            {caseData.top_findings.map(f => (
              <span key={f.label} className="text-[10px] px-2 py-0.5 rounded border font-semibold uppercase tracking-wider"
                style={{ borderColor: `${tierColor(f.tier)}40`, color: tierColor(f.tier),
                         background: `${tierColor(f.tier)}10` }}>
                {f.label} {(f.probability * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>
        {finalized && (
          <div className="flex items-center gap-2 px-4 py-2 bg-chronic/10 text-chronic border border-chronic/20 rounded-xl text-sm font-bold tracking-wide">
            <CheckCircle className="w-5 h-5" />
            FINALIZED
          </div>
        )}
      </div>

      {/* Main Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1">
        
        {/* Left Column: Image Viewer (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          
          {/* Action Toolbar */}
          <div className="flex flex-wrap gap-2 p-2 bg-surface-1 border border-border rounded-xl">
            <ActionBtn onClick={generateDraft} loading={draftLoading} icon={<Cpu className="w-4 h-4" />}
              label="Draft + Grad-CAM" primary hint={draftProgress} />
            <div className="w-px h-6 my-auto bg-border mx-1"></div>
            <ActionBtn onClick={runGradCAM} loading={busy === 'gradcam'} disabled={busy !== null}
              hint={busy === 'gradcam' ? 'Working…' : undefined}
              icon={<Flame className="w-4 h-4 text-orange-500" />} label="Grad-CAM" />
            <ActionBtn onClick={runLocalize} loading={busy === 'localize'} disabled={busy !== null}
              hint={busy === 'localize' ? 'Localizing…' : undefined}
              icon={<Focus className="w-4 h-4 text-accent-sky" />} label="Localize" />
            <ActionBtn onClick={runSegment} loading={busy === 'segment'} disabled={busy !== null}
              hint={busy === 'segment' ? 'Segmenting…' : undefined}
              icon={<Layers className="w-4 h-4 text-purple-400" />} label="Segment" />
            <div className="flex-1"></div>
            <ActionBtn onClick={runQC} loading={qcLoading} icon={<ShieldAlert className="w-4 h-4 text-urgent" />} label="Omission QC" />
          </div>

          {/* Action status line — feedback for the vision tools */}
          {(busy || actionMsg) && (
            <div
              className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-xs font-medium border ${
                busy
                  ? 'bg-accent-sky/10 border-accent-sky/30 text-accent-sky'
                  : actionMsg?.kind === 'error'
                  ? 'bg-critical/10 border-critical/30 text-critical'
                  : actionMsg?.kind === 'success'
                  ? 'bg-chronic/10 border-chronic/30 text-chronic'
                  : 'bg-surface-2 border-border text-slate-400'
              }`}
            >
              {busy ? (
                <>
                  <Zap className="w-3.5 h-3.5 animate-pulse shrink-0" />
                  <span>
                    {busy === 'localize'
                      ? 'Running the grounding model… (first run loads ~8 GB, this can take up to a minute)'
                      : busy === 'segment'
                      ? 'Segmenting lung fields & heart…'
                      : 'Computing Grad-CAM…'}
                  </span>
                </>
              ) : (
                <span>{actionMsg?.text}</span>
              )}
            </div>
          )}

          <div className="glass rounded-2xl overflow-hidden flex-1 flex flex-col min-h-[600px] border border-border">
            {/* View Selector Tabs */}
            <div className="flex gap-1 p-2 border-b border-border bg-surface-1/80">
              {views.map(v => (
                <button key={v} onClick={() => setViewMode(v)}
                  className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
                    viewMode === v ? 'bg-accent-sky text-surface-1 shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-surface-3'
                  }`}>
                  {v === 'gradcam' ? 'Grad-CAM' : v === 'grounding' ? 'Boxes' : v}
                </button>
              ))}
            </div>
            
            {/* Image Canvas — clinical film viewbox */}
            <div className="relative flex-1 film overflow-hidden flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={viewMode === 'original' ? imgSrc : (overlays[viewMode] || imgSrc)}
                alt={`CXR ${viewMode}`}
                className="max-w-full max-h-full object-contain"
              />
            </div>

            {/* Overlay Meta Bar */}
            {viewMode === 'grounding' && localFindings.length > 0 && (
              <div className="p-4 border-t border-border bg-surface-1/90 backdrop-blur">
                <div className="text-[10px] font-bold text-accent-sky uppercase tracking-widest mb-3">Localized Findings</div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                  {localFindings.map((f, i) => (
                    <div key={i} className="text-xs text-slate-300 flex justify-between items-center bg-surface-2 px-3 py-2 rounded-lg border border-surface-3">
                      <span className="font-semibold">{f.label_pretty}</span>
                      <span className="text-slate-500 font-mono text-[10px]">{f.zone} · {(f.confidence * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {viewMode === 'segmentation' && structures.length > 0 && (
              <div className="p-4 border-t border-border bg-surface-1/90 backdrop-blur text-xs text-slate-400 flex items-center gap-4">
                <div><span className="font-bold text-slate-300">Structures:</span> {structures.join(', ')}</div>
                {ctr !== null && (
                  <div className={`px-3 py-1 rounded border font-bold ${ctr > 0.5 ? 'bg-urgent/10 border-urgent/30 text-urgent' : 'bg-chronic/10 border-chronic/30 text-chronic'}`}>
                    CTR: {ctr.toFixed(2)} {ctr > 0.5 ? '⚠️' : '✓'}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Report & Assistant (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          
          {/* Report Editor */}
          <div className="bg-surface-2 border border-border rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Draft Report
              </div>
              <button onClick={finalizeCase} disabled={!findings || finalized || finalizing}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-chronic/10 text-chronic font-bold text-xs rounded-lg border border-chronic/20 hover:bg-chronic/20 transition disabled:opacity-50 disabled:grayscale">
                <CheckCircle className="w-3.5 h-3.5" />
                {finalizing ? 'Saving…' : 'Sign Off'}
              </button>
            </div>
            
            {draftLoading && (
              <div className="flex items-center gap-3 bg-accent-sky/10 border border-accent-sky/20 rounded-lg p-3 mb-4">
                <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
                <span className="text-accent-sky text-xs font-semibold uppercase tracking-wider">{draftProgress}</span>
              </div>
            )}
            
            <div className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">FINDINGS</label>
                <textarea
                  value={findings}
                  onChange={e => setFindings(e.target.value)}
                  placeholder="Generate or type findings here…"
                  rows={8}
                  className="w-full bg-surface-1 border border-border rounded-xl p-4 text-sm text-slate-200
                             placeholder:text-slate-600 focus:outline-none focus:border-accent-sky focus:ring-1 focus:ring-accent-sky/50 resize-none
                             font-mono leading-relaxed transition-all"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">IMPRESSION</label>
                <textarea
                  value={impression}
                  onChange={e => setImpression(e.target.value)}
                  rows={4}
                  className="w-full bg-surface-1 border border-border rounded-xl p-4 text-sm text-slate-200
                             placeholder:text-slate-600 focus:outline-none focus:border-accent-sky focus:ring-1 focus:ring-accent-sky/50 resize-none
                             font-mono leading-relaxed transition-all"
                />
              </div>
            </div>
          </div>

          {/* Omissions alerts */}
          {omissions.length > 0 && (
            <div className="bg-urgent/10 border border-urgent/30 rounded-2xl p-5 shadow-lg shadow-urgent/5">
              <div className="flex items-center gap-2 text-[11px] font-bold text-urgent uppercase tracking-widest mb-4">
                <ShieldAlert className="w-4 h-4" />
                Omission QC Alert
              </div>
              <div className="space-y-4">
                {omissions.map((o, i) => (
                  <div key={i} className="bg-surface-1/50 rounded-xl p-3 border border-urgent/20">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-bold text-slate-200">{o.finding}</span>
                      <span className="text-[10px] font-mono text-urgent bg-urgent/10 px-2 py-0.5 rounded">
                        {(o.confidence * 100).toFixed(0)}% Conf
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mb-2 leading-relaxed">{o.suggestion}</p>
                    <button
                      onClick={() => setImpression(imp => `${imp}\n${o.suggestion}`.trim())}
                      className="text-[11px] font-bold text-accent-sky hover:text-accent-teal uppercase tracking-wider transition"
                    >
                      + Add to Impression
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Assistant Chat */}
          <div className="flex-1 bg-surface-2 border border-border rounded-2xl overflow-hidden flex flex-col shadow-sm min-h-[300px]">
            <div className="px-5 py-3 border-b border-border bg-surface-1 flex items-center gap-3">
              <Brain className="w-4 h-4 text-accent-purple" />
              <span className="text-xs font-bold text-slate-200 uppercase tracking-widest">RadQuant Assistant</span>
              <span className="ml-auto text-[10px] font-mono text-slate-500 bg-surface-3 px-2 py-0.5 rounded uppercase">Agent</span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {chat.length === 0 && (
                <div className="text-center mt-8">
                  <Brain className="w-12 h-12 mx-auto text-surface-4 mb-3" />
                  <p className="text-xs font-medium text-slate-500">
                    Ask about this case. The agent can use tools to analyze the image.
                  </p>
                </div>
              )}
              {chat.map((m, i) => (
                <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-accent-sky text-surface-1 font-medium rounded-tr-sm'
                      : 'bg-surface-3 text-slate-200 rounded-tl-sm border border-surface-4'
                  }`}>
                    {m.text}
                    {m.tools && m.tools.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-surface-4/30 flex flex-wrap gap-1">
                        {m.tools.map(t => (
                          <span key={t} className="text-[10px] font-mono bg-surface-1/50 px-1.5 py-0.5 rounded text-slate-400">
                            🛠 {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-surface-3 rounded-2xl rounded-tl-sm px-5 py-4 border border-surface-4">
                    <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            
            <div className="border-t border-border p-3 bg-surface-1/50">
              <div className="relative flex items-center">
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendChat()}
                  placeholder="Ask a clinical question…"
                  className="w-full bg-surface-1 border border-border rounded-xl pl-4 pr-12 py-3 text-sm
                             text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-accent-sky focus:ring-1 focus:ring-accent-sky/30 transition-all shadow-inner"
                />
                <button onClick={sendChat} disabled={chatLoading}
                  className="absolute right-2 p-2 bg-accent-sky text-surface-1 rounded-lg hover:bg-accent-teal transition disabled:opacity-50">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function ActionBtn({
  onClick, loading, icon, label, primary, hint, disabled
}: {
  onClick: () => void; loading?: boolean; icon: React.ReactNode; label: string;
  primary?: boolean; hint?: string; disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all
        ${primary
          ? 'bg-accent-sky text-surface-1 hover:bg-accent-teal shadow-md shadow-accent-sky/20'
          : 'bg-surface-2 border border-border text-slate-300 hover:border-accent-sky hover:text-slate-100 hover:bg-surface-3'
        } disabled:opacity-50`}
    >
      {loading ? <Zap className="w-4 h-4 animate-pulse" /> : icon}
      <span>{hint || label}</span>
    </button>
  );
}

function Loading() {
  return (
    <div className="p-8 max-w-[1400px] mx-auto h-screen flex flex-col">
      <div className="h-16 rounded-2xl shimmer mb-8" />
      <div className="grid grid-cols-12 gap-8 flex-1">
        <div className="col-span-7 rounded-2xl shimmer" />
        <div className="col-span-5 space-y-6">
          <div className="h-96 rounded-2xl shimmer" />
          <div className="h-64 rounded-2xl shimmer" />
        </div>
      </div>
    </div>
  );
}
