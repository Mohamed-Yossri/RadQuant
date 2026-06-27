"""radquant/ui/app.py — Main Streamlit app (st.navigation multi-page)."""

import streamlit as st

st.set_page_config(
    page_title="RadQuant",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="expanded",
)

from radquant.worklist import Worklist

# Singleton worklist in session state
if "worklist" not in st.session_state:
    st.session_state["worklist"] = Worklist()

worklist: Worklist = st.session_state["worklist"]

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["📋 Worklist", "🩺 Case View", "🗣️ Explainer", "⚙️ Settings"],
    index=0,
)

if page == "📋 Worklist":
    from radquant.ui.worklist import render
    render(worklist)

elif page == "🩺 Case View":
    from radquant.ui.case_view import render
    render(worklist)

elif page == "🗣️ Explainer":
    from radquant.ui.explainer import render
    render()

elif page == "⚙️ Settings":
    from radquant.ui.settings import render
    render()
