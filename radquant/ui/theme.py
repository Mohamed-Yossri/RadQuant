"""RadQuant design system — shared CSS, header, and status/urgency components.

A small, cohesive visual language reused across all pages: a deep-navy clinical
palette with a cyan accent, urgency pills, tier badges, and status chips.
"""

from __future__ import annotations

import html

import streamlit as st

# Palette ------------------------------------------------------------------- #
ACCENT = "#22D3EE"
INK = "#E5EAF1"
MUTED = "#8A99AD"
PANEL = "#131C2B"
LINE = "#243245"

URGENCY = [  # (min_score, label, color)
    (1.5, "CRITICAL", "#F87171"),
    (0.8, "HIGH", "#FB923C"),
    (0.4, "MODERATE", "#FBBF24"),
    (0.0, "LOW", "#34D399"),
]
TIER_COLOR = {
    "Critical": "#F87171", "Urgent": "#FB923C",
    "Important": "#FBBF24", "Chronic": "#34D399", "Unknown": "#8A99AD",
}
STATUS_COLOR = {"pending": "#8A99AD", "in_review": "#22D3EE", "finalized": "#34D399"}

_CSS = f"""
<style>
  .stApp {{ background:
      radial-gradient(1200px 600px at 80% -10%, #16243a 0%, #0B1220 45%) fixed; }}
  /* Header */
  .rq-header {{ display:flex; align-items:center; justify-content:space-between;
     padding: 6px 2px 14px; border-bottom: 1px solid {LINE}; margin-bottom: 14px; }}
  .rq-brand {{ font-size: 1.55rem; font-weight: 800; letter-spacing:-0.5px; color:{INK}; }}
  .rq-brand span {{ color:{ACCENT}; }}
  .rq-tag {{ color:{MUTED}; font-size:.82rem; margin-top:-2px; }}
  .rq-pillbar {{ display:flex; gap:8px; align-items:center; }}
  /* Generic pills/badges */
  .rq-pill {{ display:inline-block; padding:2px 10px; border-radius:999px;
     font-size:.72rem; font-weight:700; letter-spacing:.3px; }}
  .rq-badge {{ display:inline-block; padding:1px 9px; border-radius:6px;
     font-size:.72rem; font-weight:600; border:1px solid {LINE}; }}
  .rq-disc {{ background:#2A1726; border:1px solid #5b2741; color:#F7C6D6;
     padding:8px 12px; border-radius:10px; font-size:.8rem; margin-bottom:12px; }}
  .rq-kpi {{ color:{MUTED}; font-size:.75rem; text-transform:uppercase;
     letter-spacing:.6px; }}
  .rq-card {{ border:1px solid {LINE}; border-radius:14px; padding:14px 16px;
     background:linear-gradient(180deg,#10192880,#0e1622 100%); }}
  div[data-testid="stMetricValue"] {{ font-size:1.6rem; }}
  .stButton button {{ border-radius:10px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def app_header(active: str = "") -> None:
    st.markdown(
        f"""<div class="rq-header">
          <div>
            <div class="rq-brand">Rad<span>Quant</span></div>
            <div class="rq-tag">Quantified triage &amp; reporting for chest radiography</div>
          </div>
          <div class="rq-pillbar">
            <span class="rq-pill" style="background:#1c2a3f;color:{ACCENT};">{html.escape(active)}</span>
            <span class="rq-pill" style="background:#3a2030;color:#F7C6D6;">RESEARCH USE ONLY</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


def disclaimer(text: str) -> None:
    st.markdown(f'<div class="rq-disc">⚠️ {html.escape(text)}</div>', unsafe_allow_html=True)


def urgency_meta(score: float) -> tuple[str, str]:
    """Return (label, color) bucket for an urgency score."""
    for threshold, label, color in URGENCY:
        if score >= threshold:
            return label, color
    return "LOW", "#34D399"


def urgency_pill(score: float) -> str:
    label, color = urgency_meta(score)
    return (f'<span class="rq-pill" style="background:{color}22;color:{color};'
            f'border:1px solid {color}55;">{label} · {score:.2f}</span>')


def tier_badge(name: str, tier: str) -> str:
    color = TIER_COLOR.get(tier, MUTED)
    return (f'<span class="rq-badge" style="color:{color};border-color:{color}55;">'
            f'{html.escape(name)}</span>')


def status_chip(status: str) -> str:
    color = STATUS_COLOR.get(status, MUTED)
    return (f'<span class="rq-pill" style="background:{color}22;color:{color};">'
            f'{html.escape(status.replace("_", " "))}</span>')
