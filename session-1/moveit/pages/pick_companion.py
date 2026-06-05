"""
Screen: Onboarding — Step 2
User picks a preset companion or creates a custom one.
"""

import streamlit as st
from utils.companions import COMPANIONS, CATEGORIES
from utils.state import go


def render() -> None:
    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <span style="font-size:1.2rem;font-weight:900;color:#FF6B35">MoveIt 💪</span>
        <span style="font-size:0.75rem;color:#7A6A55;background:#EDE3D8;padding:3px 10px;border-radius:12px">Step 2 of 3</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## Pick your companion 🎭")
    st.markdown(
        "<p style='color:#7A6A55;margin-bottom:1rem'>"
        "Pick from the list — or create your own. Anyone, any character, any vibe."
        "</p>",
        unsafe_allow_html=True,
    )

    current = st.session_state.companion_id

    # ── Preset companions by category ──────────────────────────────────────
    for category in CATEGORIES:
        companions_in_cat = {k: v for k, v in COMPANIONS.items() if v["category"] == category}
        if not companions_in_cat:
            continue

        st.markdown(
            f"<span class='cat-label'>{_cat_icon(category)} {category}</span>",
            unsafe_allow_html=True,
        )

        for cid, comp in companions_in_cat.items():
            is_selected = (current == cid)
            border_style = f"border-color:{comp['color']};background:{comp['bg']}" if is_selected else ""
            check = "✓ " if is_selected else ""

            st.markdown(f"""
            <div class="moveit-card" style="{border_style};cursor:pointer">
                <div style="display:flex;align-items:center;gap:12px">
                    <div style="width:46px;height:46px;border-radius:13px;background:{comp['bg']};
                                display:flex;align-items:center;justify-content:center;
                                font-size:1.5rem;flex-shrink:0;border:1px solid {comp['color']}30">
                        {comp['emoji']}
                    </div>
                    <div style="flex:1">
                        <div style="font-weight:700;font-size:0.9rem;color:{comp['color'] if is_selected else '#1C1308'}">
                            {check}{comp['name']}
                        </div>
                        <div style="font-size:0.78rem;color:#7A6A55;line-height:1.45;margin-top:2px">
                            {comp['sample_quote']}
                        </div>
                        <span style="display:inline-block;font-size:0.7rem;font-weight:600;
                                     padding:2px 8px;border-radius:9px;margin-top:4px;
                                     background:{comp['bg']};color:{comp['color']}">
                            {comp['style_tag']}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                f"{'✓ Selected' if is_selected else 'Select'} {comp['name']}",
                key=f"pick_{cid}",
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.companion_id = cid
                st.rerun()

    # ── Custom companion ───────────────────────────────────────────────────
    st.markdown(
        "<span class='cat-label'>✨ Create your own</span>",
        unsafe_allow_html=True,
    )
    is_custom = (current == "custom")
    border_style = "border-color:#7C3AED;background:#F5F3FF" if is_custom else ""

    st.markdown(f"""
    <div class="moveit-card" style="{border_style}">
        <div style="display:flex;align-items:center;gap:12px">
            <div style="width:46px;height:46px;border-radius:13px;background:#F5F0FF;
                        display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">
                🪄
            </div>
            <div>
                <div style="font-weight:700;font-size:0.9rem">Custom companion</div>
                <div style="font-size:0.78rem;color:#7A6A55;line-height:1.4">
                    Type anyone — celebrity, character, your dog's name, a vibe.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(
        "✓ Custom selected" if is_custom else "Create custom companion",
        key="pick_custom",
        type="primary" if is_custom else "secondary",
    ):
        st.session_state.companion_id = "custom"
        st.rerun()

    # Show custom form when custom is selected
    if is_custom:
        with st.container():
            st.markdown("<div style='background:#F5F3FF;border-radius:12px;padding:1rem;margin-top:0.5rem'>", unsafe_allow_html=True)

            cname = st.text_input(
                "Who is your companion?",
                value=st.session_state.custom_companion.get("name", ""),
                placeholder="e.g. Dwayne 'The Rock' Johnson, Hermione Granger, my mom...",
                key="custom_name_input",
            )
            col_e, col_v = st.columns([1, 3])
            with col_e:
                cemoji = st.text_input(
                    "Emoji",
                    value=st.session_state.custom_companion.get("emoji", "🪄"),
                    max_chars=4,
                    key="custom_emoji_input",
                )
            with col_v:
                cvibe = st.text_area(
                    "Their vibe / how they talk (optional)",
                    value=st.session_state.custom_companion.get("vibe", ""),
                    placeholder="e.g. Intense, uses wrestling metaphors, very no-excuses...",
                    height=70,
                    key="custom_vibe_input",
                )

            st.session_state.custom_companion = {
                "name": cname,
                "emoji": cemoji,
                "vibe": cvibe,
            }
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Navigation ──────────────────────────────────────────────────────────
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back", key="pick_back", type="secondary"):
            go("onboard_goals")

    with col_next:
        can_proceed = bool(current)
        if is_custom:
            can_proceed = bool(st.session_state.custom_companion.get("name", "").strip())

        if can_proceed:
            if st.button("Next →", key="pick_next", type="primary"):
                # Pre-clear ready message so it reloads
                st.session_state.ready_message = ""
                go("ready")
        else:
            st.button("Select a companion first", disabled=True, key="pick_next_disabled")


def _cat_icon(category: str) -> str:
    icons = {
        "Motivators": "🎤",
        "Late Night": "😂",
        "TV Characters": "📺",
        "Animals": "🐾",
    }
    return icons.get(category, "⭐")
