'use client';

/**
 * Insights Graph — an Obsidian-style knowledge graph over the worklist.
 *
 * Cases and pathology "hubs" are nodes; an edge means a case's classifier
 * cleared the finding threshold for that pathology. Hubs touched by many cases
 * surface as potential cohort signals ("outbreak" alerts). Rendered with a
 * dependency-free force simulation (no react-force-graph / d3) so it builds with
 * the pinned package set. Data comes from /api/insights/graph.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Network, AlertTriangle, RefreshCw, Info } from 'lucide-react';
import { insights, tierColor, InsightsGraphData, GraphNode } from '@/lib/api';

const W = 1200;
const H = 820;
const HUB_PREFIX = 'hub::';

interface Sim {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  node: GraphNode;
}

function radiusOf(n: GraphNode): number {
  return Math.max(5, n.size * (n.kind === 'hub' ? 0.7 : 0.6));
}

export default function InsightsPage() {
  const router = useRouter();
  const [data, setData] = useState<InsightsGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [, setTick] = useState(0); // re-render trigger for the animation frames

  const simRef = useRef<Map<string, Sim>>(new Map());
  const dataRef = useRef<InsightsGraphData | null>(null);
  const dragRef = useRef<string | null>(null);
  const alphaRef = useRef(1);
  const runningRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await insights.graph();
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // ── Force simulation ────────────────────────────────────────────────────────
  const stepOnce = useCallback(() => {
    const d = dataRef.current;
    if (!d) return;
    const sim = simRef.current;
    const arr = Array.from(sim.values());
    const alpha = alphaRef.current;

    // Repulsion (every pair)
    for (let a = 0; a < arr.length; a++) {
      for (let b = a + 1; b < arr.length; b++) {
        const p = arr[a];
        const q = arr[b];
        const dx = p.x - q.x;
        const dy = p.y - q.y;
        const d2 = dx * dx + dy * dy || 0.01;
        const dist = Math.sqrt(d2);
        const rep = 2800 / d2;
        const fx = (dx / dist) * rep;
        const fy = (dy / dist) * rep;
        p.vx += fx;
        p.vy += fy;
        q.vx -= fx;
        q.vy -= fy;
      }
    }

    // Attraction along edges (springs)
    for (const e of d.edges) {
      const p = sim.get(e.source);
      const q = sim.get(e.target);
      if (!p || !q) continue;
      const dx = q.x - p.x;
      const dy = q.y - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const rest = 165;
      const k = 0.02 * (0.5 + e.weight);
      const f = (dist - rest) * k;
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      p.vx += fx;
      p.vy += fy;
      q.vx -= fx;
      q.vy -= fy;
    }

    // Centering + integration
    for (const p of arr) {
      if (dragRef.current === p.id) {
        p.vx = 0;
        p.vy = 0;
        continue;
      }
      p.vx += (W / 2 - p.x) * 0.0022;
      p.vy += (H / 2 - p.y) * 0.0022;
      p.vx *= 0.86;
      p.vy *= 0.86;
      const mass = p.node.kind === 'hub' ? 1.7 : 1.0;
      p.x += (p.vx / mass) * alpha;
      p.y += (p.vy / mass) * alpha;
      p.x = Math.max(40, Math.min(W - 40, p.x));
      p.y = Math.max(40, Math.min(H - 40, p.y));
    }

    alphaRef.current *= 0.99;
    setTick((t) => t + 1);
  }, []);

  const runSim = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    const loop = () => {
      stepOnce();
      if (alphaRef.current > 0.02 || dragRef.current) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        runningRef.current = false;
      }
    };
    rafRef.current = requestAnimationFrame(loop);
  }, [stepOnce]);

  // (Re)seed positions whenever the graph data changes
  useEffect(() => {
    if (!data) return;
    dataRef.current = data;
    const m = new Map<string, Sim>();
    const n = data.nodes.length || 1;
    data.nodes.forEach((node, i) => {
      const ang = (i / n) * Math.PI * 2;
      const r = node.kind === 'hub' ? 130 : 330;
      m.set(node.id, {
        id: node.id,
        x: W / 2 + Math.cos(ang) * r + (i % 7) * 6,
        y: H / 2 + Math.sin(ang) * r + (i % 5) * 6,
        vx: 0,
        vy: 0,
        node,
      });
    });
    simRef.current = m;
    alphaRef.current = 1;
    runSim();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      runningRef.current = false;
    };
  }, [data, runSim]);

  // ── Pointer → SVG coordinate mapping ────────────────────────────────────────
  const toSvg = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  };

  const onPointerDownNode = (id: string) => (e: React.PointerEvent) => {
    e.stopPropagation();
    dragRef.current = id;
    alphaRef.current = Math.max(alphaRef.current, 0.3);
    runSim();
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const p = simRef.current.get(dragRef.current);
    if (!p) return;
    const { x, y } = toSvg(e.clientX, e.clientY);
    p.x = x;
    p.y = y;
    p.vx = 0;
    p.vy = 0;
  };

  const endDrag = () => {
    dragRef.current = null;
    alphaRef.current = Math.max(alphaRef.current, 0.15);
    runSim();
  };

  // ── Adjacency for hover highlighting ────────────────────────────────────────
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

  const isLit = (id: string) =>
    !hover || hover === id || adjacency.get(hover)?.has(id);

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-screen text-slate-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-3" /> Building knowledge graph…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-8">
        <PageHeader onRefresh={load} />
        <div className="mt-6 p-4 rounded-xl bg-critical/10 border border-critical/20 text-critical text-sm">
          Failed to load graph: {error}
        </div>
      </div>
    );
  }

  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const sim = simRef.current;

  return (
    <div className="p-6 lg:p-8 max-w-[1600px] mx-auto animate-fade-in">
      <PageHeader onRefresh={load} />

      {nodes.length === 0 ? (
        <div className="mt-6 p-10 rounded-2xl bg-surface-1 border border-border text-center text-slate-400">
          <Network className="w-10 h-10 mx-auto mb-3 text-slate-600" />
          No connected findings yet. Seed or upload cases from the Worklist, then
          come back to see how they cluster by pathology.
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Graph canvas */}
          <div className="xl:col-span-8 rounded-2xl bg-surface-1 border border-border overflow-hidden relative">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${W} ${H}`}
              className="w-full h-[640px] touch-none select-none"
              onPointerMove={onPointerMove}
              onPointerUp={endDrag}
              onPointerLeave={endDrag}
            >
              {/* Edges */}
              {edges.map((e, i) => {
                const p = sim.get(e.source);
                const q = sim.get(e.target);
                if (!p || !q) return null;
                const lit = isLit(e.source) && isLit(e.target);
                return (
                  <line
                    key={`e${i}`}
                    x1={p.x}
                    y1={p.y}
                    x2={q.x}
                    y2={q.y}
                    stroke={lit ? '#3B82F6' : '#334155'}
                    strokeOpacity={lit ? 0.35 + e.weight * 0.4 : 0.08}
                    strokeWidth={0.8 + e.weight * 2.4}
                  />
                );
              })}

              {/* Nodes */}
              {nodes.map((node) => {
                const p = sim.get(node.id);
                if (!p) return null;
                const r = radiusOf(node);
                const color = tierColor(node.tier ?? 'Unknown');
                const lit = isLit(node.id);
                const isHub = node.kind === 'hub';
                return (
                  <g
                    key={node.id}
                    transform={`translate(${p.x},${p.y})`}
                    style={{ cursor: isHub ? 'grab' : 'pointer' }}
                    opacity={lit ? 1 : 0.25}
                    onPointerDown={onPointerDownNode(node.id)}
                    onMouseEnter={() => setHover(node.id)}
                    onMouseLeave={() => setHover(null)}
                    onClick={() => {
                      if (!isHub) router.push(`/case/${node.id}`);
                    }}
                  >
                    {isHub && (
                      <circle r={r + 5} fill="none" stroke={color} strokeOpacity={0.35} />
                    )}
                    <circle
                      r={r}
                      fill={color}
                      fillOpacity={isHub ? 0.9 : 0.85}
                      stroke={isHub ? '#0A0F1C' : color}
                      strokeWidth={isHub ? 2 : 1}
                    />
                    {(isHub || hover === node.id) && (
                      <text
                        x={0}
                        y={r + 13}
                        textAnchor="middle"
                        fontSize={isHub ? 13 : 11}
                        fontWeight={isHub ? 700 : 500}
                        fill={isHub ? '#E2E8F0' : '#94A3B8'}
                        style={{ pointerEvents: 'none' }}
                      >
                        {node.label}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>

            <div className="absolute bottom-3 left-4 text-[11px] text-slate-500 flex items-center gap-1.5">
              <Info className="w-3 h-3" /> Drag hubs to rearrange · hover to trace links · click a case to open it
            </div>
          </div>

          {/* Side panel */}
          <div className="xl:col-span-4 space-y-5">
            {/* Outbreak alerts */}
            <div className="rounded-2xl bg-surface-1 border border-border p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-urgent" />
                <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                  Cohort signals
                </h2>
              </div>
              {data && data.alerts.length > 0 ? (
                <ul className="space-y-2">
                  {data.alerts.map((a, i) => (
                    <li
                      key={i}
                      className="text-sm text-slate-300 bg-surface-2 rounded-lg px-3 py-2 border border-border"
                    >
                      {a}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No pathology is shared by 3+ cases.</p>
              )}
              <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
                Exploratory descriptive signal over the current worklist — not a
                clinical outbreak-detection claim.
              </p>
            </div>

            {/* Legend + stats */}
            <div className="rounded-2xl bg-surface-1 border border-border p-5">
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-3">
                Legend
              </h2>
              <div className="space-y-2 text-sm">
                {[
                  ['Critical', 'Critical'],
                  ['Urgent', 'Urgent'],
                  ['Important', 'Important'],
                  ['Chronic', 'Chronic'],
                ].map(([label, tier]) => (
                  <div key={tier} className="flex items-center gap-2.5">
                    <span
                      className="w-3 h-3 rounded-full"
                      style={{ background: tierColor(tier) }}
                    />
                    <span className="text-slate-400">{label}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2.5 pt-1">
                  <span className="w-4 h-4 rounded-full border-2 border-slate-500" />
                  <span className="text-slate-400">Pathology hub (ringed, labelled)</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
                  <span className="text-slate-400">Case (click to open)</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-3 text-center">
                <div>
                  <div className="text-2xl font-bold text-accent-teal">
                    {nodes.filter((n) => n.kind === 'case').length}
                  </div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Cases</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-accent-sky">
                    {nodes.filter((n) => n.kind === 'hub').length}
                  </div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Hubs</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
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
