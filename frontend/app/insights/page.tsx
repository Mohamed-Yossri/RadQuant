'use client';

/**
 * Insights Graph — a clean radial knowledge graph over the worklist.
 *
 * Why radial (not force-directed): the case↔pathology graph is dense and
 * bipartite (each case shares many findings), so a physics layout collapses into
 * a hairball. Instead we place pathology "hubs" evenly on an outer ring with
 * labels fanning outward (so nodes and labels can never overlap), cases on an
 * inner ring positioned near the findings they share, and draw edges faint by
 * default — they light up only around the node you hover. Deterministic, stable,
 * readable. Data comes from /api/insights/graph.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Network,
  AlertTriangle,
  RefreshCw,
  Info,
  ZoomIn,
  ZoomOut,
  Maximize2,
  SlidersHorizontal,
} from 'lucide-react';
import { insights, tierColor, InsightsGraphData, GraphNode } from '@/lib/api';

const W = 980;
const H = 820;
const CX = W / 2;
const CY = H / 2 - 6;
const R_HUB = 270;   // hub ring radius
const R_CASE = 150;  // case ring radius

interface Placed {
  node: GraphNode;
  x: number;
  y: number;
  ang: number;
  r: number;
}

const hubRadius = (count: number) => 10 + Math.min(count, 10) * 2.1;

export default function InsightsPage() {
  const router = useRouter();
  const [data, setData] = useState<InsightsGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });

  const panRef = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const gRef = useRef<SVGGElement | null>(null);

  const load = useCallback(async (thr: number) => {
    setLoading(true);
    setError(null);
    try {
      setData(await insights.graph(thr));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(threshold);
  }, [load, threshold]);

  // ── Deterministic radial layout ─────────────────────────────────────────────
  const layout = useMemo(() => {
    if (!data) return null;
    const pos = new Map<string, Placed>();
    const hubs = data.nodes.filter((n) => n.kind === 'hub');
    const cases = data.nodes.filter((n) => n.kind === 'case');

    // Hubs: evenly spaced on the outer ring, ordered by prevalence (biggest at top)
    const count = (n: GraphNode) => data.hub_sizes[n.label] ?? 1;
    const hubsSorted = [...hubs].sort((a, b) => count(b) - count(a));
    // interleave large/small around the ring so big nodes don't bunch up
    const ordered: GraphNode[] = [];
    let lo = 0;
    let hi = hubsSorted.length - 1;
    let take = true;
    while (lo <= hi) {
      ordered.push(take ? hubsSorted[lo++] : hubsSorted[hi--]);
      take = !take;
    }
    ordered.forEach((n, i) => {
      const ang = -Math.PI / 2 + (i / Math.max(ordered.length, 1)) * Math.PI * 2;
      pos.set(n.id, {
        node: n,
        ang,
        r: hubRadius(count(n)),
        x: CX + Math.cos(ang) * R_HUB,
        y: CY + Math.sin(ang) * R_HUB,
      });
    });

    // Cases: angle = circular mean of the hubs they connect to
    const caseHubs = new Map<string, string[]>();
    for (const e of data.edges) {
      const hubId = e.target.startsWith('hub::') ? e.target : e.source;
      const caseId = e.target.startsWith('hub::') ? e.source : e.target;
      if (!caseHubs.has(caseId)) caseHubs.set(caseId, []);
      caseHubs.get(caseId)!.push(hubId);
    }
    // resolve angle collisions by nudging cases that land too close
    const used: number[] = [];
    const caseAng = new Map<string, number>();
    cases.forEach((c) => {
      const hs = caseHubs.get(c.id) ?? [];
      let sx = 0;
      let sy = 0;
      for (const h of hs) {
        const hp = pos.get(h);
        if (hp) {
          sx += Math.cos(hp.ang);
          sy += Math.sin(hp.ang);
        }
      }
      let ang = hs.length ? Math.atan2(sy, sx) : Math.random() * Math.PI * 2;
      // spread out collisions
      while (used.some((u) => Math.abs(angDiff(u, ang)) < 0.22)) ang += 0.23;
      used.push(ang);
      caseAng.set(c.id, ang);
    });
    cases.forEach((c) => {
      const ang = caseAng.get(c.id)!;
      pos.set(c.id, {
        node: c,
        ang,
        r: 7,
        x: CX + Math.cos(ang) * R_CASE,
        y: CY + Math.sin(ang) * R_CASE,
      });
    });

    return { pos, hubs: ordered, cases };
  }, [data]);

  // ── Hover adjacency ─────────────────────────────────────────────────────────
  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    if (!data) return map;
    for (const e of data.edges) {
      if (!map.has(e.source)) map.set(e.source, new Set());
      if (!map.has(e.target)) map.set(e.target, new Set());
      map.get(e.source)!.add(e.target);
      map.get(e.target)!.add(e.source);
    }
    return map;
  }, [data]);

  const lit = (id: string) => !hover || hover === id || !!adjacency.get(hover)?.has(id);

  // ── Pan / zoom ──────────────────────────────────────────────────────────────
  const onBgDown = (e: React.PointerEvent) => {
    panRef.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
  };
  const onMove = (e: React.PointerEvent) => {
    if (!panRef.current) return;
    const scale = (gRef.current?.ownerSVGElement?.clientWidth || W) / W;
    setView((v) => ({
      ...v,
      x: panRef.current!.vx + (e.clientX - panRef.current!.x) / scale,
      y: panRef.current!.vy + (e.clientY - panRef.current!.y) / scale,
    }));
  };
  const onUp = () => {
    panRef.current = null;
  };
  const zoom = (f: number) => setView((v) => ({ ...v, k: Math.max(0.5, Math.min(2.5, v.k * f)) }));
  const resetView = () => setView({ k: 1, x: 0, y: 0 });

  const nodes = data?.nodes ?? [];

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto animate-fade-in">
      <PageHeader onRefresh={() => load(threshold)} />

      <div className="mt-6 grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Canvas */}
        <div className="xl:col-span-8 rounded-2xl card overflow-hidden relative">
          {/* Controls */}
          <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between gap-3 pointer-events-none">
            <div className="pointer-events-auto flex items-center gap-3 bg-surface-2/90 backdrop-blur border border-border rounded-xl px-3 py-2 shadow-lg">
              <SlidersHorizontal className="w-4 h-4 text-accent-teal" />
              <div className="text-[11px] text-slate-400 font-medium whitespace-nowrap">
                Link strength ≥ <span className="text-slate-100 font-bold tabular">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0.3}
                max={0.8}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-28 accent-accent-teal cursor-pointer"
              />
            </div>
            <div className="pointer-events-auto flex items-center gap-1 bg-surface-2/90 backdrop-blur border border-border rounded-xl p-1 shadow-lg">
              <IconBtn onClick={() => zoom(1.2)} title="Zoom in"><ZoomIn className="w-4 h-4" /></IconBtn>
              <IconBtn onClick={() => zoom(0.83)} title="Zoom out"><ZoomOut className="w-4 h-4" /></IconBtn>
              <IconBtn onClick={resetView} title="Reset view"><Maximize2 className="w-4 h-4" /></IconBtn>
            </div>
          </div>

          {loading ? (
            <div className="h-[660px] flex items-center justify-center text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mr-3" /> Building graph…
            </div>
          ) : error ? (
            <div className="h-[660px] flex items-center justify-center px-8 text-center text-critical text-sm">{error}</div>
          ) : !layout || nodes.length === 0 ? (
            <div className="h-[660px] flex flex-col items-center justify-center text-center text-slate-400 px-8">
              <Network className="w-10 h-10 mb-3 text-slate-600" />
              No links at this strength. Lower the threshold, or seed/upload cases from the Worklist.
            </div>
          ) : (
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="w-full h-[660px] touch-none select-none cursor-grab active:cursor-grabbing"
              onPointerDown={onBgDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerLeave={onUp}
              onWheel={(e) => zoom(e.deltaY < 0 ? 1.1 : 0.9)}
            >
              <defs>
                <radialGradient id="bgGrad" cx="50%" cy="46%" r="62%">
                  <stop offset="0%" stopColor="#101a30" />
                  <stop offset="100%" stopColor="#070B14" />
                </radialGradient>
                <filter id="softGlow" x="-60%" y="-60%" width="220%" height="220%">
                  <feGaussianBlur stdDeviation="3" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <rect x={0} y={0} width={W} height={H} fill="url(#bgGrad)" />

              <g ref={gRef} transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
                {/* guide rings */}
                <circle cx={CX} cy={CY} r={R_HUB} fill="none" stroke="#1B2740" strokeWidth={1} strokeDasharray="2 6" />
                <circle cx={CX} cy={CY} r={R_CASE} fill="none" stroke="#1B2740" strokeWidth={1} strokeDasharray="2 6" />

                {/* edges */}
                {data!.edges.map((e, i) => {
                  const p = layout.pos.get(e.source);
                  const q = layout.pos.get(e.target);
                  if (!p || !q) return null;
                  const on = hover === e.source || hover === e.target;
                  const dim = hover && !on;
                  const hub = p.node.kind === 'hub' ? p : q;
                  // bow the edge gently toward the centre
                  const mx = (p.x + q.x) / 2;
                  const my = (p.y + q.y) / 2;
                  const cx = mx + (CX - mx) * 0.25;
                  const cy = my + (CY - my) * 0.25;
                  return (
                    <path
                      key={i}
                      d={`M ${p.x} ${p.y} Q ${cx} ${cy} ${q.x} ${q.y}`}
                      fill="none"
                      stroke={on ? tierColor(hub.node.tier ?? 'Unknown') : '#3B82F6'}
                      strokeOpacity={dim ? 0.025 : on ? 0.6 : 0.07}
                      strokeWidth={(on ? 1.6 : 0.7) + e.weight * 1.6}
                    />
                  );
                })}

                {/* cases (inner ring) */}
                {layout.cases.map((c) => {
                  const p = layout.pos.get(c.id)!;
                  const color = tierColor(c.tier ?? 'Unknown');
                  const isLit = lit(c.id);
                  return (
                    <g
                      key={c.id}
                      transform={`translate(${p.x},${p.y})`}
                      opacity={isLit ? 1 : 0.2}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={() => setHover(c.id)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => router.push(`/case/${c.id}`)}
                    >
                      {hover === c.id && <circle r={11} fill="none" stroke={color} strokeOpacity={0.7} />}
                      <circle r={6} fill={color} stroke="#070B14" strokeWidth={1.5} />
                      {hover === c.id && (
                        <text x={0} y={-13} textAnchor="middle" fontSize={11} fontWeight={600} fill="#E2E8F0">
                          {c.label}
                        </text>
                      )}
                    </g>
                  );
                })}

                {/* hubs (outer ring) with outward labels */}
                {layout.hubs.map((h) => {
                  const p = layout.pos.get(h.id)!;
                  const color = tierColor(h.tier ?? 'Unknown');
                  const isLit = lit(h.id);
                  const c = Math.cos(p.ang);
                  const s = Math.sin(p.ang);
                  const lx = CX + c * (R_HUB + p.r + 12);
                  const ly = CY + s * (R_HUB + p.r + 12);
                  const anchor = c > 0.2 ? 'start' : c < -0.2 ? 'end' : 'middle';
                  return (
                    <g
                      key={h.id}
                      opacity={isLit ? 1 : 0.28}
                      style={{ cursor: 'default' }}
                      onMouseEnter={() => setHover(h.id)}
                      onMouseLeave={() => setHover(null)}
                    >
                      <circle cx={p.x} cy={p.y} r={p.r + 4} fill="none" stroke={color} strokeOpacity={0.35} strokeWidth={1.5} />
                      <circle cx={p.x} cy={p.y} r={p.r} fill={color} fillOpacity={0.92} filter="url(#softGlow)" />
                      <circle cx={p.x} cy={p.y} r={p.r} fill="none" stroke="#070B14" strokeWidth={1.5} />
                      <text
                        x={lx}
                        y={ly}
                        textAnchor={anchor}
                        dominantBaseline="middle"
                        fontSize={11.5}
                        fontWeight={700}
                        fill={isLit ? '#E2E8F0' : '#64748B'}
                        style={{ pointerEvents: 'none' }}
                      >
                        {h.label}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          )}

          <div className="absolute bottom-3 left-4 text-[11px] text-slate-500 flex items-center gap-1.5 pointer-events-none">
            <Info className="w-3 h-3" /> hover a finding to trace its cases · scroll to zoom · click a case to open
          </div>
        </div>

        {/* Side panel */}
        <div className="xl:col-span-4 space-y-5">
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-urgent" />
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Cohort signals</h2>
            </div>
            {data && data.alerts.length > 0 ? (
              <ul className="space-y-2">
                {data.alerts.map((a, i) => {
                  const [name, rest] = a.split(':');
                  return (
                    <li
                      key={i}
                      className="flex items-center gap-2 text-sm bg-surface-2 rounded-lg px-3 py-2 border border-border cursor-default hover:border-surface-4 transition"
                      onMouseEnter={() => setHover(`hub::${name.trim()}`)}
                      onMouseLeave={() => setHover(null)}
                    >
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: tierColor(tierForName(name, data)) }} />
                      <span className="text-slate-200 font-medium">{name}</span>
                      <span className="text-slate-500 text-xs ml-auto">{rest?.replace(/cases.*/, 'cases').trim()}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No pathology is shared by 3+ cases at this link strength.</p>
            )}
            <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
              Exploratory descriptive signal over the current worklist — not a clinical outbreak-detection claim.
            </p>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-3">Legend</h2>
            <div className="grid grid-cols-2 gap-y-2 text-sm">
              {([['Critical', 'Critical'], ['Urgent', 'Urgent'], ['Important', 'Important'], ['Chronic', 'Chronic']] as const).map(
                ([label, tier]) => (
                  <div key={tier} className="flex items-center gap-2.5">
                    <span className="w-3 h-3 rounded-full" style={{ background: tierColor(tier) }} />
                    <span className="text-slate-400">{label}</span>
                  </div>
                ),
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-border space-y-2 text-sm">
              <div className="flex items-center gap-2.5">
                <span className="w-4 h-4 rounded-full border-2 border-slate-400" />
                <span className="text-slate-400">Pathology — outer ring, size = cases</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                <span className="text-slate-400">Case — inner ring, click to open</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-3 text-center">
              <Stat value={nodes.filter((n) => n.kind === 'case').length} label="Cases" color="text-accent-teal" />
              <Stat value={nodes.filter((n) => n.kind === 'hub').length} label="Findings" color="text-accent-sky" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function angDiff(a: number, b: number): number {
  let d = a - b;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return d;
}

function tierForName(name: string, data: InsightsGraphData): string {
  const n = data.nodes.find((x) => x.kind === 'hub' && x.label === name.trim());
  return n?.tier ?? 'Unknown';
}

function IconBtn({ onClick, title, children }: { onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300 hover:text-slate-100 hover:bg-surface-3 transition"
    >
      {children}
    </button>
  );
}

function Stat({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div>
      <div className={`text-2xl font-bold tabular ${color}`}>{value}</div>
      <div className="text-[11px] text-slate-500 uppercase tracking-wider">{label}</div>
    </div>
  );
}

function PageHeader({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-accent-sky/10 border border-accent-sky/20 flex items-center justify-center">
          <Network className="w-5 h-5 text-accent-sky" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Insights Graph</h1>
          <p className="text-sm text-slate-500">How the worklist clusters by pathology — cases linked to shared findings.</p>
        </div>
      </div>
      <button
        onClick={onRefresh}
        className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-surface-2 border border-border
                   text-sm text-slate-300 font-medium hover:text-slate-100 hover:border-accent-sky/40 transition"
      >
        <RefreshCw className="w-4 h-4" /> Refresh
      </button>
    </div>
  );
}
