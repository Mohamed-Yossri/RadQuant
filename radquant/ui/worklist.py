"""Worklist page — cases ranked by urgency, as interactive cards.

Run standalone:  streamlit run radquant/ui/worklist.py
"""

from __future__ import annotations

import streamlit as st

from radquant.worklist import Worklist
from radquant.nodes.triage import tier_of
from radquant.ui import theme


def _seed_demo(n: int) -> None:
    """Populate the worklist from N sample figures (classify + triage)."""
    from radquant.data import sample
    from radquant.nodes.classify import classify_image

    wl = Worklist()
    with st.spinner(f"Classifying {n} sample studies..."):
        for i, img in enumerate(sample(n)):
            wl.add_from_findings(f"case-{i:02d}", str(img), classify_image(str(img)))
    wl.save()


def page() -> None:
    theme.app_header("WORKLIST")
    theme.disclaimer("Urgency weights are literature-anchored defaults, not "
                     "site-validated. Research/assistive demo — not for clinical use.")

    wl = Worklist.load()

    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("⟳ Seed demo worklist", use_container_width=True):
        _seed_demo(12)
        st.rerun()
    if c2.button("🗑 Clear", use_container_width=True):
        Worklist().save()
        st.rerun()

    if len(wl) == 0:
        st.info("Worklist is empty. Click **Seed demo worklist** to ingest a few "
                "sample studies through classify → triage.")
        return

    cases = wl.sorted(descending=True)
    pending = sum(1 for c in cases if c.status == "pending")
    k1, k2, k3 = st.columns(3)
    k1.metric("Studies", len(cases))
    k2.metric("Pending", pending)
    k3.metric("Top urgency", f"{cases[0].urgency_score:.2f}")
    st.write("")

    for c in cases:
        with st.container(border=True):
            col_u, col_f, col_s, col_b = st.columns([1.1, 3, 0.9, 0.9])
            col_u.markdown(theme.urgency_pill(c.urgency_score), unsafe_allow_html=True)
            col_u.caption(c.case_id)
            badges = " ".join(
                theme.tier_badge(f"{k} {v:.2f}", tier_of(k)) for k, v in c.top(3)
            )
            col_f.markdown(badges, unsafe_allow_html=True)
            col_s.markdown(theme.status_chip(c.status), unsafe_allow_html=True)
            if col_b.button("Open ›", key=f"open_{c.case_id}", use_container_width=True):
                st.session_state["selected_case"] = c.case_id
                _pages = st.session_state.get("_pages")
                if _pages and "case" in _pages:
                    st.switch_page(_pages["case"])
                else:
                    st.toast(f"Selected {c.case_id} — open the Case tab.")


def render() -> None:  # standalone entry
    st.set_page_config(page_title="RadQuant — Worklist", page_icon="🫁", layout="wide")
    theme.inject_css()
    page()


if __name__ == "__main__":
    render()
