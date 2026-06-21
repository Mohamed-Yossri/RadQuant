"""Streamlit case view — image (+ Grad-CAM toggle) and editable draft report.

Run standalone:  streamlit run radcopilot/ui/case_view.py
(Phase 7 wires this into the multi-page app and the regenerate/QC loop.)
"""

from __future__ import annotations

import streamlit as st

from radcopilot.worklist import Worklist
from radcopilot.nodes.classify import classify_image
from radcopilot.nodes.draft import draft_report
from radcopilot.nodes.visualize import gradcam_overlay

DISCLAIMER = ("⚠️ Research / assistive demo — **not for clinical use**. "
              "Draft is machine-generated and must be reviewed by a radiologist.")


def render() -> None:
    st.set_page_config(page_title="RadQuant — Case", layout="wide")
    st.title("🩻 Case view")
    st.caption(DISCLAIMER)

    wl = Worklist.load()
    if len(wl) == 0:
        st.info("Worklist is empty — run scripts/phase3_check.py to populate it.")
        return

    cases = wl.sorted(descending=True)
    labels = [f"{c.case_id}  (urgency {c.urgency_score:.2f})" for c in cases]
    pick = st.selectbox("Case", range(len(cases)), format_func=lambda i: labels[i])
    case = cases[pick]

    if st.button("Generate draft + heatmap", type="primary"):
        with st.spinner("Classifying, drafting, and computing Grad-CAM..."):
            findings = case.findings or classify_image(case.image_path)
            f_text, i_text, _ = draft_report(case.image_path, findings)
            heat_path, top = gradcam_overlay(case.image_path, findings=findings)
        st.session_state[case.case_id] = {
            "findings": f_text, "impression": i_text,
            "heatmap": heat_path, "top": top,
        }

    state = st.session_state.get(case.case_id)
    left, right = st.columns(2)
    with left:
        show_heat = st.toggle("Show Grad-CAM overlay", value=False)
        if state and show_heat:
            st.image(state["heatmap"], caption=f"Grad-CAM: {state['top']}",
                     use_container_width=True)
        else:
            st.image(case.image_path, caption=case.case_id, use_container_width=True)
    with right:
        st.subheader("Draft report (editable)")
        st.text_area("FINDINGS", value=(state or {}).get("findings", ""), height=200,
                     key=f"f_{case.case_id}")
        st.text_area("IMPRESSION", value=(state or {}).get("impression", ""), height=120,
                     key=f"i_{case.case_id}")


if __name__ == "__main__":
    render()
