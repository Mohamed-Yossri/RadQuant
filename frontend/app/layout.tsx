import type { Metadata } from 'next';
import './globals.css';
import Sidebar from './sidebar';

export const metadata: Metadata = {
  title: { default: 'RadQuant', template: '%s | RadQuant' },
  description:
    'A privacy-first, locally-deployable AI workstation for chest X-ray interpretation. ' +
    'Triage, drafting, QC and explanation run on a 4B open-weights model — no patient data ' +
    'leaves the building. Research demo.',
  keywords: ['chest X-ray', 'AI radiology', 'MedGemma', 'CXR', 'radiology AI'],
  robots: 'noindex',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🫁</text></svg>" />
      </head>
      <body className="text-slate-200 font-sans antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
