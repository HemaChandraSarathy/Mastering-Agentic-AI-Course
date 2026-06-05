"""
Screen: Ready — Step 3
Companion greets the user personally based on their goals.
"""

import streamlit as st
from utils.companions import get_companion
from utils.chain import stream_companion
from utils.prompts import first_meeting
from utils.state import go
from utils.styles import companion_bubble, goals_summary


def render() -> None:
    comp = get_companion(
        st.session_state.companion_id,
        st.session_state.custom_companion,
    )

    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <span style="font-size:1.2rem;font-weight:900;color:#FF6B35">MoveIt 💪</span>
        <span style="font-size:0.75rem;color:#7A6A55;background:#EDE3D8;padding:3px 10px;border-radius:12px">Step 3 of 3</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        f"<div class='hero-emoji'>{comp['emoji']}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<h2 style='text-align:center;color:{comp['color']};margin-top:0.5rem'>{comp['name']}</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center;color:#7A6A55;font-size:0.85rem;margin-bottom:1rem'>{comp['tagline']}</p>",
        unsafe_allow_html=True,
    )

    # ── Goals summary ───────────────────────────────────────────────────────
    goals_summary(st.session_state.goals, st.session_state.goal_chips)

    # ── First meeting message ───────────────────────────────────────────────
    if not st.session_state.ready_message:
        prompt = first_meeting(
            st.session_state.goals,
            st.session_state.goal_chips,
            st.session_state.challenge,
        )
        with st.spinner(f"{comp['emoji']} {comp['name']} is getting ready..."):
            # Stream into the bubble
            bubble_placeholder = st.empty()
            full_text = ""
            for chunk in stream_companion(comp["persona"], prompt):
                full_text += chunk
                bubble_placeholder.markdown(f"""
                <div class="companion-bubble">
                    <div class="speaker-name">{comp['emoji']} {comp['name']} says</div>
                    <div class="bubble-text">{full_text}▌</div>
                </div>
                """, unsafe_allow_html=True)
            # Final without cursor
            bubble_placeholder.markdown(f"""
            <div class="companion-bubble">
                <div class="speaker-name">{comp['emoji']} {comp['name']} says</div>
                <div class="bubble-text">{full_text}</div>
            </div>
            """, unsafe_allow_html=True)
            st.session_state.ready_message = full_text
    else:
        companion_bubble(comp["emoji"], comp["name"], st.session_state.ready_message)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Actions ─────────────────────────────────────────────────────────────
    if st.button("🚀 Let's go!", type="primary", key="ready_go"):
        st.session_state.home_message = ""
        st.session_state.onboarded = True
        go("home")

    if st.button("↺ Change companion", type="secondary", key="ready_change"):
        st.session_state.ready_message = ""
        go("pick_companion")
