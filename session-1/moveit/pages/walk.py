"""
Screen: Walk Mode
Timed walk with companion responses on demand.
"""

import streamlit as st
import time
from utils.companions import get_companion
from utils.chain import stream_companion
from utils.prompts import walk_opener, walk_random, walk_chip
from utils.state import go
from utils.styles import companion_bubble


# Prompt chip definitions
WALK_CHIPS = [
    ("🔥 Hype me!", "motivate"),
    ("😮‍💨 I'm tired", "tired"),
    ("😂 Make me laugh", "funny"),
    ("🏁 Halfway there!", "halfway"),
    ("🎉 Just finished!", "done"),
    ("🎯 Remind my goals", "goals"),
]


def _stream_walk_message(comp: dict, prompt: str) -> str:
    """Stream a companion response into the walk bubble. Returns full text."""
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
    return full_text


def render() -> None:
    comp = get_companion(
        st.session_state.companion_id,
        st.session_state.custom_companion,
    )

    # ── Top bar ─────────────────────────────────────────────────────────────
    col_back, col_title, col_timer = st.columns([1, 3, 2])
    with col_back:
        if st.button("←", key="walk_back", type="secondary"):
            st.session_state.walk_active = False
            go("home")
    with col_title:
        st.markdown("<span style='font-weight:700;font-size:1rem'>Walk Mode 🚶</span>", unsafe_allow_html=True)
    with col_timer:
        secs = st.session_state.walk_seconds
        m, s = divmod(secs, 60)
        st.markdown(
            f"<div class='walk-timer'>{m}:{s:02d}</div>",
            unsafe_allow_html=True,
        )

    # ── Auto-increment timer via rerun ──────────────────────────────────────
    # Simple timer: each rerun increments by 1 second
    if st.session_state.walk_active:
        time.sleep(1)
        st.session_state.walk_seconds += 1
        # Don't rerun automatically — user triggers next message

    # ── Opening message ─────────────────────────────────────────────────────
    if not st.session_state.walk_message:
        prompt = walk_opener(st.session_state.goals)
        st.session_state.walk_message = _stream_walk_message(comp, prompt)
    else:
        companion_bubble(comp["emoji"], comp["name"], st.session_state.walk_message)

    # ── Prompt chips (2 per row) ────────────────────────────────────────────
    st.markdown("**Tap for a response:**")
    rows = [WALK_CHIPS[i:i+2] for i in range(0, len(WALK_CHIPS), 2)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, chip_type) in zip(cols, row):
            with col:
                if st.button(label, key=f"chip_{chip_type}", type="secondary"):
                    prompt = walk_chip(chip_type, st.session_state.goals)
                    st.session_state.walk_message = _stream_walk_message(comp, prompt)

    # ── New random message ──────────────────────────────────────────────────
    if st.button("💬 Say something new", type="primary", key="walk_new"):
        prompt = walk_random()
        st.session_state.walk_message = _stream_walk_message(comp, prompt)
