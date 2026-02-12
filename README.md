A personal assistant to handle tasks, time, money and habits using Telegram. Uses Groq LLM (gpt-oss-20b) to parse natural language—no slash commands needed.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Add to `.env`:
- `TG_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)

## Run

```bash
python bot.py
```

**Bot:** [@hands_on_uiet_bot](https://t.me/hands_on_uiet_bot) — open in Telegram to chat

## Functional Use Cases :

### Tasks

- Record tasks with dealine
- Reminder for upcoming tasks

## Habits

- Create a new habit
- Follow up for habits

## Money

- Tracking expenses
- Recommendation Engine (if an expense is causing a habit to break or get on a downfall, you will recommend me things to save money or save my habit.)

