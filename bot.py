"""
Telegram personal assistant bot.
Uses Groq LLM (gpt-oss-20b) to parse natural language and call tools.
"""
import asyncio
import json
import logging

from groq import Groq
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import config
import db
from tools import TOOLS_SCHEMA, execute_tool

# Verbose logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)
log = logging.getLogger("bot")

# Initialize
db.init_db()
groq_client = Groq(api_key=config.GROQ_API_KEY)

SYSTEM_PROMPT = """You are a helpful personal assistant for tasks, habits, and money tracking.
The user talks to you in natural language. Use the available tools to:

Tasks: add_task, list_tasks, delete_task. For dates use ISO 8601 (e.g. "tomorrow 5pm" -> 2025-02-13T17:00:00).
Habits: add_habit, list_habits, complete_habit, get_habit_streak. Use complete_habit when they say they did something (e.g. "I ran today", "did meditation").
Money: add_expense, list_expenses, get_spending_summary, get_recommendations. Use add_expense when they log spending (e.g. "Spent 50 on food"). Use get_recommendations for savings advice.

When adding a habit, use add_habit with name and optional frequency (daily/weekly).
When they say they completed a habit, use complete_habit with name or habit_id.
For expenses, infer category (food, transport, entertainment, shopping, bills, other) from context.

Be concise and friendly. After calling a tool, summarize the result for the user."""

MAX_TOOL_ITERATIONS = 5


def run_llm_loop(user_id: int, user_message: str) -> str:
    """Run the LLM + tool loop until we get a final reply."""
    log.info("Processing message from user %s: %r", user_id, user_message[:80] + ("..." if len(user_message) > 80 else ""))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = groq_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if msg.content and not msg.tool_calls:
            return msg.content

        if not msg.tool_calls:
            return msg.content or "Sorry, I couldn't process that."

        messages.append(msg)

        for tc in msg.tool_calls:
            log.info("Tool call: %s(%s)", tc.function.name, tc.function.arguments[:100] if tc.function.arguments else "")
            if tc.function.name not in (
                "add_task", "list_tasks", "delete_task",
                "add_habit", "list_habits", "complete_habit", "get_habit_streak",
                "add_expense", "list_expenses", "get_spending_summary", "get_recommendations",
            ):
                continue
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = execute_tool(tc.function.name, args, user_id)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": result,
            })

    return "I hit a limit on processing. Please try again with a simpler request."


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id if update.effective_user else update.message.chat_id
    text = update.message.text.strip()

    # Quick reply for /start
    if text == "/start":
        await update.message.reply_text(
            "Hi! I'm your personal assistant. Tell me in natural language:\n"
            "Tasks: \"Remind me to call mom tomorrow at 5pm\", \"What tasks do I have?\"\n"
            "Habits: \"Start habit meditation\", \"I ran today\", \"What's my streak?\"\n"
            "Money: \"Spent 50 on food\", \"Show my expenses\", \"Give me savings advice\""
        )
        return

    await update.message.chat.send_action("typing")
    reply = await asyncio.to_thread(run_llm_loop, user_id, text)
    await update.message.reply_text(reply)
    log.info("Replied to user %s: %s", user_id, reply[:200] + ("..." if len(reply) > 200 else ""))


async def send_task_reminders(app: Application):
    """Send reminders for tasks due in the next hour."""
    tasks = db.get_tasks_for_reminder()
    if tasks:
        log.info("Sending %d task reminder(s)", len(tasks))
    for t in tasks:
        user_id = t["user_id"]
        try:
            await app.bot.send_message(
                chat_id=user_id,
                text=f"Reminder: {t['title']} is due at {t['deadline']}",
            )
            db.mark_task_reminder_sent(t["id"])
        except Exception:
            pass  # User may have blocked bot; still mark as sent to avoid repeat


async def send_habit_reminders(app: Application):
    """Send daily reminders for habits not completed today."""
    by_user = db.get_all_users_with_incomplete_habits_today()
    if by_user:
        log.info("Sending habit reminders to %d user(s)", len(by_user))
    for user_id, habits in by_user.items():
        if not habits:
            continue
        names = ", ".join(h["name"] for h in habits[:5])
        if len(habits) > 5:
            names += f" and {len(habits) - 5} more"
        try:
            await app.bot.send_message(
                chat_id=user_id,
                text=f"Habit check-in: Did you complete {names} today?",
            )
        except Exception:
            pass


def main():
    if not config.TG_BOT_TOKEN:
        raise ValueError("TG_BOT_TOKEN not set in .env")
    if not config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env")

    # Scheduler for reminders (must start inside event loop)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    async def post_init(app: Application):
        log.info("Starting reminder scheduler (tasks every 15m, habits daily at 9pm)")
        scheduler = AsyncIOScheduler()
        scheduler.add_job(send_task_reminders, "interval", minutes=15, args=[app])
        scheduler.add_job(send_habit_reminders, "cron", hour=21, minute=0, args=[app])  # 9pm daily
        scheduler.start()

    log.info("Building application...")
    app = (
        Application.builder()
        .token(config.TG_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .post_init(post_init)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Connecting to Telegram (this may take a few seconds)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
