#!/usr/bin/env python3
"""Phase 7 end-to-end: drive the real compiled LangGraph through a full case.

ingest → classify → triage → visualize → draft → [interrupt: review] →
(finalize) → qc → END. Then exercises the explain side-call.

Run: python scripts/phase7_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.data import sample
from radquant.graph import run_to_review, resume_review
from radquant.nodes.explain import explain_report


def main() -> None:
    img = str(sample(1)[0])
    print(f"image: {img}")

    # Run to the human-review checkpoint.
    graph, tid, state = run_to_review(img, case_id="case-demo")
    print("\n[paused at review] keys:", sorted(state))
    assert len(state["findings"]) == 18, "classify did not populate 18 findings"
    assert state["urgency_score"] >= 0, "triage did not score"
    assert Path(state["heatmap_path"]).is_file(), "visualize did not write a heatmap"
    assert state["draft_findings"], "draft FINDINGS empty"
    print(f"  urgency={state['urgency_score']:.2f}  heatmap={state['heatmap_path']}")
    print(f"  draft FINDINGS: {state['draft_findings'][:90]}...")

    # Radiologist finalizes with an edited report that omits a high-confidence finding.
    edited = ("FINDINGS: The lungs are clear. The heart size is normal.\n\n"
              "IMPRESSION: No acute cardiopulmonary process.")
    final = resume_review(graph, tid, action="finalize",
                          edits={"final_report": edited})
    print("\n[finalized] omissions:",
          [o["finding"] for o in final.get("omissions", [])] or "none")
    assert "omissions" in final, "qc node did not run"

    # Side-call: explain the final report in plain language.
    plain = explain_report(final["final_report"])
    assert plain.strip()
    print("\n[explain side-call] ->", plain[:120], "...")

    print("\n\033[32m✓ Phase 7 check passed — full LangGraph state machine runs "
          "end-to-end (with human-in-the-loop review + QC + explain).\033[0m")
    print("  App: streamlit run radquant/ui/app.py")


if __name__ == "__main__":
    main()
