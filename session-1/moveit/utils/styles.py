"""
Global CSS injected via st.markdown.
Keeps the app looking clean and mobile-friendly.
"""

import streamlit as st


STYLES = """
<style>
/* ── Reset & base ────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    max-width: 480px !important;
    margin: 0 auto !important;
    padding: 1rem 1rem 5rem 1rem !important;
}

/* ── Typography ──────────────────────────────────────────────────────── */
h1 { font-size: 1.65rem !important; font-weight: 900 !important; line-height: 1.25 !important; }
h2 { font-size: 1.3rem !important; font-weight: 800 !important; }
h3 { font-size: 1.1rem !important; font-weight: 700 !important; }
p  { font-size: 0.9rem !important; line-height: 1.7 !important; }

/* ── Streamlit button overrides ──────────────────────────────────────── */
.stButton > button {
    border-radius: 13px !important;
    font-weight: 700 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 1.2rem !important;
    border: none !important;
    transition: transform 0.1s, box-shadow 0.1s !important;
}
.stButton > button:active {
    transform: translateY(2px) !important;
}

/* Primary buttons */
.stButton > button[kind="primary"] {
    background: #FF6B35 !important;
    color: #ffffff !important;
    box-shadow: 0 3px 0 #CC4A1A !important;
    width: 100% !important;
}
.stButton > button[kind="primary"]:hover {
    background: #e85d2a !important;
}

/* Secondary buttons */
.stButton > button[kind="secondary"] {
    background: #ffffff !important;
    color: #1C1308 !important;
    border: 1.5px solid #EDE3D8 !important;
    box-shadow: 0 2px 0 #EDE3D8 !important;
    width: 100% !important;
}

/* ── Cards ───────────────────────────────────────────────────────────── */
.moveit-card {
    background: #ffffff;
    border: 2px solid #EDE3D8;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 0.6rem;
}
.moveit-card.selected {
    border-color: var(--sel-color, #FF6B35);
    background: var(--sel-bg, #FFF0E8);
}
.moveit-card.done {
    border-color: #2ECC71;
    background: #F0FFF6;
}

/* ── Companion bubble ────────────────────────────────────────────────── */
.companion-bubble {
    background: #ffffff;
    border: 2px solid #EDE3D8;
    border-radius: 18px;
    padding: 1rem;
    margin: 0.75rem 0;
    border-top: 4px solid #FF6B35;
}
.companion-bubble .speaker-name {
    font-size: 0.72rem;
    font-weight: 700;
    color: #7A6A55;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.35rem;
}
.companion-bubble .bubble-text {
    font-size: 0.92rem;
    line-height: 1.75;
    color: #1C1308;
}

/* ── Goal summary box ────────────────────────────────────────────────── */
.goals-summ {
    background: #F5FAF2;
    border: 1.5px solid #B8DFB0;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.75rem;
}
.goals-summ .summ-title {
    font-size: 0.7rem;
    font-weight: 700;
    color: #1A4417;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.25rem;
}
.goals-summ .summ-body {
    font-size: 0.85rem;
    color: #2D6A26;
    line-height: 1.6;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
.prog-wrap {
    background: #EDE3D8;
    border-radius: 10px;
    height: 8px;
    margin: 0.5rem 0 1rem;
    overflow: hidden;
}
.prog-fill {
    height: 100%;
    background: #FF6B35;
    border-radius: 10px;
    transition: width 0.4s ease;
}

/* ── Streak pill ─────────────────────────────────────────────────────── */
.streak-pill {
    display: inline-block;
    background: #FFE66D;
    color: #5A4500;
    font-size: 0.78rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 20px;
}

/* ── Category label ──────────────────────────────────────────────────── */
.cat-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #7A6A55;
    margin: 1rem 0 0.4rem;
    display: block;
}

/* ── Chip pills ──────────────────────────────────────────────────────── */
.chip-selected {
    display: inline-block;
    background: #FFF0E8;
    border: 1.5px solid #FF6B35;
    color: #CC4A1A;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 18px;
    margin: 2px;
}

/* ── Hero emoji animation ────────────────────────────────────────────── */
.hero-emoji {
    font-size: 4.5rem;
    display: block;
    text-align: center;
    animation: bob 3s ease-in-out infinite;
}
@keyframes bob {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-8px); }
}

/* ── Walk timer ──────────────────────────────────────────────────────── */
.walk-timer {
    font-size: 1.8rem;
    font-weight: 900;
    color: #FF6B35;
    text-align: center;
    font-variant-numeric: tabular-nums;
    margin: 0.5rem 0;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr.moveit-divider {
    border: none;
    border-top: 1px solid #EDE3D8;
    margin: 1rem 0;
}

/* ── Stray padding reduction ─────────────────────────────────────────── */
.element-container { margin-bottom: 0.3rem !important; }
.stCheckbox { font-size: 0.9rem !important; }
div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
</style>
"""


def inject_styles() -> None:
    st.markdown(STYLES, unsafe_allow_html=True)


def companion_bubble(emoji: str, name: str, text: str) -> None:
    """Render a styled companion speech bubble."""
    st.markdown(f"""
    <div class="companion-bubble">
        <div class="speaker-name">{emoji} {name} says</div>
        <div class="bubble-text">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def goals_summary(goals: list[str], chips: list[str]) -> None:
    """Render the green goals summary box."""
    parts = []
    if chips:
        parts.append(" · ".join(chips))
    filled = [g for g in goals if g.strip()]
    if filled:
        parts.extend([f"{i+1}. {g}" for i, g in enumerate(filled)])
    body = "<br>".join(parts) if parts else "No goals set yet — let's start moving!"
    st.markdown(f"""
    <div class="goals-summ">
        <div class="summ-title">Today's mission</div>
        <div class="summ-body">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def progress_bar(done: int, total: int = 6) -> None:
    pct = int(done / total * 100)
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem">
        <div class="prog-wrap" style="flex:1">
            <div class="prog-fill" style="width:{pct}%"></div>
        </div>
        <span style="font-size:0.78rem;font-weight:700;color:#7A6A55;min-width:30px">{done}/{total}</span>
    </div>
    """, unsafe_allow_html=True)


def streak_badge(streak: int) -> None:
    st.markdown(f'<span class="streak-pill">🔥 {streak} day streak</span>', unsafe_allow_html=True)
