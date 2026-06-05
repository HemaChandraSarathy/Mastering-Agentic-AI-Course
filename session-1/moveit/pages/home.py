"""
Screen: Home
Daily hub — companion greeting, goals summary, nav to other screens.
"""

import streamlit as st
from datetime import datetime
from utils.companions import get_companion
from utils.chain import stream_companion
from utils.prompts import daily_opener
from utils.state import go
from utils.styles import companion_bubble, goals_summary, streak_badge


def render() -> None:
    comp = get_companion(
        st.session_state.companion_id,
        st.session_state.custom_companion,
    )

    h = datetime.now().hour
    tod = "morning" if h < 12 else "afternoon" if h < 17 else "evening"

    # ── Top bar ─────────────────────────────────────────────────────────────
    col_logo, col_streak = st.columns([3, 1])
    with col_logo:
        st.markdown("<span style='font-size:1.3rem;font-weight:900;color:#FF6B35'>MoveIt 💪</span>", unsafe_allow_html=True)
    with col_streak:
        streak_badge(st.session_state.streak)

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='hero-emoji' style='margin:0.5rem 0 0.25rem'>{comp['emoji']}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<h2 style='text-align:center;color:{comp['color']};margin:0'>{comp['name']}</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center;color:#7A6A55;font-size:0.82rem;margin-top:0.2rem'>Good {tod}!</p>",
        unsafe_allow_html=True,
    )

    # ── Daily companion message ─────────────────────────────────────────────
    if not st.session_state.home_message:
        prompt = daily_opener(st.session_state.goals, st.session_state.goal_chips)
        placeholder = st.empty()
        full_text = ""
        for chunk in stream_companion(comp["persona"], prompt):
            full_text += chunk
            placeholder.markdown(f"""
            <div class="companion-bubble">
                <div class="speaker-name">{comp['emoji']} {comp['name']} says</div>
                <div class="bubble-text">{full_text}▌</div>
            </div>
            """, unsafe_allow_html=True)
        placeholder.markdown(f"""
        <div class="companion-bubble">
            <div class="speaker-name">{comp['emoji']} {comp['name']} says</div>
            <div class="bubble-text">{full_text}</div>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.home_message = full_text
    else:
        companion_bubble(comp["emoji"], comp["name"], st.session_state.home_message)

    # ── Goals summary ───────────────────────────────────────────────────────
    goals_summary(st.session_state.goals, st.session_state.goal_chips)

    # ── Navigation buttons ──────────────────────────────────────────────────
    if st.button("🚶 Start Walk Mode", type="primary", key="home_walk"):
        st.session_state.walk_message = ""
        st.session_state.walk_seconds = 0
        st.session_state.walk_active = True
        go("walk")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Daily Check-In", type="secondary", key="home_ci"):
            go("checkin")
    with col2:
        if st.button("🎯 Update Goals", type="secondary", key="home_goals"):
            go("goals")

    st.markdown("<hr class='moveit-divider'>", unsafe_allow_html=True)

    if st.button("↺ Switch companion", type="secondary", key="home_switch"):
        st.session_state.ready_message = ""
        st.session_state.home_message = ""
        go("pick_companion")

    # ── Refresh greeting ─────────────────────────────────────────────────────
    if st.button("🔄 New message from companion", type="secondary", key="home_refresh"):
        st.session_state.home_message = ""
        st.rerun()
