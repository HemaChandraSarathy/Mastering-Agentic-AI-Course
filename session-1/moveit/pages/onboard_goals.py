"""
Screen: Onboarding — Step 1
User sets their fitness focus areas, specific daily goals, and biggest challenge.
"""

import streamlit as st
from utils.state import go


FOCUS_CHIPS = [
    "Lose weight", "Build muscle", "Walk daily", "Drink more water",
    "Eat healthier", "Sleep better", "Run a 5K", "More energy",
    "Stay consistent", "Reduce stress",
]


def render() -> None:
    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem">
        <span style="font-size:1.2rem;font-weight:900;color:#FF6B35">MoveIt 💪</span>
        <span style="font-size:0.75rem;color:#7A6A55;background:#EDE3D8;padding:3px 10px;border-radius:12px">Step 1 of 3</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## Let's set your goals 🎯")
    st.markdown(
        "<p style='color:#7A6A55;margin-bottom:1.2rem'>"
        "Tell us what you're working on — your companion will personalise everything around you."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Focus area chips ───────────────────────────────────────────────────
    st.markdown("**What are you working on?**")
    st.caption("Select all that apply")

    # Use a grid of checkboxes styled as chips
    selected_chips = list(st.session_state.goal_chips)
    cols_per_row = 2
    rows = [FOCUS_CHIPS[i:i+cols_per_row] for i in range(0, len(FOCUS_CHIPS), cols_per_row)]

    for row in rows:
        cols = st.columns(len(row))
        for col, chip in zip(cols, row):
            with col:
                checked = st.checkbox(chip, value=(chip in selected_chips), key=f"chip_{chip}")
                if checked and chip not in selected_chips:
                    selected_chips.append(chip)
                elif not checked and chip in selected_chips:
                    selected_chips.remove(chip)

    st.session_state.goal_chips = selected_chips

    st.markdown("<hr class='moveit-divider'>", unsafe_allow_html=True)

    # ── Specific daily goals ───────────────────────────────────────────────
    st.markdown("**Your 3 daily goals** *(be specific!)*")
    st.caption("Specific goals get specific motivation")

    g1 = st.text_input(
        "Goal 1",
        value=st.session_state.goals[0],
        placeholder="e.g. Walk 30 min before 9am",
        key="goal_input_1",
    )
    g2 = st.text_input(
        "Goal 2",
        value=st.session_state.goals[1],
        placeholder="e.g. Drink 8 glasses of water",
        key="goal_input_2",
    )
    g3 = st.text_input(
        "Goal 3",
        value=st.session_state.goals[2],
        placeholder="e.g. No sugar after 7pm",
        key="goal_input_3",
    )
    st.session_state.goals = [g1, g2, g3]

    st.markdown("<hr class='moveit-divider'>", unsafe_allow_html=True)

    # ── Biggest challenge ──────────────────────────────────────────────────
    st.markdown("**Biggest challenge?**")
    challenge = st.text_area(
        "Challenge",
        value=st.session_state.challenge,
        placeholder="e.g. I always quit after 2 weeks…",
        height=80,
        key="challenge_input",
        label_visibility="collapsed",
    )
    st.session_state.challenge = challenge

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Next ───────────────────────────────────────────────────────────────
    if st.button("Next — pick your companion →", type="primary", key="goals_next"):
        go("pick_companion")
