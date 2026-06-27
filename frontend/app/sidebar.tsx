'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Activity,
  Stethoscope,
  LayoutDashboard,
  Settings,
  FileText,
  Network,
  Brain,
  Boxes,
} from 'lucide-react';

const NAV = [
  { href: '/worklist', icon: LayoutDashboard, label: 'Worklist' },
  { href: '/case', icon: Stethoscope, label: 'Active Case' },
  { href: '/insights', icon: Network, label: 'Insights Graph' },
  { href: '/ct', icon: Boxes, label: 'CT Reader' },
  { href: '/general', icon: Brain, label: 'General Medical' },
  { href: '/explainer', icon: FileText, label: 'Patient Explainer' },
  { href: '/settings', icon: Settings, label: 'System Settings' },
];

export default function Sidebar() {
  const pathname = usePathname() || '';
  const isActive = (href: string) =>
    href === '/worklist'
      ? pathname === '/' || pathname.startsWith('/worklist')
      : pathname.startsWith(href);

  return (
    <aside className="w-64 shrink-0 border-r border-border flex flex-col bg-surface-1/70 backdrop-blur-xl">
      {/* Brand */}
      <div className="px-5 py-6 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-accent-teal/20 to-accent-sky/20 border border-accent-teal/30 flex items-center justify-center">
            <Activity className="w-5 h-5 text-accent-teal" />
          </div>
          <div className="leading-none">
            <div className="text-xl font-extrabold tracking-tight">
              Rad<span className="brand-gradient">Quant</span>
            </div>
          </div>
        </div>
        {/* ECG sweep accent */}
        <svg viewBox="0 0 220 24" className="w-full h-5 mt-3 opacity-70" preserveAspectRatio="none">
          <path
            d="M0 12 H60 l6 -9 l7 18 l6 -9 H120 l5 -5 l5 5 H220"
            fill="none"
            stroke="url(#ecgGrad)"
            strokeWidth="1.5"
            className="ecg-line"
          />
          <defs>
            <linearGradient id="ecgGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#2DD4BF" />
              <stop offset="100%" stopColor="#38BDF8" />
            </linearGradient>
          </defs>
        </svg>
        <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em] mt-1">
          Chest X-ray Workstation
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                active
                  ? 'bg-accent-teal/10 text-slate-100'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-surface-2'
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full bg-gradient-to-b from-accent-teal to-accent-sky" />
              )}
              <Icon className={`w-[18px] h-[18px] ${active ? 'text-accent-teal' : 'text-slate-500 group-hover:text-slate-300'}`} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-border space-y-3">
        <div className="rounded-xl bg-surface-2/60 border border-border px-3 py-2.5">
          <div className="flex items-center gap-2 text-[11px] text-chronic font-semibold">
            <span className="pulse-dot w-1.5 h-1.5 rounded-full bg-chronic text-chronic" />
            Engine online · 100% local
          </div>
          <div className="mt-2 space-y-0.5 text-[11px] text-slate-500 font-mono">
            <div>MedGemma 1.5 · 4B</div>
            <div>TorchXRayVision · DenseNet-121</div>
          </div>
        </div>
        <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-urgent/10 text-urgent text-[9px] font-bold uppercase tracking-wider border border-urgent/20">
          <span className="w-1.5 h-1.5 rounded-full bg-urgent animate-pulse" />
          Research demo — not for clinical use
        </div>
      </div>
    </aside>
  );
}
