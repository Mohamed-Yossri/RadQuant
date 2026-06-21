"""Case view — per-study workflow: draft, Grad-CAM, edit, omission QC, finalize.

Run standalone:  streamlit run radquant/ui/case_view.py
"""

from __future__ import annotations

import streamlit as st

from radquant.worklist import Worklist
from radquant.nodes.classify import classify_image
from radquant.nodes.draft import draft_report
from radquant.nodes.visualize import gradcam_overlay
from radquant.nodes.qc import find_omissions
from radquant.nodes.explain import explain_report
from radquant.nodes.triage import tier_of
from radquant.ui import theme
from radquant.ui.qc_panel import render_omissions_panel


def _compose_report(findings_txt: str, impression_txt: str) -> str:
    return f"FINDINGS: {findings_txt}\n\nIMPRESSION: {impression_txt}".strip()


def page() -> None:
    theme.app_header("CASE")
    wl = Worklist.load()
    if len(wl) == 0:
        st.info("Worklist is empty — seed it from the Worklist page first.")
        return

    cases = wl.sorted(descending=True)
    ids = [c.case_id for c in cases]
    sel = st.session_state.get("selected_case")
    idx = ids.index(sel) if sel in ids else 0
    cid = st.selectbox("Study", ids, index=idx,
                       format_func=lambda x: f"{x}  ·  urgency {wl.get(x).urgency_score:.2f}")
    case = wl.get(cid)
    st.session_state["selected_case"] = cid

    head = (theme.urgency_pill(case.urgency_score) + "  " +
            " ".join(theme.tier_badge(f"{k} {v:.2f}", tier_of(k)) for k, v in case.top(3)))
    st.markdown(head, unsafe_allow_html=True)

    key = f"art_{cid}"
    if st.button("⚙️ Generate draft + Grad-CAM", type="primary"):
        with st.spinner("Classifying, drafting (MedGemma), and computing Grad-CAM..."):
            findings = case.findings or classify_image(case.image_path)
            f_text, i_text, _ = draft_report(case.image_path, findings)
            heat, top = gradcam_overlay(case.image_path, findings=findings)
        st.session_state[key] = {"findings": findings, "f": f_text, "i": i_text,
                                 "heat": heat, "top": top}

    art = st.session_state.get(key)

    left, right = st.columns([1, 1])
    with left:
        show_heat = st.toggle("Grad-CAM overlay", value=bool(art))
        if art and show_heat:
            st.image(art["heat"], caption=f"Grad-CAM · {art['top']}",
                     use_container_width=True)
        else:
            st.image(case.image_path, caption=cid, use_container_width=True)
    with right:
        st.markdown("**Draft report** (editable)")
        f_val = st.text_area("FINDINGS", value=(art or {}).get("f", ""), height=170,
                             key=f"f_{cid}")
        i_val = st.text_area("IMPRESSION", value=(art or {}).get("i", ""), height=110,
                             key=f"i_{cid}")

    if not art:
        st.caption("Generate a draft to enable QC, finalize, and the explainer.")
        return

    report = _compose_report(f_val, i_val)

    st.divider()
    a1, a2, a3 = st.columns(3)
    if a1.button("🔁 Regenerate draft", use_container_width=True):
        with st.spinner("Regenerating..."):
            f_text, i_text, _ = draft_report(case.image_path, art["findings"])
        st.session_state[key].update({"f": f_text, "i": i_text})
        st.rerun()
    if a2.button("🛡️ Run omission QC", use_container_width=True):
        with st.spinner("Checking for omitted high-confidence findings..."):
            st.session_state[key]["omissions"] = find_omissions(report, art["findings"])
    if a3.button("✅ Finalize case", use_container_width=True):
        wl.set_status(cid, "finalized")
        wl.save()
        st.success(f"{cid} finalized.")

    if "omissions" in art:
        st.subheader("Omission QC")
        to_add = render_omissions_panel(art["omissions"], key_prefix=cid)
        if to_add:
            extra = " ".join(o["suggestion"] for o in to_add)
            st.session_state[f"i_{cid}"] = (i_val + "\n" + extra).strip()
            st.rerun()

    with st.expander("🗣️ Patient-friendly explainer (side-call)"):
        if st.button("Explain this report", key=f"explain_{cid}"):
            with st.spinner("Translating..."):
                st.session_state[key]["plain"] = explain_report(report)
        if art.get("plain"):
            theme.disclaimer("Draft for radiologist approval before sharing with a patient.")
            st.write(art["plain"])


def render() -> None:  # standalone entry
    st.set_page_config(page_title="RadQuant — Case", page_icon="🫁", layout="wide")
    theme.inject_css()
    page()


if __name__ == "__main__":
    render()
