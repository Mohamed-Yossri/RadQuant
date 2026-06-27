import { Cpu, ScanLine, Bot, Crosshair, Gauge, Server, ShieldAlert, Info } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight mb-1.5">System Settings</h1>
      <p className="text-sm text-slate-500 mb-8">RadQuant configuration, models, and system info.</p>

      {/* What RadQuant is — scope clarity */}
      <div className="card p-5 mb-5 border-l-2 border-l-accent-teal">
        <div className="flex items-center gap-2 mb-2">
          <Info className="w-4 h-4 text-accent-teal" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">What this is</span>
        </div>
        <p className="text-sm text-slate-400 leading-relaxed">
          A <span className="text-slate-200 font-semibold">chest X-ray reading workstation</span> — triage,
          report drafting, omission QC, localization, segmentation and a patient explainer, all running
          locally. The reasoning engine (MedGemma 1.5 4B) is separately{' '}
          <span className="text-slate-200 font-semibold">benchmarked on ChestAgentBench at 57.6%</span> (matching
          GPT-4o), which measures the model&apos;s chest-case reasoning — not the workstation features themselves.
        </p>
      </div>

      <div className="space-y-4">
        <Section title="Models" icon={Cpu}>
          <Row icon={Bot} label="Vision-Language Model" value="MedGemma 1.5 4B (google/medgemma-1.5-4b-it)" />
          <Row icon={ScanLine} label="Classifier" value="TorchXRayVision DenseNet-121 (densenet121-res224-all)" />
          <Row icon={Server} label="Orchestrator LLM" value="NVIDIA NIM · meta/llama-3.3-70b-instruct (Groq gpt-oss-120b optional)" />
          <Row icon={Crosshair} label="Grounding Model" value="alex-feeel/medgemma-cxr-auditor-v2" />
          <Row icon={ScanLine} label="Segmentation (general)" value="MedSAM ViT-B (flaviagiammarino/medsam-vit-base) — box-prompted, any modality" />
        </Section>

        <Section title="Inference" icon={Gauge}>
          <Row label="Precision" value="bf16 on ≥24 GB GPU · 4-bit NF4 on ≤16 GB GPU" />
          <Row label="Decoding" value="Greedy (deterministic) · concise chain-of-thought for the eval" />
          <Row label="Device" value="Auto-detected (CUDA → CPU fallback)" />
        </Section>

        <Section title="Detection Thresholds" icon={ScanLine}>
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
                <span className="text-slate-300 font-mono tabular">{val}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-3">
            Per-pathology thresholds — critical findings use lower values for higher sensitivity.
          </p>
        </Section>

        <Section title="Backend" icon={Server}>
          <Row label="API" value="FastAPI · Uvicorn (port 8000)" />
          <Row label="Frontend" value="Next.js 14 · Tailwind CSS (port 3000)" />
          <Row
            label="API docs"
            value={
              <a href="/api/docs" target="_blank" className="text-accent-sky hover:underline">
                /api/docs (Swagger)
              </a>
            }
          />
        </Section>

        <div className="flex items-start gap-2.5 bg-urgent/5 border border-urgent/20 rounded-xl px-4 py-3 text-xs text-urgent/90">
          <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Research / assistive demo only — not a medical device. Not for clinical use without
            site-level validation and regulatory review.
          </span>
        </div>
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-slate-500" />
        <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">{title}</div>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({ icon: Icon, label, value }: { icon?: React.ElementType; label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start text-sm py-1 gap-4">
      <span className="text-slate-400 shrink-0 flex items-center gap-2">
        {Icon && <Icon className="w-3.5 h-3.5 text-slate-600" />}
        {label}
      </span>
      <span className="text-slate-200 text-right">{value}</span>
    </div>
  );
}
