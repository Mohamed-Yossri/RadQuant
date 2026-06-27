'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * "Active Case" tab has no case id of its own — route it to the last case the
 * user opened (remembered in localStorage), or to the worklist if none yet.
 */
export default function CaseIndexPage() {
  const router = useRouter();
  useEffect(() => {
    const last = typeof window !== 'undefined' ? localStorage.getItem('radquant:lastCase') : null;
    router.replace(last ? `/case/${last}` : '/worklist');
  }, [router]);

  return (
    <div className="p-8 text-sm text-slate-500">Opening your active case…</div>
  );
}
