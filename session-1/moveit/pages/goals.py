"""
Screen: Goals
Update daily goals and get a personalized companion hype speech.
"""

import streamlit as st
from utils.companions import get_companion
from utils.chain import stream_companion
from utils.prompts import hype_goals
from utils.state import go
from utils.styles import companion_bubble


def render() -> None:
    comp = get_companion(
        st.session_state.companion_id,
        st.session_state.custom_companion,
    )

    # ── Top bar ─────────────────────────────────────────────────────────────
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("←", key="goals_back", type="secondary"):
            go("home")
    with col_title:
        st.markdown("<span style='font-weight:700;font-size:1rem'>Your Goals 🎯</span>", unsafe_allow_html=True)

    st.markdown(
        "<p style='color:#7A6A55;font-size:0.85rem;margin-bottom:1rem'>"
        "Update anytime. Your companion re-calibrates everything around your new goals."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Goal inputs ─────────────────────────────────────────────────────────
    g1 = st.text_input(
        "🟠 Goal 1",
        value=st.session_state.goals[0],
        placeholder="e.g. Walk 30 min before 9am",
        key="goals_g1",
    )
    g2 = st.text_input(
        "🟢 Goal 2",
        value=st.session_state.goals[1],
        placeholder="e.g. Drink 8 glasses of water",
        key="goals_g2",
    )
    g3 = st.text_input(
        "🟡 Goal 3",
        value=st.session_state.goals[2],
        placeholder="e.g. No sugar after 7pm",
        key="goals_g3",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Hype button ─────────────────────────────────────────────────────────
    if st.button("🔥 Hype my goals!", type="primary", key="goals_hype"):
        new_goals = [g1.strip(), g2.strip(), g3.strip()]
        filled = [g for g in new_goals if g]
        if not filled:
            st.warning("Write at least one goal first!")
        else:
            st.session_state.goals = new_goals

            prompt = hype_goals(new_goals)
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
            st.session_state.goals_message = full_text
            # Also refresh the home message
            st.session_state.home_message = ""

    # Show cached goals message
    elif st.session_state.goals_message:
        companion_bubble(comp["emoji"], comp["name"], st.session_state.goals_message)

    st.markdown("<hr class='moveit-divider'>", unsafe_allow_html=True)

    # ── Save without hype ───────────────────────────────────────────────────
    if st.button("Save goals quietly", type="secondary", key="goals_save"):
        st.session_state.goals = [g1.strip(), g2.strip(), g3.strip()]
        st.session_state.home_message = ""
        st.success("Goals saved! ✓")
