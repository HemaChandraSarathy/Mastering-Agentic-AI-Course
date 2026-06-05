"""
MoveIt — Fitness Accountability App
Built with Streamlit + LangChain + Anthropic Claude
"""

import streamlit as st
from utils.state import init_state, reset_to_home, fresh_start
from utils.styles import inject_styles

st.set_page_config(
    page_title="MoveIt 💪",
    page_icon="💪",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_styles()
init_state()

# ── Route to the right screen ──────────────────────────────────────────────
screen = st.session_state.screen

# ── Top-right utility toolbar ───────────────────────────────────────────────
# Compact icon buttons pinned to the top-right. 🏠 stops the current activity and
# goes home (hidden during onboarding — no home yet); ✨ wipes everything. Narrow
# columns keep them small despite the global width:100% button rule.
show_stop = screen not in ("onboard_goals", "pick_companion")
_, stop_col, fresh_col = st.columns([6, 1, 1])
with stop_col:
    if show_stop and st.button("🏠", key="stop_btn", type="secondary", help="Stop & go back home"):
        reset_to_home()
with fresh_col:
    if st.button("✨", key="fresh_btn", type="secondary", help="Fresh start — reset everything"):
        st.session_state.confirm_fresh = True

# Confirmation prompt for Fresh Start (everything gets wiped, so double-check).
if st.session_state.get("confirm_fresh"):
    st.warning("Start over? This wipes your goals, companion, streak, and check-ins.")
    yes_col, no_col = st.columns(2)
    with yes_col:
        if st.button("Yes, wipe it", key="fresh_yes"):
            fresh_start()
    with no_col:
        if st.button("Cancel", key="fresh_no"):
            st.session_state.confirm_fresh = False
            st.rerun()

if screen == "onboard_goals":
    from pages.onboard_goals import render
    render()

elif screen == "pick_companion":
    from pages.pick_companion import render
    render()

elif screen == "ready":
    from pages.ready import render
    render()

elif screen == "home":
    from pages.home import render
    render()

elif screen == "walk":
    from pages.walk import render
    render()

elif screen == "checkin":
    from pages.checkin import render
    render()

elif screen == "goals":
    from pages.goals import render
    render()
