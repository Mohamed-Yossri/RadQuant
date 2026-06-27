"""Insights Graph page — Obsidian-style network view of cases linked by shared
AI findings, with pathology "hub" nodes (e.g. a Pneumonia hub) at the center
of every cluster.

Fix (Phase 7.1): Replaced default vis.js physics-only positioning with a
NetworkX-computed radial layout. Hubs sit in an inner ring; case nodes are
pushed to an outer ring anchored near their strongest connected hub.
This eliminates the "gravity collapse" where all nodes pile into one blob.

Fix (Phase 7.2):
- physics=False: static layout keeps nodes in their pre-computed radial
  positions instead of collapsing back to centre.
- Edge width reduced (max 1.8 px) to avoid spider-web overcrowding.
- Controls relabelled with Arabic/bilingual help text so purpose is clear.
- Isolated case nodes (no surviving edges) are removed in the node layer —
  see insights_graph_node.py for that logic.

Run standalone:  streamlit run radquant/ui/insights_graph.py
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Tuple

import streamlit as st

from radquant.nodes.insights_graph import build_graph, outbreak_alerts, HUB_PREFIX
from radquant.ui import theme
from radquant.worklist import Worklist

try:
    from streamlit_agraph import Config, Edge, Node, agraph
    _AGRAPH_OK = True
except ImportError:
    _AGRAPH_OK = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _node_color(node) -> str:
    if node.kind == "hub":
        return theme.TIER_COLOR.get(node.tier, theme.ACCENT2)
    return theme.TIER_COLOR.get(node.tier, theme.MUTED)


def _radial_layout(
    graph_data,
    hub_radius: float = 220,
    case_radius: float = 480,
) -> Dict[str, Tuple[float, float]]:
    """Pre-compute (x, y) positions so vis.js starts from a clean layout.

    Strategy
    --------
    • Hub nodes → arranged evenly on an inner circle of radius `hub_radius`.
    • Case nodes → projected onto an outer circle of radius `case_radius`,
      anchored toward the centroid of their connected hubs' positions.
      Cases that connect to many hubs land between them; cases with a single
      hub land almost directly behind it.

    This breaks the "gravity collapse": instead of all nodes racing toward the
    same dense centre, they start spread across ~960 × 960 px and the physics
    engine only has to fine-tune.
    """
    hub_nodes = [n for n in graph_data.nodes if n.kind == "hub"]
    case_nodes = [n for n in graph_data.nodes if n.kind == "case"]

    pos: Dict[str, Tuple[float, float]] = {}

    # ── 1. Hubs on inner ring ──────────────────────────────────────────────
    n_hubs = len(hub_nodes)
    for i, hub in enumerate(hub_nodes):
        angle = 2 * math.pi * i / max(n_hubs, 1) - math.pi / 2  # start at top
        pos[hub.id] = (hub_radius * math.cos(angle), hub_radius * math.sin(angle))

    # ── 2. Build case → hub adjacency ─────────────────────────────────────
    case_hub_map: Dict[str, list] = defaultdict(list)
    for edge in graph_data.edges:
        if edge.target.startswith(HUB_PREFIX):
            case_hub_map[edge.source].append(edge.target)

    # ── 3. Cases on outer ring anchored to their hub cluster ───────────────
    hub_pos_set = {n.id for n in hub_nodes}
    for case in case_nodes:
        connected = [h for h in case_hub_map.get(case.id, []) if h in hub_pos_set]
        if not connected:
            # Orphan case — place at top
            pos[case.id] = (0.0, case_radius)
            continue

        # Average position of connected hubs → direction vector
        avg_x = sum(pos[h][0] for h in connected) / len(connected)
        avg_y = sum(pos[h][1] for h in connected) / len(connected)
        dist = math.sqrt(avg_x ** 2 + avg_y ** 2) or 1.0
        pos[case.id] = (
            case_radius * avg_x / dist,
            case_radius * avg_y / dist,
        )

    return pos


# ── page ─────────────────────────────────────────────────────────────────────

def page() -> None:
    theme.app_header("INSIGHTS GRAPH")
    theme.disclaimer(
        "Exploratory view only — clusters reflect AI-classifier output, not a "
        "validated epidemiological signal. Research/assistive demo — not for "
        "clinical use."
    )

    if not _AGRAPH_OK:
        st.error(
            "Missing dependency: run `pip install streamlit-agraph` to "
            "enable the graph view."
        )
        return

    wl = Worklist.load()
    if len(wl) == 0:
        st.info("Worklist is empty — seed some cases from the Worklist page first.")
        return

    # ── controls ─────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([1, 1, 1])
    finding_threshold = c1.slider(
        "AI Confidence Filter",
        0.0, 1.0, 0.35, 0.05,
        help=(
            "اعرض الـ findings اللي نسبة ثقة الـ AI فيها أعلى من الرقم ده.\n\n"
            "**منخفض (0.2–0.4):** جراف كثيف — بيشوف حتى الـ findings الضعيفة.\n"
            "**متوسط (0.4–0.6):** توازن مقترح.\n"
            "**عالي (0.6+):** بس الـ findings القوية جداً — جراف أبسط وأوضح."
        ),
    )
    min_hub_size = c2.slider(
        "Minimum cluster size",
        1, 5, 2,
        help=(
            "اخفي الـ pathology hubs اللي عدد الحالات فيها أقل من الرقم ده.\n\n"
            "**1:** اعرض كل الـ hubs حتى اللي فيها حالة واحدة.\n"
            "**2–3 (مقترح):** اخفي الـ hubs الصغيرة وفضل بس الـ clusters المهمة.\n"
            "**4–5:** بس الـ clusters الكبيرة جداً — جراف نظيف لكن ممكن يفقد تفاصيل."
        ),
    )
    direct_case_edges = c3.toggle(
        "Show case-to-case links",
        value=False,
        help=(
            "لما تفعّلها: بيضيف خطوط مباشرة بين الحالات اللي بتشترك في نفس الـ finding.\n"
            "بيدي شكل أكثف شبه Obsidian، لكن ممكن يعمل ازدحام في الجراف الكبير."
        ),
    )

    graph = build_graph(
        wl,
        finding_threshold=finding_threshold,
        direct_case_edges=direct_case_edges,
        min_hub_size=min_hub_size,
    )

    # ── outbreak alerts ───────────────────────────────────────────────────────
    alerts = outbreak_alerts(graph, threshold=3)
    if alerts:
        st.warning("**Cluster watch** — " + " · ".join(alerts))

    # ── layout pre-computation ────────────────────────────────────────────────
    # Scale hub/case radii based on total node count so large worklists don't
    # cramp. Phase 7.2: base radii increased (280/580 vs old 220/480) so nodes
    # breathe more even at small counts. Scale kicks in earlier (n/15 vs n/20).
    n = len(graph.nodes)
    scale = max(1.0, n / 15)
    pos = _radial_layout(graph, hub_radius=280 * scale, case_radius=580 * scale)

    # ── build agraph primitives ───────────────────────────────────────────────
    nodes = []
    for n_obj in graph.nodes:
        x, y = pos.get(n_obj.id, (0.0, 0.0))
        nodes.append(
            Node(
                id=n_obj.id,
                label=n_obj.label,
                # ↓ smaller sizes: hub max was 66, now capped at ~38; cases ~20
                size=n_obj.size * 0.55,
                color=_node_color(n_obj),
                shape="dot" if n_obj.kind == "case" else "diamond",
                x=x,
                y=y,
            )
        )

    edges = [
        Edge(
            source=e.source,
            target=e.target,
            # Phase 7.2: much thinner lines — max now 1.8 px (was 2.5 px).
            # Avoids the "thick spider web" effect when many cases share a hub.
            width=0.4 + e.weight * 1.4,
            color=theme.LINE,
        )
        for e in graph.edges
    ]

    # ── vis.js config ─────────────────────────────────────────────────────────
    # Phase 7.2: physics disabled — the pre-computed radial layout is already
    # clean, and the spring physics was pulling everything back into a central
    # blob (gravity collapse). Static layout = nodes stay where we put them.
    config = Config(
        width="100%",
        height=680,
        directed=False,
        physics=False,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor=theme.ACCENT,
        collapsible=False,
        node={"labelProperty": "label"},
        link={"labelProperty": "label", "renderLabel": False},
    )

    clicked_id = agraph(nodes=nodes, edges=edges, config=config)

    # ── click-to-inspect ──────────────────────────────────────────────────────
    if clicked_id and not clicked_id.startswith(HUB_PREFIX):
        case = wl.get(clicked_id)
        if case:
            st.divider()
            st.subheader(f"Case {case.case_id}")
            for pathology, prob in case.top(5):
                st.progress(min(prob, 1.0), text=f"{pathology} — {prob:.0%}")
            if st.button("Open in Case view", type="primary"):
                st.session_state["selected_case_id"] = case.case_id
                st.switch_page(st.session_state["_pages"]["case"])

    # ── legend + isolated-case notice ────────────────────────────────────────
    all_case_ids = {c.case_id for c in wl.sorted()}
    shown_case_ids = {n.id for n in graph.nodes if n.kind == "case"}
    hidden_count = len(all_case_ids - shown_case_ids)
    if hidden_count:
        st.caption(
            f"ℹ️ {hidden_count} case(s) not shown — all their AI findings are below "
            f"the current confidence filter ({finding_threshold:.0%}) or belong to "
            f"clusters smaller than {min_hub_size}. Lower the filters to include them."
        )

    with st.expander("Legend", expanded=False):
        st.markdown(
            "**◆ Diamond** = pathology hub (shared AI finding)  \n"
            "**● Circle** = individual case — size reflects urgency score  \n"
            "**Line thickness** = AI confidence for that finding  \n"
            "**Color** = urgency tier (🟢 low → 🟡 medium → 🟠 high → 🔴 critical)  \n\n"
            "Cases that cluster tightly share many AI findings above the confidence filter.  \n"
            "Cases with no findings above the filter are hidden (see notice above if any)."
        )


if __name__ == "__main__":
    st.set_page_config(page_title="RadQuant · Insights Graph", layout="wide")
    theme.inject_css()
    page()
