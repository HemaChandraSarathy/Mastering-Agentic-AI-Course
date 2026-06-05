# MoveIt 💪 — Fitness Accountability App

Your AI-powered fitness companion. Pick your personality — Simon Sinek, Gordon Ramsay, Leslie Knope, a Golden Retriever — and get personalised motivation all day.

Built with **Streamlit** + **LangChain** + **Anthropic Claude**.

---

## Features

- 🎯 **Goal onboarding** — set your focus areas and specific daily goals
- 🎭 **13 companion personalities** — preset celebs/characters + fully custom
- 🚶 **Walk mode** — real-time motivation with prompt chips
- ✅ **Daily check-in** — 6 habits tracked with companion reactions
- 🔥 **Goal hype** — companion fires you up around your specific goals
- 📺 **Streaming responses** — text streams token by token, just like chat

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your API key
Edit `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

### 3. Run
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`

---

## Project Structure

```
moveit/
├── app.py                    # Entry point + screen router
├── requirements.txt
├── CLAUDE.md                 # Instructions for Claude Code
├── README.md
├── .streamlit/
│   ├── config.toml           # Theme + server config
│   └── secrets.toml          # API key (never commit)
├── pages/
│   ├── onboard_goals.py      # Step 1: set goals
│   ├── pick_companion.py     # Step 2: pick companion
│   ├── ready.py              # Step 3: first meeting
│   ├── home.py               # Daily hub
│   ├── walk.py               # Walk mode
│   ├── checkin.py            # Habit check-in
│   └── goals.py              # Update goals
└── utils/
    ├── companions.py         # Companion definitions
    ├── chain.py              # LangChain chain builder
    ├── prompts.py            # All prompt templates
    ├── state.py              # Session state helpers
    └── styles.py             # CSS + HTML components
```

---

## Companions

| Category | Companions |
|---|---|
| Motivators | Simon Sinek, Oprah Winfrey, Gordon Ramsay |
| Late Night | Trevor Noah, Jimmy Kimmel, Jimmy Fallon |
| TV Characters | Lorelai Gilmore, Rachel Green, Marshall Eriksen, Leslie Knope, Ted Lasso |
| Animals | Golden Retriever Buddy, Judgmental Cat |
| Custom | Type anyone — The Rock, Hermione, your mom... |

---

## Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Point to `app.py`
4. Add `ANTHROPIC_API_KEY` in the Secrets panel
5. Deploy 🚀

---

## Extending

**Add a companion** → edit `utils/companions.py`, add entry to `COMPANIONS` dict.

**Add a screen** → create `pages/new_screen.py` with `render()`, add route in `app.py`.

**Change the model** → edit `model=` in `utils/chain.py`.
