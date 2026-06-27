"""radquant/ui/case_view.py — Case workflow Streamlit page."""

import streamlit as st
from PIL import Image

from radquant.worklist import Worklist
from radquant.graph import build_graph, run_to_review, resume_review
from radquant.ui.theme import inject_css, urgency_pill, DISCLAIMER
from radquant.ui.qc_panel import render_qc_panel
from radquant.ui.comparison_panel import render_prior_sidebar, render_comparison_panel


def render(worklist: Worklist) -> None:
    inject_css()
    st.title("🩺 Case View")
    st.markdown(DISCLAIMER, unsafe_allow_html=True)

    # ── case selection ──────────────────────────────────────────────────────
    cases = worklist.sorted_cases()
    if not cases:
        st.info("No cases in worklist. Go to Worklist to add cases.")
        return

    active_id = st.session_state.get("active_case_id", cases[0]["case_id"])
    case_options = {c["case_id"]: f"{c['case_id']} ({c.get('urgency_tier','?')})" for c in cases}
    selected_id = st.selectbox("Select case:", list(case_options.keys()),
                               index=list(case_options.keys()).index(active_id)
                               if active_id in case_options else 0,
                               format_func=lambda k: case_options[k])
    st.session_state["active_case_id"] = selected_id

    case = worklist.get_case(selected_id)

    # ── sidebar: prior study linking ────────────────────────────────────────
    with st.sidebar:
        state = st.session_state.get("case_state") or dict(case)
        state = render_prior_sidebar(state, worklist)

    # ── load or retrieve state ───────────────────────────────────────────────
    if "case_state" not in st.session_state or st.session_state.get("case_state", {}).get("case_id") != selected_id:
        st.session_state["case_state"] = dict(case)
        st.session_state.pop("graph_ran", None)

    state = st.session_state["case_state"]

    # ── run pipeline ─────────────────────────────────────────────────────────
    if not st.session_state.get("graph_ran"):
        if st.button("▶️ Analyse case"):
            graph = build_graph()
            with st.spinner("Running pipeline (classify → compare → triage → visualize → draft) …"):
                result = run_to_review(graph, state, thread_id=selected_id)
                if isinstance(result, dict):
                    state.update(result)
                worklist.update_case(selected_id,
                    findings=state.get("findings", {}),
                    urgency_score=state.get("urgency_score", 0.0),
                    urgency_tier=state.get("urgency_tier", "Chronic"),
                    status="in_review",
                )
                st.session_state["case_state"] = state
                st.session_state["graph_ran"] = True
            st.rerun()

    # ── display image + heatmap ───────────────────────────────────────────────
    img_path = state.get("image_path")
    heatmap_path = state.get("heatmap_path")
    if img_path:
        col_img, col_heat = st.columns(2)
        with col_img:
            try:
                st.image(Image.open(img_path).convert("RGB"), caption="Input image",
                         use_container_width=True)
            except Exception:
                st.warning("Image unavailable.")
        with col_heat:
            if heatmap_path:
                try:
                    st.image(Image.open(heatmap_path).convert("RGB"), caption="Grad-CAM heatmap",
                             use_container_width=True)
                except Exception:
                    st.info("Heatmap not yet generated.")
            else:
                st.info("Run analysis to generate heatmap.")

    # ── urgency badge ─────────────────────────────────────────────────────────
    tier = state.get("urgency_tier", "")
    if tier:
        st.markdown(f"**Urgency:** {urgency_pill(tier)} &nbsp; Score: {state.get('urgency_score', 0):.3f}",
                    unsafe_allow_html=True)

    # ── longitudinal comparison panel ─────────────────────────────────────────
    render_comparison_panel(state)

    # ── draft report editing ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📝 Draft Report")
    if not state.get("draft_findings"):
        st.info("Run analysis to generate draft report.")
        return

    col_f, col_i = st.columns(2)
    with col_f:
        edited_findings = st.text_area("FINDINGS", value=state.get("draft_findings", ""), height=200)
    with col_i:
        edited_impression = st.text_area("IMPRESSION", value=state.get("draft_impression", ""), height=200)

    col_regen, col_finalize = st.columns(2)
    with col_regen:
        if st.button("🔁 Regenerate"):
            graph = build_graph()
            state["radiologist_edits"] = {"regenerate": True}
            result = resume_review(graph, {"regenerate": True}, thread_id=selected_id)
            if isinstance(result, dict):
                state.update(result)
            st.session_state["case_state"] = state
            st.rerun()

    with col_finalize:
        if st.button("✅ Finalize & run QC"):
            final_report = f"FINDINGS:\n{edited_findings}\n\nIMPRESSION:\n{edited_impression}"
            state["final_report"] = final_report
            state["draft_findings"] = edited_findings
            state["draft_impression"] = edited_impression
            # Run QC
            from radquant.nodes.qc import qc_node
            state = qc_node(state)
            worklist.update_case(selected_id, status="finalized",
                                 final_report=final_report)
            st.session_state["case_state"] = state
            st.rerun()

    # ── QC panel ─────────────────────────────────────────────────────────────
    if state.get("omissions") is not None:
        st.markdown("---")
        st.subheader("🛡️ Omission QC")
        state = render_qc_panel(state)
        st.session_state["case_state"] = state

    # ── finalized report ──────────────────────────────────────────────────────
    if state.get("final_report") and state.get("status") == "finalized":
        st.markdown("---")
        st.subheader("📄 Finalized Report")
        st.text(state["final_report"])
