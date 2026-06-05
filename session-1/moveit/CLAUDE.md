# MoveIt — Claude Code Instructions

## What this is
A Streamlit + LangChain fitness accountability app with AI-powered companions.
Users pick a personality (Simon Sinek, Gordon Ramsay, Golden Retriever, etc.) or create
a custom one, then get personalised motivation throughout their day.

## Stack
- **UI**: Streamlit (single-page app with screen routing via `st.session_state.screen`)
- **AI**: LangChain + ChatAnthropic (`langchain-anthropic`)
- **Model**: `claude-sonnet-4-5` via `utils/chain.py`
- **State**: All state lives in `st.session_state` (see `utils/state.py`)

## Project structure
```
app.py                  ← Entry point, routes to screens
pages/
  onboard_goals.py      ← Step 1: user sets fitness goals
  pick_companion.py     ← Step 2: user picks companion
  ready.py              ← Step 3: companion meets user
  home.py               ← Main daily hub
  walk.py               ← Walk mode with timer + prompts
  checkin.py            ← Daily habit check-in
  goals.py              ← Update goals + get hyped
utils/
  companions.py         ← All companion definitions + get_companion()
  chain.py              ← LangChain chain builder + run/stream helpers
  prompts.py            ← All prompt templates
  state.py              ← Session state init + navigation helpers
  styles.py             ← CSS injection + reusable HTML components
.streamlit/
  secrets.toml          ← ANTHROPIC_API_KEY goes here
  config.toml           ← Theme + server config
requirements.txt
```

## Running locally
```bash
pip install -r requirements.txt
# Add your key to .streamlit/secrets.toml
streamlit run app.py
```

## Key patterns

### Navigation
Use `go(screen_name)` from `utils/state.py` — it sets `st.session_state.screen` and calls `st.rerun()`.
Never use `st.switch_page()` — this is a single-file app with manual routing.

### AI responses
- `run_companion(persona, prompt)` — synchronous, returns string
- `stream_companion(persona, prompt)` — generator, use with a `st.empty()` placeholder
- Always get persona from `get_companion()` in `utils/companions.py`
- All prompt strings live in `utils/prompts.py`

### Adding a new companion
Add a new entry to the `COMPANIONS` dict in `utils/companions.py` following the existing pattern.
Assign it to one of the existing categories: Motivators, Late Night, TV Characters, Animals.

### Adding a new screen
1. Create `pages/my_screen.py` with a `render()` function
2. Add the route to `app.py`
3. Add navigation buttons using `go("my_screen")` or `st.session_state.screen = "my_screen"`

### Caching AI messages
Each screen has a corresponding `_message` key in session state (e.g. `home_message`).
Set it to `""` to force a refresh on next render.

## Secrets
`ANTHROPIC_API_KEY` must be in `.streamlit/secrets.toml` (local) or Streamlit Cloud secrets.

## Deployment (Streamlit Cloud)
1. Push to GitHub
2. Connect repo at share.streamlit.io
3. Add `ANTHROPIC_API_KEY` in the secrets panel
4. Deploy — it picks up `app.py` automatically
