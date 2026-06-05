"""
Session state initialisation.
Call init_state() once at app startup.
"""

import streamlit as st


DEFAULTS: dict = {
    # Navigation
    "screen": "onboard_goals",

    # Onboarding
    "goal_chips": [],
    "goals": ["", "", ""],
    "challenge": "",

    # Companion
    "companion_id": None,
    "custom_companion": {
        "name": "",
        "emoji": "🪄",
        "vibe": "",
    },

    # Daily data
    "checks": {
        "walk": False,
        "water": False,
        "protein": False,
        "workout": False,
        "sleep": False,
        "veggies": False,
    },

    # Streak
    "streak": 0,
    "last_checkin_date": None,

    # Walk mode
    "walk_seconds": 0,
    "walk_active": False,

    # Cached AI responses (avoid re-calling on rerun)
    "home_message": "",
    "walk_message": "",
    "checkin_message": "",
    "goals_message": "",
    "ready_message": "",
}


def init_state() -> None:
    """Set defaults for any missing session state keys."""
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go(screen: str) -> None:
    """Navigate to a screen and trigger a rerun."""
    st.session_state.screen = screen
    # Clear cached messages when switching screens so they refresh
    st.session_state.home_message = ""
    st.session_state.walk_message = ""
    st.rerun()


def reset_to_home() -> None:
    """Stop any active activity and return to the home screen."""
    st.session_state.walk_active = False
    st.session_state.walk_seconds = 0
    go("home")


def fresh_start() -> None:
    """Wipe all state back to defaults and restart onboarding from scratch."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()  # screen defaults back to "onboard_goals"
    st.rerun()


def get_done_checks() -> list[str]:
    """Return list of completed check-in item ids."""
    return [k for k, v in st.session_state.checks.items() if v]


def get_done_count() -> int:
    return sum(1 for v in st.session_state.checks.values() if v)
