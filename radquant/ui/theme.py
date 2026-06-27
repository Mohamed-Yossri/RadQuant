"""radquant/ui/theme.py — Design system: CSS, urgency pills, status badges."""

import streamlit as st

TIER_COLORS = {
    "Critical":  ("#ff4b4b", "white"),
    "Urgent":    ("#ff8c00", "white"),
    "Important": ("#f0c93a", "black"),
    "Chronic":   ("#21c354", "white"),
}


def inject_css() -> None:
    st.markdown("""
    <style>
    .urgency-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75em;
        background: #333;
        color: #ccc;
    }
    .disclaimer {
        font-size: 0.75em;
        color: #888;
        border-left: 3px solid #444;
        padding-left: 8px;
        margin-top: 8px;
    }
    </style>
    """, unsafe_allow_html=True)


def urgency_pill(tier: str) -> str:
    bg, fg = TIER_COLORS.get(tier, ("#555", "white"))
    return f'<span class="urgency-pill" style="background:{bg};color:{fg};">{tier}</span>'


DISCLAIMER = (
    '<div class="disclaimer">⚠️ Research / assistive demo — not a medical device. '
    'No report is finalized without a radiologist in the loop.</div>'
)
