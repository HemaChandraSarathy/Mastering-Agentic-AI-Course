"""
Screen: Daily Check-In
Six habit checkboxes with companion reactions.
"""

import streamlit as st
from utils.companions import get_companion
from utils.chain import stream_companion
from utils.prompts import checkin_reaction
from utils.state import go, get_done_count, get_done_checks
from utils.styles import companion_bubble, progress_bar


CHECK_ITEMS = [
    ("walk",    "🚶", "Went for a walk?",       "Even 10 min counts!"),
    ("water",   "💧", "Drank enough water?",     "8 glasses of liquid gold"),
    ("protein", "🥩", "Hit your protein?",       "Muscles don't run on vibes"),
    ("workout", "🏋️", "Did your workout?",       "Future you is watching"),
    ("sleep",   "😴", "Got 7-8hrs sleep?",       "Rest is part of the grind"),
    ("veggies", "🥦", "Ate your greens?",        "Broccoli won't eat itself"),
]


def render() -> None:
    comp = get_companion(
        st.session_state.companion_id,
        st.session_state.custom_companion,
    )

    # ── Top bar ─────────────────────────────────────────────────────────────
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("←", key="ci_back", type="secondary"):
            go("home")
    with col_title:
        st.markdown("<span style='font-weight:700;font-size:1rem'>Daily Check-In ✅</span>", unsafe_allow_html=True)

    # ── Progress bar ────────────────────────────────────────────────────────
    done_count = get_done_count()
    progress_bar(done_count)

    # ── Checkboxes ──────────────────────────────────────────────────────────
    changed = False
    for item_id, emoji, label, hint in CHECK_ITEMS:
        current_val = st.session_state.checks.get(item_id, False)

        # Style the row
        bg = "#F0FFF6" if current_val else "#ffffff"
        border = "#2ECC71" if current_val else "#EDE3D8"
        st.markdown(f"""
        <div style="background:{bg};border:2px solid {border};border-radius:14px;
                    padding:0.7rem 1rem;margin-bottom:0.4rem;display:flex;align-items:center;gap:0.6rem">
            <span style="font-size:1.3rem">{emoji}</span>
            <div>
                <div style="font-weight:600;font-size:0.88rem">{label}</div>
                <div style="font-size:0.75rem;color:#7A6A55">{hint}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        new_val = st.checkbox(
            label,
            value=current_val,
            key=f"ci_{item_id}",
            label_visibility="collapsed",
        )
        if new_val != current_val:
            st.session_state.checks[item_id] = new_val
            changed = True

    # ── Companion reaction ──────────────────────────────────────────────────
    if changed or (not st.session_state.checkin_message and done_count > 0):
        prompt = checkin_reaction(get_done_count(), get_done_checks())
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
        st.session_state.checkin_message = full_text

    elif st.session_state.checkin_message:
        companion_bubble(comp["emoji"], comp["name"], st.session_state.checkin_message)

    elif done_count == 0:
        st.info(f"{comp['emoji']} Start checking off habits and {comp['name']} will react!")

    # ── Celebrate all done ──────────────────────────────────────────────────
    if done_count == 6:
        st.balloons()
        st.success("🏆 All 6 done! You are an absolute legend today!")
