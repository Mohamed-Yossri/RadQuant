"""Streamlit omission-QC panel — soft warnings with Dismiss / Add-to-report.

Used by the case view (Phase 7). ``render_omissions_panel`` returns the list of
omissions the radiologist chose to add to the report, so the caller can append
their suggested phrasing.
"""

from __future__ import annotations

from typing import List

import streamlit as st

from radquant.prompts.draft_report import _pretty
from radquant.nodes.triage import tier_of


def render_omissions_panel(omissions: List[dict], key_prefix: str = "om") -> List[dict]:
    """Render omissions as soft warnings. Returns the ones marked 'Add to report'."""
    if not omissions:
        st.success("✅ No high-confidence findings appear to be omitted.")
        return []

    st.warning(f"⚠️ {len(omissions)} high-confidence finding(s) may be missing "
               "from the report. Review each — this is a soft prompt, not a block.")

    to_add: List[dict] = []
    for i, om in enumerate(omissions):
        name = _pretty(om["finding"])
        with st.container(border=True):
            st.markdown(f"**{name}** — confidence {om['confidence']:.2f} "
                        f"· tier *{tier_of(om['finding'])}*")
            st.caption(om["suggestion"])
            c1, c2 = st.columns(2)
            dismissed = c1.button("Dismiss", key=f"{key_prefix}_dismiss_{i}")
            add = c2.button("Add to report", key=f"{key_prefix}_add_{i}", type="primary")
            if add and not dismissed:
                to_add.append(om)
    return to_add
