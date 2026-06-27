export default function SettingsPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Settings</h1>
      <p className="text-sm text-slate-500 mb-8">RadQuant configuration and system info.</p>

      <div className="space-y-4">
        <Section title="Model">
          <Row label="Vision-Language Model" value="MedGemma 1.5 4B (google/medgemma-1.5-4b-it)" />
          <Row label="Classifier" value="TorchXRayVision DenseNet-121 Ensemble (all / chex / nih)" />
          <Row label="Orchestrator LLM" value="Groq openai/gpt-oss-120b (via OpenAI-compatible API)" />
          <Row label="Grounding Model" value="alex-feeel/medgemma-cxr-auditor-v2" />
        </Section>

        <Section title="Inference Settings">
          <Row label="Quantization" value="4-bit NF4 on ≤16GB GPU · bf16 on ≥24GB GPU" />
          <Row label="Beam Width (MedGemma)" value="4 beams (improved coherence)" />
          <Row label="Repetition Penalty" value="1.2" />
          <Row label="Pan-and-Scan" value="Enabled (4 crops — improved fine-detail resolution)" />
        </Section>

        <Section title="Detection Thresholds">
          <div className="grid grid-cols-2 gap-x-8 gap-y-1">
            {[
              ['Pneumothorax', '0.35'], ['Pneumonia', '0.40'],
              ['Effusion', '0.42'], ['Edema', '0.45'],
              ['Consolidation', '0.45'], ['Cardiomegaly', '0.50'],
              ['Atelectasis', '0.55'], ['Emphysema', '0.55'],
              ['Fibrosis', '0.58'], ['Hernia', '0.60'],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between text-sm py-0.5">
                <span className="text-slate-400">{label}</span>
                <span className="text-slate-300 font-mono">{val}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-2">
            Per-pathology thresholds — critical findings use lower values for higher sensitivity.
          </p>
        </Section>

        <Section title="Backend">
          <Row label="API" value="FastAPI · Uvicorn (port 8000)" />
          <Row label="Frontend" value="Next.js 14 · Tailwind CSS (port 3000)" />
          <Row label="API docs" value={<a href="/api/docs" target="_blank" className="text-accent-sky hover:underline">/api/docs (Swagger)</a>} />
        </Section>

        <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-xl px-4 py-3 text-xs text-yellow-400">
          ⚠️ Research / assistive demo only — not a medical device. Not for clinical use without
          site-level validation and regulatory review.
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-2 border border-border rounded-xl p-5">
      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start text-sm py-0.5">
      <span className="text-slate-400 shrink-0 mr-4">{label}</span>
      <span className="text-slate-200 text-right">{value}</span>
    </div>
  );
}
