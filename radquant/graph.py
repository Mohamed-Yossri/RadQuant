"""
radquant/graph.py — Full LangGraph state machine (Phases 7 + 10).

Pipeline:
  ingest → classify → compare → triage → visualize → draft → review
                                                               │
                                          ┌────────────────────┤
                                     (QC end)           (Regenerate)
                                          │                    │
                                         END              draft ↩
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from radquant.state import CaseState
from radquant.nodes.classify import classify_node
from radquant.nodes.compare import comparison_node
from radquant.nodes.triage import triage_node
from radquant.nodes.visualize import visualize_node
from radquant.nodes.draft import draft_node
from radquant.nodes.qc import qc_node
from radquant.nodes.explain import explain_node


def _route_after_review(state: CaseState) -> str:
    edits = state.get("radiologist_edits") or {}
    return "draft" if edits.get("regenerate") else "qc"


def build_graph() -> StateGraph:
    builder = StateGraph(CaseState)

    builder.add_node("classify",  classify_node)
    builder.add_node("compare",   comparison_node)
    builder.add_node("triage",    triage_node)
    builder.add_node("visualize", visualize_node)
    builder.add_node("draft",     draft_node)
    builder.add_node("review",    lambda s: s)   # UI interrupt placeholder
    builder.add_node("qc",        qc_node)
    builder.add_node("explain",   explain_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify",  "compare")
    builder.add_edge("compare",   "triage")
    builder.add_edge("triage",    "visualize")
    builder.add_edge("visualize", "draft")
    builder.add_edge("draft",     "review")
    builder.add_conditional_edges(
        "review",
        _route_after_review,
        {"draft": "draft", "qc": "qc"},
    )
    builder.add_edge("qc",     END)
    builder.add_edge("explain", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory, interrupt_before=["review"])


def run_to_review(graph, state: CaseState, thread_id: str = "default") -> CaseState:
    """Run classify→compare→triage→visualize→draft, pause before review."""
    config = {"configurable": {"thread_id": thread_id}}
    final = state
    for event in graph.stream(state, config=config):
        final = event
    return final


def resume_review(graph, edits: dict, thread_id: str = "default") -> CaseState:
    """Resume after radiologist edits."""
    config = {"configurable": {"thread_id": thread_id}}
    graph.update_state(config, {"radiologist_edits": edits})
    final = {}
    for event in graph.stream(None, config=config):
        final = event
    return final
