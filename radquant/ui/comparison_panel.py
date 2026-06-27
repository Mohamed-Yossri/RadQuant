"""radquant/ui/comparison_panel.py — Longitudinal comparison Streamlit component (Phase 10)."""

import streamlit as st
from PIL import Image

from radquant.worklist import Worklist
from radquant.nodes.compare import comparison_node

_CATEGORY_CONFIG = [
    ("new",      "🔴 New",      "#ff4b4b"),
    ("worsened", "🟠 Worsened", "#ff8c00"),
    ("improved", "🟢 Improved", "#21c354"),
    ("resolved", "✅ Resolved", "#1c83e1"),
    ("stable",   "⚪ Stable",   "#888888"),
]


def render_prior_sidebar(state: dict, worklist: Worklist) -> dict:
    """Render sidebar section. Returns (possibly updated) state."""
    st.subheader("📅 Prior Study")

    case_id = state.get("case_id", "")
    patient_id = (state.get("dicom_metadata") or {}).get("PatientID", "")

    if worklist.has_prior(case_id):
        prior_date = state.get("prior_study_date", "unknown")
        st.success(f"Prior linked: **{prior_date}**")

        col_run, col_unlink = st.columns(2)
        with col_run:
            if st.button("🔄 Re-compare", use_container_width=True):
                with st.spinner("Comparing …"):
                    state = comparison_node(state)
                    worklist.update_case(
                        case_id,
                        comparison_impression=state.get("comparison_impression"),
                        comparison_interval=state.get("comparison_interval"),
                    )
                    st.session_state["case_state"] = state
                st.rerun()
        with col_unlink:
            if st.button("✖ Unlink", use_container_width=True):
                worklist.unlink_prior(case_id)
                state = {**state,
                    "prior_image_path": None, "prior_study_date": None,
                    "prior_findings": None, "comparison_report": None,
                    "interval_findings": None, "comparison_impression": None,
                    "comparison_interval": None,
                }
                st.session_state["case_state"] = state
                st.rerun()
    else:
        prior_cases = worklist.get_same_patient_cases(patient_id=patient_id, exclude=case_id)
        if not prior_cases:
            st.info("No prior studies found for this patient." if patient_id
                    else "Patient ID unavailable (anonymous upload).")
        else:
            options = {c["case_id"]: f"{c.get('study_date','?')} — {c['case_id']}" for c in prior_cases}
            selected_id = st.selectbox("Select prior study:", list(options.keys()),
                                       format_func=lambda k: options[k])
            if st.button("🔗 Link & Compare", use_container_width=True):
                worklist.link_prior(case_id, selected_id)
                prior_case = worklist.cases[selected_id]
                state = {**state,
                    "prior_image_path": prior_case["image_path"],
                    "prior_study_date": prior_case.get("study_date"),
                    "prior_findings": prior_case.get("findings"),
                }
                with st.spinner("Running comparison …"):
                    state = comparison_node(state)
                    worklist.update_case(case_id,
                        comparison_impression=state.get("comparison_impression"),
                        comparison_interval=state.get("comparison_interval"),
                    )
                    st.session_state["case_state"] = state
                st.rerun()
    return state


def render_comparison_panel(state: dict) -> None:
    """Render the comparison results in the main content area."""
    interval_findings = state.get("interval_findings") or []
    if not interval_findings and not state.get("comparison_impression"):
        return

    st.markdown("---")
    st.subheader("🔄 Interval Comparison")

    interval = state.get("comparison_interval", "")
    prior_date = state.get("prior_study_date", "unknown")
    if interval:
        st.caption(f"Interval: **{interval}**  ·  Prior dated {prior_date}")

    # Side-by-side thumbnails
    col_prior, col_current = st.columns(2)
    with col_prior:
        if state.get("prior_image_path"):
            try:
                st.image(Image.open(state["prior_image_path"]).convert("RGB"),
                         caption=f"Prior — {prior_date}", use_container_width=True)
            except Exception:
                st.warning("Prior image unavailable.")
    with col_current:
        if state.get("image_path"):
            try:
                st.image(Image.open(state["image_path"]).convert("RGB"),
                         caption="Current study", use_container_width=True)
            except Exception:
                st.warning("Current image unavailable.")

    # Clinical impression
    if state.get("comparison_impression"):
        st.info(f"**Clinical impression:** {state['comparison_impression']}")

    if not interval_findings:
        with st.expander("Raw comparison report"):
            st.text(state.get("comparison_report", ""))
        return

    # Colour-coded findings
    grouped = {cat: [] for cat, *_ in _CATEGORY_CONFIG}
    for f in interval_findings:
        cat = f.get("change", "stable")
        if cat in grouped:
            grouped[cat].append(f)

    for change_type, label, colour in _CATEGORY_CONFIG:
        items = grouped.get(change_type, [])
        if not items:
            continue
        st.markdown(f"**{label}** ({len(items)})")
        for item in items:
            with st.expander(item.get("finding", ""), expanded=(change_type in ("new", "worsened"))):
                st.markdown(item.get("detail", "_No additional detail._"))

    with st.expander("Raw MedGemma comparison report"):
        st.text(state.get("comparison_report", ""))
