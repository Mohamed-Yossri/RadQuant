"""radquant/ui/worklist.py — Worklist Streamlit page."""

import streamlit as st
from radquant.ui.theme import inject_css, urgency_pill, DISCLAIMER
from radquant.worklist import Worklist


def render(worklist: Worklist) -> None:
    inject_css()
    st.title("📋 Worklist")
    st.markdown(DISCLAIMER, unsafe_allow_html=True)

    cases = worklist.sorted_cases()

    if not cases:
        st.info("No cases in the worklist. Upload a chest X-ray in Case View to get started.")
        if st.button("🌱 Seed demo worklist"):
            _seed_demo(worklist)
            st.rerun()
        return

    col_refresh, col_seed = st.columns([1, 1])
    with col_refresh:
        if st.button("🔄 Refresh"):
            st.rerun()
    with col_seed:
        if st.button("🌱 Add demo cases"):
            _seed_demo(worklist)
            st.rerun()

    st.markdown(f"**{len(cases)} case(s)** — sorted by urgency")

    for case in cases:
        tier = case.get("urgency_tier", "Chronic")
        score = case.get("urgency_score", 0.0)
        case_id = case["case_id"]
        status = case.get("status", "pending")
        findings = case.get("findings") or {}
        top = sorted(findings.items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join(f"{k} ({v:.2f})" for k, v in top) if top else "—"

        pill = urgency_pill(tier)
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
            with col1:
                st.markdown(f"**{case_id}**  {pill}", unsafe_allow_html=True)
            with col2:
                st.caption(top_str)
            with col3:
                st.caption(f"Score: {score:.3f}  ·  {status}")
            with col4:
                if st.button("Open", key=f"open_{case_id}"):
                    st.session_state["active_case_id"] = case_id
                    st.session_state["page"] = "case"
                    st.rerun()
            st.divider()


def _seed_demo(worklist: Worklist) -> None:
    """Add a couple of demo PNG paths if they exist."""
    import os
    from pathlib import Path
    demo_dir = Path("data/chestagentbench/figures")
    if demo_dir.exists():
        pngs = sorted(demo_dir.glob("*.png"))[:3]
        for p in pngs:
            worklist.add_case(str(p), patient_id="DEMO")
    else:
        st.warning("Demo images not found. Run scripts/setup.py first.")
