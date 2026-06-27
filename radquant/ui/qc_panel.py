"""radquant/ui/qc_panel.py — Omission QC Streamlit component."""

import streamlit as st


def render_qc_panel(state: dict) -> dict:
    """
    Show omission warnings. Returns updated state after dismiss/add actions.
    """
    omissions = state.get("omissions") or []
    if not omissions:
        st.success("✅ No omissions detected — all high-confidence findings addressed.")
        return state

    st.warning(f"⚠️ {len(omissions)} possible omission(s) detected")

    dismissed = set(st.session_state.get("dismissed_omissions", []))
    added = list(st.session_state.get("added_omissions", []))
    final_report = state.get("final_report") or ""

    for omission in omissions:
        finding = omission["finding"]
        if finding in dismissed:
            continue
        confidence = omission["confidence"]
        suggestion = omission["suggestion"]

        with st.expander(f"🔴 {finding} (confidence: {confidence:.0%})", expanded=True):
            st.markdown(f"*{suggestion}*")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✖ Dismiss", key=f"dismiss_{finding}"):
                    dismissed.add(finding)
                    st.session_state["dismissed_omissions"] = list(dismissed)
                    st.rerun()
            with col2:
                if st.button(f"➕ Add to report", key=f"add_{finding}"):
                    note = f"\n[QC note: {suggestion}]"
                    final_report += note
                    added.append(finding)
                    st.session_state["added_omissions"] = added
                    st.rerun()

    return {**state, "final_report": final_report}
