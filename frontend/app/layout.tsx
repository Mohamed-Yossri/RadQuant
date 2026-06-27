import type { Metadata } from 'next';
import { Activity, Stethoscope, LayoutDashboard, Settings, FileText } from 'lucide-react';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'RadQuant', template: '%s | RadQuant' },
  description:
    'Privacy-first, locally-deployable AI workstation for chest X-ray interpretation. ' +
    'Matches GPT-4o accuracy on ChestAgentBench with a 4B open-weights model — research demo.',
  keywords: ['chest X-ray', 'AI radiology', 'MedGemma', 'CXR', 'radiology AI'],
  robots: 'noindex',   // research demo — not for public indexing
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚕️</text></svg>" />
      </head>
      <body className="bg-surface text-slate-200 font-sans antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

function Sidebar() {
  return (
    <aside className="w-64 shrink-0 bg-surface-1 border-r border-border flex flex-col shadow-xl">
      {/* Logo */}
      <div className="px-6 py-6 border-b border-border bg-surface-2/50">
        <div className="flex items-center gap-2 text-2xl font-bold tracking-tight leading-none">
          <Activity className="w-6 h-6 text-accent-teal" />
          <span>Rad<span className="text-accent-sky">Quant</span></span>
        </div>
        <div className="text-xs font-medium text-slate-500 mt-2 uppercase tracking-widest">
          Diagnostic Workstation
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-4 space-y-2">
        <NavLink href="/worklist" icon={<LayoutDashboard className="w-5 h-5" />} label="Worklist" />
        <NavLink href="/case" icon={<Stethoscope className="w-5 h-5" />} label="Active Case" />
        <NavLink href="/explainer" icon={<FileText className="w-5 h-5" />} label="Patient Explainer" />
        <NavLink href="/settings" icon={<Settings className="w-5 h-5" />} label="System Settings" />
      </nav>

      {/* Footer */}
      <div className="px-5 py-5 border-t border-border bg-surface-2/50">
        <div className="text-xs font-mono text-slate-500 space-y-1">
          <div>Engine: MedGemma 1.5 4B</div>
          <div>Vision: TorchXRayVision Ensemble</div>
        </div>
        <div className="mt-3 inline-flex items-center gap-1.5 px-2 py-1 rounded bg-yellow-500/10 text-yellow-500 text-[10px] font-semibold uppercase tracking-wider border border-yellow-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse"></span>
          Research Demo Only
        </div>
      </div>
    </aside>
  );
}

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <a
      href={href}
      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 font-medium
                 hover:text-slate-100 hover:bg-surface-3/50 hover:shadow-sm transition-all duration-200"
    >
      <div className="text-slate-500">{icon}</div>
      <span>{label}</span>
    </a>
  );
}
