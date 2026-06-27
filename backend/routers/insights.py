"""Insights router — the Obsidian-style knowledge graph over the worklist.

Thin HTTP wrapper around ``radquant.nodes.insights_graph`` (pure logic), exposing
the case<->pathology-hub graph as JSON for the Next.js force-graph view. The
heavy lifting (node sizing, hub pruning, isolated-node removal) lives in the
node module so it stays testable and shared with the original Streamlit page.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import get_worklist
from backend.schemas import GraphEdgeOut, GraphNodeOut, InsightsGraphOut
from radquant.nodes.insights_graph import build_graph, outbreak_alerts

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/graph", response_model=InsightsGraphOut)
async def graph(
    finding_threshold: float = 0.35,
    min_hub_size: int = 2,
    wl=Depends(get_worklist),
):
    """Return the worklist knowledge graph (nodes, edges, outbreak alerts)."""
    g = build_graph(
        wl,
        finding_threshold=finding_threshold,
        min_hub_size=min_hub_size,
    )
    return InsightsGraphOut(
        nodes=[
            GraphNodeOut(
                id=n.id,
                label=n.label,
                kind=n.kind,
                size=n.size,
                tier=n.tier,
                urgency_score=n.urgency_score,
            )
            for n in g.nodes
        ],
        edges=[
            GraphEdgeOut(source=e.source, target=e.target, weight=e.weight)
            for e in g.edges
        ],
        alerts=outbreak_alerts(g),
        hub_sizes=g.hub_sizes(),
    )
