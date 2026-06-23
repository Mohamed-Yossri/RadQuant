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
from radquant.models.auditor import get_auditor, render_overlay, PRETTY
from radquant.models.segmenter import segment_overlay
from radquant.assistant import build_assistant, ask
from radquant.ui import theme
from radquant.ui.qc_panel import render_omissions_panel


def _compose_report(findings_txt: str, impression_txt: str) -> str:
    return f"FINDINGS: {findings_txt}\n\nIMPRESSION: {impression_txt}".strip()


def _render_assistant(case, cid: str) -> None:
    """Interactive tool-using assistant: the orchestrator calls the CV tools."""
    st.divider()
    st.subheader("🤖 Ask RadQuant about this case")
    st.caption("A tool-using agent — the orchestrator calls MedGemma-VQA, the "
               "classifier, localization, and segmentation to answer. Research demo.")

    hist = st.session_state.setdefault(f"chat_{cid}", [])
    for role, text, used in hist:
        with st.chat_message("user" if role == "user" else "assistant"):
            st.write(text)
            if used:
                st.caption("🛠 tools: " + ", ".join(used))

    q = st.chat_input("e.g. Is there an effusion and where? Is the heart enlarged?")
    if q:
        akey = f"assistant_{cid}"
        if akey not in st.session_state:
            with st.spinner("Starting the case assistant..."):
                st.session_state[akey] = build_assistant(case.image_path)[0]
        hist.append(("user", q, []))
        with st.spinner("RadQuant is reasoning and using its tools..."):
            try:
                answer, used = ask(st.session_state[akey], q, thread_id=cid)
            except Exception as e:  # noqa: BLE001
                answer, used = f"(assistant error: {e})", []
        hist.append(("assistant", answer, used))
        st.rerun()


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
    b1, b2, b3 = st.columns(3)
    if b1.button("⚙️ Draft + Grad-CAM", type="primary", use_container_width=True):
        with st.spinner("Classifying, drafting (MedGemma), and computing Grad-CAM..."):
            findings = case.findings or classify_image(case.image_path)
            f_text, i_text, _ = draft_report(case.image_path, findings)
            heat, top = gradcam_overlay(case.image_path, findings=findings)
        st.session_state.setdefault(key, {})
        st.session_state[key].update({"findings": findings, "f": f_text, "i": i_text,
                                      "heat": heat, "top": top})
        # stage into a pending buffer; applied to the text widgets before they render
        st.session_state[f"pend_f_{cid}"] = f_text
        st.session_state[f"pend_i_{cid}"] = i_text
        st.rerun()
    if b2.button("🔍 Localize (boxes)", use_container_width=True):
        with st.spinner("Detecting & localizing findings (auditor model)..."):
            gf = get_auditor().detect(case.image_path)
            overlay = render_overlay(case.image_path, gf) if gf else None
        st.session_state.setdefault(key, {})
        st.session_state[key].update({"ground": gf, "ground_overlay": overlay})
    if b3.button("🫁 Segment anatomy", use_container_width=True):
        with st.spinner("Segmenting lung fields & heart (PSPNet)..."):
            seg, present = segment_overlay(case.image_path)
        st.session_state.setdefault(key, {})
        st.session_state[key].update({"seg_overlay": seg, "seg_present": present})

    art = st.session_state.get(key)

    left, right = st.columns([1, 1])
    with left:
        views = ["Original"]
        if art and art.get("heat"):
            views.append("Grad-CAM")
        if art and art.get("ground_overlay"):
            views.append("Grounding boxes")
        if art and art.get("seg_overlay"):
            views.append("Segmentation")
        view = st.radio("View", views, horizontal=True,
                        index=len(views) - 1 if len(views) > 1 else 0)
        if view == "Grad-CAM":
            st.image(art["heat"], caption=f"Grad-CAM · {art['top']}", use_container_width=True)
        elif view == "Grounding boxes":
            st.image(art["ground_overlay"], caption="Localized findings (auditor)",
                     use_container_width=True)
        elif view == "Segmentation":
            st.image(art["seg_overlay"],
                     caption="Anatomy: " + ", ".join(art.get("seg_present", [])),
                     use_container_width=True)
        else:
            st.image(case.image_path, caption=cid, use_container_width=True)
        if art and "ground" in art:
            gf = art["ground"]
            if gf:
                st.caption("**Localized:** " + ", ".join(
                    f"{PRETTY.get(f['label'], f['label'])}" for f in gf))
            else:
                st.caption("Grounding: no focal findings detected (or non-frontal image).")
    with right:
        st.markdown("**Draft report** (editable)")
        # apply any pending text BEFORE the widgets instantiate (Streamlit forbids
        # writing a widget's state after it's created in the same run).
        for _fld in ("f", "i"):
            _pk = f"pend_{_fld}_{cid}"
            if _pk in st.session_state:
                st.session_state[f"{_fld}_{cid}"] = st.session_state.pop(_pk)
        f_val = st.text_area("FINDINGS", height=170, key=f"f_{cid}",
                             placeholder="Click ⚙️ Draft + Grad-CAM to generate…")
        i_val = st.text_area("IMPRESSION", height=110, key=f"i_{cid}",
                             placeholder="—")

    _render_assistant(case, cid)

    if not art or "f" not in art:
        st.caption("Generate a draft to enable QC, finalize, and the explainer.")
        return

    report = _compose_report(f_val, i_val)

    st.divider()
    a1, a2, a3 = st.columns(3)
    if a1.button("🔁 Regenerate draft", use_container_width=True):
        with st.spinner("Regenerating..."):
            f_text, i_text, _ = draft_report(case.image_path, art["findings"])
        st.session_state[key].update({"f": f_text, "i": i_text})
        st.session_state[f"pend_f_{cid}"] = f_text
        st.session_state[f"pend_i_{cid}"] = i_text
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
            st.session_state[f"pend_i_{cid}"] = (i_val + "\n" + extra).strip()
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
