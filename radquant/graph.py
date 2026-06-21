"""RadQuant LangGraph state machine (Phase 7).

Wires every node into one graph over CaseState:

    ingest → classify → triage → visualize → draft → review
    review → qc → END          (default: finalize)
    review → draft             (if action == "regenerate")

`review` is a human-in-the-loop checkpoint: the compiled graph interrupts BEFORE
it so the radiologist can edit the draft in the UI, then resumes. `explain` is a
side-call (not on the main path) available from any state with report text.
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from radquant.state import CaseState
from radquant.nodes.classify import classify
from radquant.nodes.triage import triage
from radquant.nodes.visualize import visualize
from radquant.nodes.draft import draft
from radquant.nodes.qc import qc

DICOM_EXTS = (".dcm", ".dicom")


def ingest(state: CaseState) -> dict:
    """Load the image; convert DICOM → PNG (and capture metadata) if needed."""
    path = state["image_path"]
    if path.lower().endswith(DICOM_EXTS):
        from radquant.foundation import DicomProcessorTool

        out, meta = DicomProcessorTool(temp_dir="temp")._run(path)
        if "image_path" in out:
            return {"image_path": out["image_path"], "dicom_metadata": meta}
    return {"dicom_metadata": {}}


def review(state: CaseState) -> dict:
    """Human checkpoint. If the radiologist supplied no edits, fold the current
    draft into ``final_report`` so QC has something to check."""
    if state.get("final_report"):
        return {}
    f = state.get("draft_findings", "")
    i = state.get("draft_impression", "")
    return {"final_report": f"FINDINGS: {f}\n\nIMPRESSION: {i}".strip()}


def route_after_review(state: CaseState) -> str:
    """Regenerate the draft, or proceed to omission QC."""
    return "draft" if state.get("action") == "regenerate" else "qc"


def build_graph(checkpointer: Optional[object] = None, interrupt: bool = True):
    """Compile the full state machine.

    Args:
        checkpointer: state persistence (defaults to in-memory MemorySaver).
        interrupt: if True, pause before ``review`` for human edits.
    """
    g = StateGraph(CaseState)
    for name, fn in [
        ("ingest", ingest), ("classify", classify), ("triage", triage),
        ("visualize", visualize), ("draft", draft), ("review", review), ("qc", qc),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "classify")
    g.add_edge("classify", "triage")
    g.add_edge("triage", "visualize")
    g.add_edge("visualize", "draft")
    g.add_edge("draft", "review")
    g.add_conditional_edges("review", route_after_review, {"draft": "draft", "qc": "qc"})
    g.add_edge("qc", END)

    kwargs = {"interrupt_before": ["review"]} if interrupt else {}
    return g.compile(checkpointer=checkpointer or MemorySaver(), **kwargs)


# --------------------------------------------------------------------------- #
# Imperative helpers the UI uses to drive the interrupting graph.
# --------------------------------------------------------------------------- #
def run_to_review(image_path: str, case_id: str = "case", thread_id: Optional[str] = None):
    """Run ingest→…→draft and pause at the review checkpoint.

    Returns (graph, thread_id, state) where ``state`` holds findings, urgency,
    heatmap_path, and the draft sections.
    """
    graph = build_graph(interrupt=True)
    tid = thread_id or case_id
    cfg = {"configurable": {"thread_id": tid}}
    graph.invoke({"case_id": case_id, "image_path": image_path}, cfg)
    return graph, tid, graph.get_state(cfg).values


def resume_review(graph, thread_id: str, action: str = "finalize",
                  edits: Optional[dict] = None) -> dict:
    """Resume from review. ``action`` 'finalize' → qc, 'regenerate' → re-draft.

    ``edits`` may carry a radiologist-edited ``final_report``.
    """
    cfg = {"configurable": {"thread_id": thread_id}}
    update = {"action": action}
    if edits:
        update.update(edits)
    graph.update_state(cfg, update)
    graph.invoke(None, cfg)
    return graph.get_state(cfg).values
