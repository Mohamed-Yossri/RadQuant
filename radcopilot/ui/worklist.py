"""Streamlit worklist page — cases sorted by urgency, descending.

Run standalone:  streamlit run radcopilot/ui/worklist.py
(Phase 7 wires this into the multi-page app.)
"""

from __future__ import annotations

import streamlit as st

from radcopilot.worklist import Worklist
from radcopilot.nodes.triage import tier_of

DISCLAIMER = ("⚠️ Research / assistive demo — **not for clinical use**. "
              "Urgency weights are literature-anchored defaults, not site-validated.")


def render() -> None:
    st.set_page_config(page_title="RadQuant — Worklist", layout="wide")
    st.title("🩻 RadQuant Worklist")
    st.caption(DISCLAIMER)

    wl = Worklist.load()
    if len(wl) == 0:
        st.info("No cases yet. Ingest cases through the classify → triage pipeline "
                "(see scripts/phase3_check.py) to populate the worklist.")
        return

    rows = []
    for c in wl.sorted(descending=True):
        top = c.top(3)
        rows.append({
            "case_id": c.case_id,
            "urgency": round(c.urgency_score, 3),
            "top findings": ", ".join(f"{k} {v:.2f} [{tier_of(k)}]" for k, v in top),
            "status": c.status,
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.metric("Cases in worklist", len(wl))


if __name__ == "__main__":
    render()
