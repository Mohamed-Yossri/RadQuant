"""`insights_graph` — builds an Obsidian-style knowledge graph over the worklist.

Pure logic, no Streamlit/UI imports here (keeps it testable + reusable), mirroring
the separation already used by `triage.py` (logic) vs `ui/worklist.py` (rendering).

Graph model
-----------
- One node per `Case` ("case node").
- One node per pathology that appears above `finding_threshold` in at least one
  case ("hub node") — this is the "بؤرة Pneumonia" the feature spec describes.
- Edge: case -> hub, whenever that case's probability for that pathology clears
  `finding_threshold`. Edge weight = the probability itself (drives line
  thickness in the UI).
- Optional case -> case edges are *derived*, not stored: two cases sharing a hub
  are already transitively connected through it, so we don't duplicate edges
  unless `direct_case_edges=True` is requested (denser, noisier graph).

Size calibration (Phase 7.1 fix)
----------------------------------
Original sizes were too large (hub max = 66, case max = 28) which caused nodes
to physically overlap even after layout. New ranges:
  - Case nodes : 8 … 20  (urgency_score 0→1 maps to +12)
  - Hub nodes  : 12 … 36  (member count 1→12 maps to +24, capped)
The UI layer scales these by 0.55 so rendered sizes are ~5 … 20 px — readable
without crowding.

Fix (Phase 7.2)
---------------
- Isolated case nodes (no surviving edges after hub pruning) are now removed
  from the graph instead of floating disconnected in a corner.
- Default finding_threshold lowered to 0.35 so borderline cases aren't silently
  dropped from the graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from radquant.nodes.triage import tier_of
from radquant.worklist import Case, Worklist

HUB_PREFIX = "hub::"


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str           # "case" | "hub"
    size: float
    color: Optional[str] = None
    tier: Optional[str] = None         # only for case nodes (top finding's tier)
    urgency_score: Optional[float] = None


@dataclass
class GraphEdge:
    source: str
    target: str
    weight: float


@dataclass
class InsightsGraph:
    nodes: List[GraphNode]
    edges: List[GraphEdge]

    def hub_sizes(self) -> Dict[str, int]:
        """How many cases touch each hub — used to flag potential 'outbreaks'."""
        counts: Dict[str, int] = {}
        for e in self.edges:
            if e.target.startswith(HUB_PREFIX):
                key = e.target[len(HUB_PREFIX):]
                counts[key] = counts.get(key, 0) + 1
        return counts


def build_graph(
    worklist: Worklist,
    finding_threshold: float = 0.35,
    direct_case_edges: bool = False,
    min_hub_size: int = 2,
) -> InsightsGraph:
    """Build the case<->pathology-hub graph from a Worklist's findings.

    Parameters
    ----------
    finding_threshold : float
        A finding only "counts" (becomes an edge) above this probability.
        Lowered from 0.50 → 0.35 so borderline cases aren't silently excluded.
    direct_case_edges : bool
        Also add case<->case edges when two cases share a hub (visually
        denser; Obsidian's "linked mentions" feel). Off by default since hub
        nodes already make the relationship visible.
    min_hub_size : int
        Drop hubs touched by fewer than this many cases (decluttering).
        Raised from 1 → 2 so singleton hubs don't clutter the graph.
    """
    cases = worklist.sorted()
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    hub_members: Dict[str, List[str]] = {}

    for case in cases:
        top = case.top(1)
        top_pathology = top[0][0] if top else None

        # Case node — size range 8…20 (was 10…28)
        nodes.append(GraphNode(
            id=case.case_id,
            label=case.case_id,
            kind="case",
            size=8 + case.urgency_score * 12,
            tier=tier_of(top_pathology) if top_pathology else "Unknown",
            urgency_score=case.urgency_score,
        ))

        for pathology, prob in case.findings.items():
            if prob < finding_threshold:
                continue
            hub_id = f"{HUB_PREFIX}{pathology}"
            hub_members.setdefault(pathology, []).append(case.case_id)
            edges.append(GraphEdge(source=case.case_id, target=hub_id, weight=prob))

    for pathology, members in hub_members.items():
        if len(members) < min_hub_size:
            # Drop the hub node and any edges that point at it.
            edges = [e for e in edges if e.target != f"{HUB_PREFIX}{pathology}"]
            continue

        # Hub node — size range 12…36 (was 18…66)
        # Capped at 12 members so even "Infiltration (11 cases)" stays readable.
        nodes.append(GraphNode(
            id=f"{HUB_PREFIX}{pathology}",
            label=pathology,
            kind="hub",
            size=12 + min(len(members), 12) * 2,
            tier=tier_of(pathology),
        ))

    if direct_case_edges:
        for members in hub_members.values():
            if len(members) < 2:
                continue
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    edges.append(
                        GraphEdge(source=members[i], target=members[j], weight=0.3)
                    )

    # ── Phase 7.2 fix: remove isolated case nodes ─────────────────────────────
    # After hub pruning, some cases may have zero surviving edges (all their
    # findings were below threshold OR all their hubs were dropped by
    # min_hub_size). These cases float disconnected in a corner and confuse
    # readers. We remove them from the node list so only connected cases appear.
    # The worklist count is unaffected — this is display-only filtering.
    connected_case_ids = {
        e.source for e in edges if not e.source.startswith(HUB_PREFIX)
    }
    nodes = [
        n for n in nodes
        if n.kind == "hub" or n.id in connected_case_ids
    ]

    return InsightsGraph(nodes=nodes, edges=edges)


def outbreak_alerts(graph: InsightsGraph, threshold: int = 3) -> List[str]:
    """Plain-language flags for hubs touched by `threshold`+ cases.

    Deliberately framed as an exploratory/descriptive signal, not a clinical
    outbreak-detection claim — see the disclaimer rendered alongside the graph.
    """
    return [
        f"{pathology}: {n} cases share this finding"
        for pathology, n in sorted(
            graph.hub_sizes().items(), key=lambda kv: -kv[1]
        )
        if n >= threshold
    ]
