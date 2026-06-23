"""RadQuant design system — shared CSS, header, and status/urgency components.

A cohesive, product-grade visual language: a deep-navy clinical palette with a
cyan→indigo accent, glassy cards, gradient buttons, and a styled sidebar. The big
CSS block below restyles Streamlit's DOM so the app reads like a real web app.
"""

from __future__ import annotations

import html

import streamlit as st

# Palette ------------------------------------------------------------------- #
ACCENT = "#22D3EE"
ACCENT2 = "#6366F1"
INK = "#E6ECF5"
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

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap');

:root { --accent:#22D3EE; --accent2:#6366F1; --ink:#E6ECF5; --muted:#8A99AD;
        --line:rgba(255,255,255,.08); --card:rgba(255,255,255,.03); }

/* ---- base ---- */
html, body, .stApp, [class*="css"] { font-family:'Inter',system-ui,sans-serif; }
.stApp {
  background:
    radial-gradient(1100px 600px at 78% -12%, #18324d 0%, rgba(11,18,32,0) 55%),
    radial-gradient(900px 500px at -5% 0%, #1a1f4a 0%, rgba(11,18,32,0) 45%),
    #0A0F1A;
  color: var(--ink);
}
.block-container { max-width:1220px; padding-top:1.4rem; padding-bottom:3rem; }

/* ---- hide Streamlit chrome ---- */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
#MainMenu, footer, [data-testid="stHeader"] { display:none !important; }

/* ---- typography ---- */
h1,h2,h3 { font-family:'Space Grotesk','Inter',sans-serif; letter-spacing:-.02em;
           color:var(--ink); font-weight:700; }
h1 { font-size:1.9rem; } h2 { font-size:1.35rem; } h3 { font-size:1.1rem; }
p, span, label, li { color:#C7D2E1; }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
[data-testid="stCaptionContainer"], .stCaption, small { color:var(--muted) !important; }

/* ---- sidebar ---- */
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#0d1422 0%,#0a0f1a 100%);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] .block-container { padding-top:1rem; }
[data-testid="stSidebarNav"] { padding-top:.4rem; }
[data-testid="stSidebarNav"] a {
  border-radius:10px; margin:2px 8px; padding:7px 12px !important;
  transition:all .15s ease;
}
[data-testid="stSidebarNav"] a:hover { background:rgba(255,255,255,.05); text-decoration:none; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background:linear-gradient(90deg,rgba(34,211,238,.16),rgba(99,102,241,.12));
  box-shadow:inset 0 0 0 1px rgba(34,211,238,.35);
}
[data-testid="stSidebarNav"] a span { color:var(--ink) !important; font-weight:500; }

/* ---- buttons ---- */
.stButton > button, .stDownloadButton > button {
  border-radius:11px; font-weight:600; border:1px solid var(--line);
  background:rgba(255,255,255,.04); color:var(--ink); transition:all .15s ease;
  padding:.5rem 1rem;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  background:rgba(255,255,255,.08); border-color:rgba(34,211,238,.5);
  transform:translateY(-1px); color:var(--ink);
}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
  background:linear-gradient(135deg,#22D3EE 0%,#6366F1 100%); border:0; color:#06121c;
  box-shadow:0 6px 18px -6px rgba(34,211,238,.6);
}
.stButton > button[kind="primary"]:hover { filter:brightness(1.06); transform:translateY(-1px); }

/* ---- cards (st.container(border=True)) ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
  background:var(--card); border:1px solid var(--line) !important; border-radius:16px;
  box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 12px 30px -22px rgba(0,0,0,.8);
  transition:border-color .18s ease, transform .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color:rgba(34,211,238,.35) !important; transform:translateY(-2px);
}

/* ---- inputs ---- */
.stTextInput input, .stTextArea textarea, .stChatInput textarea,
[data-baseweb="select"] > div, [data-baseweb="input"] > div {
  background:rgba(255,255,255,.03) !important; border:1px solid var(--line) !important;
  border-radius:11px !important; color:var(--ink) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(34,211,238,.15) !important;
}

/* ---- metrics ---- */
[data-testid="stMetric"] {
  background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:14px 16px;
}
[data-testid="stMetricValue"] { font-size:1.7rem; font-weight:700; color:var(--ink); }
[data-testid="stMetricLabel"] { color:var(--muted); }

/* ---- radio as segmented control ---- */
.stRadio [role="radiogroup"] { gap:6px; }
.stRadio [role="radiogroup"] label {
  background:rgba(255,255,255,.03); border:1px solid var(--line); border-radius:10px;
  padding:5px 12px; transition:all .15s ease;
}
.stRadio [role="radiogroup"] label:hover { border-color:rgba(34,211,238,.4); }

/* ---- chat ---- */
[data-testid="stChatMessage"] {
  background:var(--card); border:1px solid var(--line); border-radius:14px; padding:6px 12px;
}
[data-testid="stChatInput"] { border-radius:14px; }

/* ---- tabs / expander ---- */
[data-testid="stExpander"] details {
  background:var(--card); border:1px solid var(--line) !important; border-radius:14px;
}
.stDataFrame { border-radius:14px; overflow:hidden; border:1px solid var(--line); }

/* ---- RadQuant components ---- */
.rq-top { display:flex; align-items:center; justify-content:space-between; gap:16px;
  padding:16px 20px; margin-bottom:16px; border-radius:18px;
  background:linear-gradient(120deg,rgba(34,211,238,.10),rgba(99,102,241,.08));
  border:1px solid var(--line);
  box-shadow:0 18px 40px -28px rgba(0,0,0,.9); }
.rq-brand { font-family:'Space Grotesk',sans-serif; font-size:1.5rem; font-weight:700;
  letter-spacing:-.02em; color:var(--ink); line-height:1; }
.rq-brand b { background:linear-gradient(135deg,#22D3EE,#818CF8);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.rq-tag { color:var(--muted); font-size:.8rem; margin-top:4px; }
.rq-pillbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.rq-dot { width:8px; height:8px; border-radius:50%; background:#34D399;
  box-shadow:0 0 0 4px rgba(52,211,153,.18); display:inline-block; margin-right:6px; }
.rq-pill { display:inline-flex; align-items:center; padding:3px 11px; border-radius:999px;
  font-size:.72rem; font-weight:700; letter-spacing:.3px; }
.rq-badge { display:inline-block; padding:2px 10px; border-radius:8px; margin:2px 2px 0 0;
  font-size:.72rem; font-weight:600; border:1px solid var(--line); background:rgba(255,255,255,.02); }
.rq-disc { background:rgba(248,113,113,.08); border:1px solid rgba(248,113,113,.3);
  color:#FCA5A5; padding:9px 14px; border-radius:12px; font-size:.8rem; margin-bottom:14px; }
.rq-card { border:1px solid var(--line); border-radius:14px; padding:14px 16px;
  background:var(--card); }

/* ---- scrollbar ---- */
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background:#243245; border-radius:8px; }
::-webkit-scrollbar-thumb:hover { background:#2f4358; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def app_header(active: str = "") -> None:
    st.markdown(
        f"""<div class="rq-top">
          <div>
            <div class="rq-brand">Rad<b>Quant</b></div>
            <div class="rq-tag">Quantified triage &amp; reporting for chest radiography</div>
          </div>
          <div class="rq-pillbar">
            <span class="rq-pill" style="background:rgba(52,211,153,.12);color:#34D399;">
              <span class="rq-dot"></span>LIVE</span>
            <span class="rq-pill" style="background:rgba(34,211,238,.14);color:{ACCENT};">{html.escape(active)}</span>
            <span class="rq-pill" style="background:rgba(248,113,113,.14);color:#FCA5A5;">RESEARCH USE ONLY</span>
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
