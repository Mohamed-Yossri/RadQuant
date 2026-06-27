'use client';

/**
 * Insights Graph — an Obsidian-style knowledge graph over the worklist.
 *
 * Cases and pathology "hubs" are nodes; an edge means a case's classifier
 * cleared the link-strength threshold for that pathology. Hubs touched by many
 * cases surface as cohort signals.
 *
 * Rendered with a dependency-free force simulation (no d3 / react-force-graph so
 * it builds with the pinned package set). Readability features:
 *   - collision resolution so nodes never overlap,
 *   - edges fade to near-invisible and only light up around the hovered node
 *     (kills the "hairball" on dense worklists),
 *   - hub labels drawn in pills; case labels only on hover,
 *   - a link-strength slider (maps to the backend finding_threshold) to thin
 *     weak links, plus zoom / pan.
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

const W = 1100;
const H = 720;

interface Sim {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  node: GraphNode;
}

function radiusOf(n: GraphNode): number {
  return n.kind === 'hub'
    ? Math.max(13, n.size * 0.82)
    : Math.max(6, n.size * 0.5);
}

export default function InsightsPage() {
  const router = useRouter();
  const [data, setData] = useState<InsightsGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  const [, setTick] = useState(0);

  const simRef = useRef<Map<string, Sim>>(new Map());
  const dataRef = useRef<InsightsGraphData | null>(null);
  const dragRef = useRef<string | null>(null);
  const panRef = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const alphaRef = useRef(1);
  const runningRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const gRef = useRef<SVGGElement | null>(null);

  const load = useCallback(async (thr: number) => {
    setLoading(true);
    setError(null);
    try {
      const d = await insights.graph(thr);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(threshold);
  }, [load, threshold]);

  // ── Simulation ──────────────────────────────────────────────────────────────
  const stepOnce = useCallback(() => {
    const d = dataRef.current;
    if (!d) return;
    const sim = simRef.current;
    const arr = Array.from(sim.values());
    const alpha = alphaRef.current;

    // Repulsion (distance-capped so far nodes don't drift apart forever)
    for (let a = 0; a < arr.length; a++) {
      for (let b = a + 1; b < arr.length; b++) {
        const p = arr[a];
        const q = arr[b];
        const dx = p.x - q.x;
        const dy = p.y - q.y;
        const d2 = dx * dx + dy * dy || 0.01;
        const dist = Math.sqrt(d2);
        const rep = Math.min(4200 / d2, 40);
        const fx = (dx / dist) * rep;
        const fy = (dy / dist) * rep;
        p.vx += fx;
        p.vy += fy;
        q.vx -= fx;
        q.vy -= fy;
      }
    }

    // Springs along edges
    for (const e of d.edges) {
      const p = sim.get(e.source);
      const q = sim.get(e.target);
      if (!p || !q) continue;
      const dx = q.x - p.x;
      const dy = q.y - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const rest = p.r + q.r + 70;
      const k = 0.015 * (0.5 + e.weight);
      const f = (dist - rest) * k;
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      p.vx += fx;
      p.vy += fy;
      q.vx -= fx;
      q.vy -= fy;
    }

    // Centering + integrate
    for (const p of arr) {
      if (dragRef.current === p.id) {
        p.vx = 0;
        p.vy = 0;
        continue;
      }
      p.vx += (W / 2 - p.x) * 0.004;
      p.vy += (H / 2 - p.y) * 0.004;
      p.vx *= 0.85;
      p.vy *= 0.85;
      const mass = p.node.kind === 'hub' ? 1.8 : 1.0;
      p.x += (p.vx / mass) * alpha;
      p.y += (p.vy / mass) * alpha;
    }

    // Collision resolution (run every tick so nodes never overlap)
    for (let iter = 0; iter < 2; iter++) {
      for (let a = 0; a < arr.length; a++) {
        for (let b = a + 1; b < arr.length; b++) {
          const p = arr[a];
          const q = arr[b];
          const pad = (p.node.kind === 'hub' || q.node.kind === 'hub') ? 16 : 8;
          const min = p.r + q.r + pad;
          let dx = p.x - q.x;
          let dy = p.y - q.y;
          let dist = Math.sqrt(dx * dx + dy * dy);
          if (dist === 0) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            dist = 0.01;
          }
          if (dist < min) {
            const push = (min - dist) / 2;
            const ux = dx / dist;
            const uy = dy / dist;
            if (dragRef.current !== p.id) {
              p.x += ux * push;
              p.y += uy * push;
            }
            if (dragRef.current !== q.id) {
              q.x -= ux * push;
              q.y -= uy * push;
            }
          }
        }
      }
    }

    // Soft bounds
    for (const p of arr) {
      p.x = Math.max(p.r + 10, Math.min(W - p.r - 10, p.x));
      p.y = Math.max(p.r + 10, Math.min(H - p.r - 10, p.y));
    }

    alphaRef.current *= 0.992;
    setTick((t) => t + 1);
  }, []);

  const runSim = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    const loop = () => {
      stepOnce();
      if (alphaRef.current > 0.015 || dragRef.current) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        runningRef.current = false;
      }
    };
    rafRef.current = requestAnimationFrame(loop);
  }, [stepOnce]);

  // Seed positions when data changes
  useEffect(() => {
    if (!data) return;
    dataRef.current = data;
    const m = new Map<string, Sim>();
    const hubs = data.nodes.filter((n) => n.kind === 'hub');
    const cases = data.nodes.filter((n) => n.kind === 'case');
    const place = (list: GraphNode[], radius: number) => {
      const n = list.length || 1;
      list.forEach((node, i) => {
        const ang = (i / n) * Math.PI * 2 + (node.kind === 'hub' ? 0 : 0.4);
        m.set(node.id, {
          id: node.id,
          x: W / 2 + Math.cos(ang) * radius + (i % 5) * 4,
          y: H / 2 + Math.sin(ang) * radius + (i % 3) * 4,
          vx: 0,
          vy: 0,
          r: radiusOf(node),
          node,
        });
      });
    };
    place(hubs, 150);
    place(cases, 300);
    simRef.current = m;
    alphaRef.current = 1;
    runSim();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      runningRef.current = false;
    };
  }, [data, runSim]);

  // ── Coordinate mapping (handles viewBox + zoom/pan) ─────────────────────────
  const toGraph = (clientX: number, clientY: number) => {
    const g = gRef.current;
    if (!g) return { x: 0, y: 0 };
    const ctm = g.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const svg = g.ownerSVGElement!;
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  };

  const onNodeDown = (id: string) => (e: React.PointerEvent) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    dragRef.current = id;
    alphaRef.current = Math.max(alphaRef.current, 0.4);
    runSim();
  };

  const onBgDown = (e: React.PointerEvent) => {
    panRef.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
  };

  const onMove = (e: React.PointerEvent) => {
    if (dragRef.current) {
      const p = simRef.current.get(dragRef.current);
      if (p) {
        const { x, y } = toGraph(e.clientX, e.clientY);
        p.x = x;
        p.y = y;
        p.vx = 0;
        p.vy = 0;
      }
      return;
    }
    if (panRef.current) {
      const scale = (gRef.current?.ownerSVGElement?.clientWidth || W) / W;
      setView((v) => ({
        ...v,
        x: panRef.current!.vx + (e.clientX - panRef.current!.x) / scale,
        y: panRef.current!.vy + (e.clientY - panRef.current!.y) / scale,
      }));
    }
  };

  const onUp = () => {
    if (dragRef.current) {
      dragRef.current = null;
      alphaRef.current = Math.max(alphaRef.current, 0.1);
      runSim();
    }
    panRef.current = null;
  };

  const zoom = (factor: number) =>
    setView((v) => ({ ...v, k: Math.max(0.4, Math.min(3, v.k * factor)) }));
  const resetView = () => setView({ k: 1, x: 0, y: 0 });

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    zoom(e.deltaY < 0 ? 1.12 : 0.89);
  };

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

  // ── Render ──────────────────────────────────────────────────────────────────
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const sim = simRef.current;

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto animate-fade-in">
      <PageHeader onRefresh={() => load(threshold)} />

      <div className="mt-6 grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Canvas */}
        <div className="xl:col-span-8 rounded-2xl bg-surface-1 border border-border overflow-hidden relative">
          {/* Control bar */}
          <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between gap-3 pointer-events-none">
            <div className="pointer-events-auto flex items-center gap-3 bg-surface-2/90 backdrop-blur border border-border rounded-xl px-3 py-2 shadow-lg">
              <SlidersHorizontal className="w-4 h-4 text-accent-sky" />
              <div className="text-[11px] text-slate-400 font-medium whitespace-nowrap">
                Link strength ≥ <span className="text-slate-200 font-bold">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0.3}
                max={0.8}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-28 accent-accent-sky cursor-pointer"
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
            <div className="h-[660px] flex items-center justify-center px-8 text-center text-critical text-sm">
              {error}
            </div>
          ) : nodes.length === 0 ? (
            <div className="h-[660px] flex flex-col items-center justify-center text-center text-slate-400 px-8">
              <Network className="w-10 h-10 mb-3 text-slate-600" />
              No links at this strength. Lower the threshold, or seed/upload cases
              from the Worklist.
            </div>
          ) : (
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="w-full h-[660px] touch-none select-none cursor-grab active:cursor-grabbing"
              onPointerDown={onBgDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerLeave={onUp}
              onWheel={onWheel}
            >
              <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="3.5" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <radialGradient id="bgGrad" cx="50%" cy="42%" r="70%">
                  <stop offset="0%" stopColor="#15203a" />
                  <stop offset="100%" stopColor="#0A0F1C" />
                </radialGradient>
              </defs>
              <rect x={0} y={0} width={W} height={H} fill="url(#bgGrad)" />

              <g ref={gRef} transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
                {/* Edges (curved; faint unless incident to hovered node) */}
                {edges.map((e, i) => {
                  const p = sim.get(e.source);
                  const q = sim.get(e.target);
                  if (!p || !q) return null;
                  const on = hover === e.source || hover === e.target;
                  const dim = hover && !on;
                  const mx = (p.x + q.x) / 2;
                  const my = (p.y + q.y) / 2;
                  const off = 0.12;
                  const cx = mx + (q.y - p.y) * off;
                  const cy = my - (q.x - p.x) * off;
                  return (
                    <path
                      key={`e${i}`}
                      d={`M ${p.x} ${p.y} Q ${cx} ${cy} ${q.x} ${q.y}`}
                      fill="none"
                      stroke={on ? tierColor(q.node.tier ?? 'Unknown') : '#3B82F6'}
                      strokeOpacity={dim ? 0.03 : on ? 0.55 : 0.1}
                      strokeWidth={(on ? 1.4 : 0.7) + e.weight * 1.8}
                    />
                  );
                })}

                {/* Nodes */}
                {nodes.map((node) => {
                  const p = sim.get(node.id);
                  if (!p) return null;
                  const color = tierColor(node.tier ?? 'Unknown');
                  const isHub = node.kind === 'hub';
                  const isLit = lit(node.id);
                  const showLabel = isHub || hover === node.id;
                  return (
                    <g
                      key={node.id}
                      transform={`translate(${p.x},${p.y})`}
                      style={{ cursor: isHub ? 'grab' : 'pointer' }}
                      opacity={isLit ? 1 : 0.22}
                      onPointerDown={onNodeDown(node.id)}
                      onMouseEnter={() => setHover(node.id)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => {
                        if (!isHub && dragRef.current === null) router.push(`/case/${node.id}`);
                      }}
                    >
                      {isHub ? (
                        <>
                          <circle r={p.r + 4} fill="none" stroke={color} strokeOpacity={0.4} strokeWidth={1.5} />
                          <circle r={p.r} fill={color} fillOpacity={0.92} filter="url(#glow)" />
                          <circle r={p.r} fill="none" stroke="#0A0F1C" strokeWidth={1.5} />
                        </>
                      ) : (
                        <>
                          {hover === node.id && (
                            <circle r={p.r + 4} fill="none" stroke={color} strokeOpacity={0.6} />
                          )}
                          <circle r={p.r} fill={color} fillOpacity={0.9} stroke="#0A0F1C" strokeWidth={1} />
                        </>
                      )}
                      {showLabel && (
                        <LabelPill
                          text={node.label}
                          y={p.r + 6}
                          hub={isHub}
                        />
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>
          )}

          <div className="absolute bottom-3 left-4 text-[11px] text-slate-500 flex items-center gap-1.5 pointer-events-none">
            <Info className="w-3 h-3" /> drag a hub to rearrange · scroll to zoom · drag background to pan · click a case to open
          </div>
        </div>

        {/* Side panel */}
        <div className="xl:col-span-4 space-y-5">
          <div className="rounded-2xl bg-surface-1 border border-border p-5">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-urgent" />
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Cohort signals</h2>
            </div>
            {data && data.alerts.length > 0 ? (
              <ul className="space-y-2">
                {data.alerts.map((a, i) => {
                  const [name, rest] = a.split(':');
                  return (
                    <li key={i} className="flex items-center gap-2 text-sm bg-surface-2 rounded-lg px-3 py-2 border border-border">
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: tierColor(tierForName(name, data)) }}
                      />
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
              Exploratory descriptive signal over the current worklist — not a clinical
              outbreak-detection claim.
            </p>
          </div>

          <div className="rounded-2xl bg-surface-1 border border-border p-5">
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
                <span className="text-slate-400">Pathology hub — size = cases sharing it</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                <span className="text-slate-400">Case — click to open</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-3 text-center">
              <Stat value={nodes.filter((n) => n.kind === 'case').length} label="Cases" color="text-accent-teal" />
              <Stat value={nodes.filter((n) => n.kind === 'hub').length} label="Hubs" color="text-accent-sky" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function tierForName(name: string, data: InsightsGraphData): string {
  const n = data.nodes.find((x) => x.kind === 'hub' && x.label === name.trim());
  return n?.tier ?? 'Unknown';
}

function LabelPill({ text, y, hub }: { text: string; y: number; hub: boolean }) {
  const w = text.length * (hub ? 6.6 : 6) + 12;
  return (
    <g style={{ pointerEvents: 'none' }}>
      <rect
        x={-w / 2}
        y={y}
        width={w}
        height={hub ? 18 : 16}
        rx={hub ? 9 : 8}
        fill="#0A0F1C"
        fillOpacity={0.78}
        stroke={hub ? '#334155' : 'transparent'}
        strokeWidth={1}
      />
      <text
        x={0}
        y={y + (hub ? 13 : 12)}
        textAnchor="middle"
        fontSize={hub ? 11.5 : 10}
        fontWeight={hub ? 700 : 500}
        fill={hub ? '#E2E8F0' : '#94A3B8'}
      >
        {text}
      </text>
    </g>
  );
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
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
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
          <p className="text-sm text-slate-500">
            How the worklist clusters by pathology — cases linked to shared findings.
          </p>
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
