"""
Prompt templates for every companion interaction.
Each function returns a fully formatted string ready to pass to run_companion().
"""

from datetime import datetime


def _time_of_day() -> str:
    h = datetime.now().hour
    if h < 5:   return "night"
    if h < 12:  return "morning"
    if h < 17:  return "afternoon"
    return "evening"


def _goals_str(goals: list[str]) -> str:
    filled = [g for g in goals if g.strip()]
    return ", ".join(filled) if filled else "general fitness"


# ── Onboarding / First Meet ────────────────────────────────────────────────

def first_meeting(goals: list[str], chips: list[str], challenge: str) -> str:
    return (
        f"You are meeting someone for the very first time as their fitness companion. "
        f"It's {_time_of_day()}. "
        f"Their fitness focus areas: {', '.join(chips) or 'general fitness'}. "
        f"Their specific goals: {_goals_str(goals)}. "
        f"Their biggest challenge: {challenge or 'not shared yet'}. "
        f"Give a warm, excited first-meeting greeting. Reference their actual goals. "
        f"Make it feel personal and in your complete character voice. 3 sentences max."
    )


# ── Home Screen ────────────────────────────────────────────────────────────

def daily_opener(goals: list[str], chips: list[str]) -> str:
    return (
        f"It's {_time_of_day()}. "
        f"Give this person a short, energising opening pep talk to start their fitness day. "
        f"Their focus: {', '.join(chips) or 'staying active'}. "
        f"Their goals: {_goals_str(goals)}. "
        f"Full character energy. 2-3 sentences."
    )


# ── Walk Mode ──────────────────────────────────────────────────────────────

def walk_opener(goals: list[str]) -> str:
    return (
        f"Someone just started a walk. Give them an energising opening line. "
        f"Their goals: {_goals_str(goals)}. Full character. 2 sentences."
    )


def walk_random() -> str:
    import random
    lines = [
        "Say something encouraging to someone who has been walking for a few minutes. Full character. 2 sentences.",
        "Drop some in-character wisdom or humor for someone mid-walk. 2 sentences.",
        "Short punchy motivational line for someone on a walk. Stay in character. 2 sentences.",
        "Observe something poetic or funny about the act of walking. In character. 2 sentences.",
    ]
    return random.choice(lines)


def walk_chip(chip_type: str, goals: list[str]) -> str:
    g = _goals_str(goals)
    prompts = {
        "motivate": (
            f"Someone on a walk needs MAXIMUM motivation right now. Their goals: {g}. "
            f"Turn it all the way up in your full character voice. 2-3 sentences."
        ),
        "tired": (
            f"Someone just said they're tired and want to quit their walk. Their goals: {g}. "
            f"Respond in your full character to keep them going. Be firm but loving. 2-3 sentences."
        ),
        "funny": (
            f"Someone on a walk asked you to make them laugh. "
            f"Give them your best in-character joke or observation about exercise. 2-3 sentences."
        ),
        "halfway": (
            f"Someone just hit the halfway point of their walk! "
            f"Celebrate with them in your full character voice. 2 sentences."
        ),
        "done": (
            f"Someone JUST FINISHED their walk! React to this huge achievement. "
            f"Their goals were: {g}. Go big — this deserves full character energy. 2-3 sentences."
        ),
        "goals": (
            f"Remind someone of their fitness goals in a motivating way: {g}. "
            f"Make it feel personal and in your complete character voice. 2-3 sentences."
        ),
    }
    return prompts.get(chip_type, walk_random())


# ── Check-In ───────────────────────────────────────────────────────────────

def checkin_reaction(done_count: int, completed_items: list[str]) -> str:
    if done_count == 6:
        return (
            "Someone just completed ALL 6 of their daily health habits: "
            "walk, water, protein, workout, sleep, and vegetables. "
            "React with full character energy — this is a massive achievement. 2-3 sentences."
        )
    items = ", ".join(completed_items) if completed_items else "none yet"
    return (
        f"Someone has completed {done_count} out of 6 daily health habits today "
        f"({items}). React in character to keep them going. "
        f"Don't list what they missed — just encourage forward momentum. 2 sentences."
    )


# ── Goals ──────────────────────────────────────────────────────────────────

def hype_goals(goals: list[str]) -> str:
    filled = [g for g in goals if g.strip()]
    if not filled:
        return "Someone wants motivation for their fitness goals. Hype them up in character. 3 sentences."
    listed = " | ".join(f'"{g}"' for g in filled)
    return (
        f"Someone just set these fitness goals for today: {listed}. "
        f"Respond in your full character voice. Hype them up to crush every single one. "
        f"Make it personal and specific to THEIR goals. 3 sentences."
    )
