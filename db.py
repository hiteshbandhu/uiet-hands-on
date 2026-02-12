"""SQLite database for tasks, habits, and expenses."""
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_PATH = Path(__file__).parent / "data" / "assistant.db"


def get_user_local_now(user_id: int) -> datetime:
    """Get current datetime in user's local timezone."""
    tz_str = get_user_timezone_or_utc(user_id)
    return datetime.now(ZoneInfo(tz_str))


def get_user_local_date(user_id: int) -> str:
    """Get today's date (YYYY-MM-DD) in user's timezone."""
    return get_user_local_now(user_id).strftime("%Y-%m-%d")


def _get_utc_range_for_local_date(user_id: int, date_str: str) -> tuple[str, str]:
    """Get (start_utc, end_utc) ISO range for a local date in user's timezone."""
    tz_str = get_user_timezone_or_utc(user_id)
    tz = ZoneInfo(tz_str)
    start_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    from datetime import timedelta
    end_local = start_local + timedelta(days=1) - timedelta(microseconds=1)
    start_utc = start_local.astimezone(ZoneInfo("UTC")).isoformat()
    end_utc = end_local.astimezone(ZoneInfo("UTC")).isoformat()
    return (start_utc, end_utc)


def get_connection():
    """Get a database connection, creating the DB file if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                deadline TEXT NOT NULL,
                reminder_sent INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                frequency TEXT DEFAULT 'daily',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                expense_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                last_habit_reminder_date TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


# --- User settings ---

def get_user_timezone(user_id: int) -> str | None:
    """Get user's timezone (IANA, e.g. Asia/Kolkata). Returns None if not set."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT timezone FROM user_settings WHERE user_id = ? AND timezone != 'UTC'",
            (user_id,),
        ).fetchone()
        return row["timezone"] if row else None
    finally:
        conn.close()


def set_user_timezone(user_id: int, timezone: str) -> None:
    """Set user's timezone. Creates or updates user_settings."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO user_settings (user_id, timezone, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET timezone = ?, updated_at = ?""",
            (user_id, timezone, now, timezone, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_settings(user_id: int) -> dict | None:
    """Get full user settings row, or None if not set."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_timezone_or_utc(user_id: int) -> str:
    """Get user's timezone, or 'UTC' if not set."""
    tz = get_user_timezone(user_id)
    return tz if tz else "UTC"


def get_last_habit_reminder_date(user_id: int) -> str | None:
    """Get the last date (YYYY-MM-DD) we sent habit reminder to this user."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT last_habit_reminder_date FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["last_habit_reminder_date"] if row and row["last_habit_reminder_date"] else None
    finally:
        conn.close()


def set_last_habit_reminder_date(user_id: int, date_str: str) -> None:
    """Record that we sent habit reminder on this date (user's local)."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        existing = conn.execute("SELECT 1 FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE user_settings SET last_habit_reminder_date = ?, updated_at = ? WHERE user_id = ?",
                (date_str, now, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO user_settings (user_id, timezone, last_habit_reminder_date, updated_at) VALUES (?, 'UTC', ?, ?)",
                (user_id, date_str, now),
            )
        conn.commit()
    finally:
        conn.close()


# --- Tasks ---

def _deadline_local_to_utc(deadline_iso: str, timezone_str: str) -> str:
    """Convert deadline from user's local time to UTC. Returns UTC ISO string."""
    from zoneinfo import ZoneInfo
    # Parse as naive datetime in user's timezone
    dt_local = datetime.fromisoformat(deadline_iso.replace("Z", "+00:00"))
    if dt_local.tzinfo is not None:
        # Already has TZ, convert to UTC
        return dt_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")
    tz = ZoneInfo(timezone_str)
    dt_aware = dt_local.replace(tzinfo=tz)
    return dt_aware.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def add_task(user_id: int, title: str, deadline: str, timezone_override: str | None = None) -> dict:
    """Add a task. deadline is ISO 8601 in user's LOCAL time; we convert to UTC for storage."""
    conn = get_connection()
    try:
        tz = timezone_override or get_user_timezone_or_utc(user_id)
        try:
            deadline_utc = _deadline_local_to_utc(deadline, tz)
        except Exception:
            deadline_utc = deadline.replace("Z", "").strip()[:19]  # Fallback: use as-is

        cur = conn.execute(
            "INSERT INTO tasks (user_id, title, deadline, created_at) VALUES (?, ?, ?, ?)",
            (user_id, title, deadline_utc, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_tasks(user_id: int, include_past: bool = False) -> list[dict]:
    """List tasks for a user. By default only upcoming."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        if include_past:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND deadline >= ? ORDER BY deadline ASC",
                (user_id, now),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_task(user_id: int, task_id: int) -> bool:
    """Delete a task if it belongs to the user. Returns True if deleted."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_tasks_for_reminder() -> list[dict]:
    """Get tasks due within the next hour that haven't been reminded."""
    conn = get_connection()
    try:
        now = datetime.utcnow()
        from datetime import timedelta
        window_end = (now + timedelta(hours=1)).isoformat()
        now_str = now.isoformat()
        rows = conn.execute(
            """SELECT * FROM tasks 
               WHERE deadline >= ? AND deadline <= ? AND reminder_sent = 0
               ORDER BY deadline ASC""",
            (now_str, window_end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_task_reminder_sent(task_id: int):
    """Mark a task as having had its reminder sent."""
    conn = get_connection()
    try:
        conn.execute("UPDATE tasks SET reminder_sent = 1 WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


# --- Habits ---

def add_habit(user_id: int, name: str, frequency: str = "daily") -> dict:
    """Add a habit."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO habits (user_id, name, frequency, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, frequency, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM habits WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_habits(user_id: int) -> list[dict]:
    """List habits for a user with streak info."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM habits WHERE user_id = ? ORDER BY name",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            h = dict(r)
            h["streak"] = get_habit_streak_count(r["id"])
            result.append(h)
        return result
    finally:
        conn.close()


def get_habit_by_id_or_name(user_id: int, habit_id: int | None = None, name: str | None = None) -> dict | None:
    """Get a habit by id or name. Returns None if not found."""
    conn = get_connection()
    try:
        if habit_id:
            row = conn.execute("SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id)).fetchone()
        elif name:
            row = conn.execute(
                "SELECT * FROM habits WHERE LOWER(name) = LOWER(?) AND user_id = ?",
                (name.strip(), user_id),
            ).fetchone()
        else:
            return None
        return dict(row) if row else None
    finally:
        conn.close()


def complete_habit(habit_id: int, user_id: int) -> bool:
    """Record a habit completion for today (user's local date). Returns True if recorded."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id)).fetchone()
        if not row:
            return False
        today_local = get_user_local_date(user_id)
        start_utc, end_utc = _get_utc_range_for_local_date(user_id, today_local)
        # Avoid duplicate for same day in user's timezone
        existing = conn.execute(
            """SELECT 1 FROM habit_completions
               WHERE habit_id = ? AND completed_at >= ? AND completed_at <= ?""",
            (habit_id, start_utc, end_utc),
        ).fetchone()
        if existing:
            return True  # Already completed today
        conn.execute(
            "INSERT INTO habit_completions (habit_id, completed_at) VALUES (?, ?)",
            (habit_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_habit_streak_count(habit_id: int) -> int:
    """Get current streak (consecutive days with completion)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT date(completed_at) as d FROM habit_completions 
               WHERE habit_id = ? ORDER BY d DESC""",
            (habit_id,),
        ).fetchall()
        if not rows:
            return 0
        dates = [r["d"] for r in rows]
        streak = 0
        prev = None
        for d in dates:
            if prev is None:
                prev = datetime.fromisoformat(d)
                streak = 1
                continue
            curr = datetime.fromisoformat(d)
            delta = (prev - curr).days
            if delta == 1:
                streak += 1
                prev = curr
            else:
                break
        return streak
    finally:
        conn.close()


def get_habits_without_completion_today(user_id: int) -> list[dict]:
    """Get habits that have no completion recorded for today (user's local date)."""
    conn = get_connection()
    try:
        today_local = get_user_local_date(user_id)
        start_utc, end_utc = _get_utc_range_for_local_date(user_id, today_local)
        rows = conn.execute(
            """SELECT h.* FROM habits h
               WHERE h.user_id = ?
               AND NOT EXISTS (
                 SELECT 1 FROM habit_completions c
                 WHERE c.habit_id = h.id AND c.completed_at >= ? AND c.completed_at <= ?
               )""",
            (user_id, start_utc, end_utc),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_users_with_incomplete_habits_today() -> dict[int, list[dict]]:
    """Get user_id -> list of habits without completion today (each user's local date)."""
    conn = get_connection()
    try:
        # Get all habits with their user_id
        habits = conn.execute("SELECT * FROM habits").fetchall()
        by_user = {}
        for r in habits:
            uid = r["user_id"]
            today_local = get_user_local_date(uid)
            start_utc, end_utc = _get_utc_range_for_local_date(uid, today_local)
            has_completion = conn.execute(
                """SELECT 1 FROM habit_completions c
                   WHERE c.habit_id = ? AND c.completed_at >= ? AND c.completed_at <= ?""",
                (r["id"], start_utc, end_utc),
            ).fetchone()
            if not has_completion:
                if uid not in by_user:
                    by_user[uid] = []
                by_user[uid].append(dict(r))
        return by_user
    finally:
        conn.close()


# --- Expenses ---

def add_expense(user_id: int, amount: float, category: str, description: str | None = None, expense_date: str | None = None) -> dict:
    """Add an expense. expense_date defaults to today in YYYY-MM-DD."""
    date_str = expense_date or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, expense_date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount, category, description or "", date_str, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_expenses(user_id: int, period: str = "week") -> list[dict]:
    """List expenses for a user. period: today, week, month."""
    conn = get_connection()
    try:
        now = datetime.utcnow()
        if period == "today":
            start = now.strftime("%Y-%m-%d")
            end = start
        elif period == "week":
            from datetime import timedelta
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
        elif period == "month":
            from datetime import timedelta
            start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
        else:
            start, end = "1970-01-01", now.strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND expense_date >= ? AND expense_date <= ? ORDER BY expense_date DESC, id DESC",
            (user_id, start, end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_spending_by_category(user_id: int, period: str = "week") -> dict[str, float]:
    """Get total spending per category for a user."""
    expenses = list_expenses(user_id, period)
    by_cat = {}
    for e in expenses:
        cat = e["category"].lower().strip()
        by_cat[cat] = by_cat.get(cat, 0) + float(e["amount"])
    return by_cat


def get_expense_totals_by_day(user_id: int, days: int = 14) -> list[tuple[str, float]]:
    """Get daily expense totals for the last N days. Returns [(date, total), ...]."""
    conn = get_connection()
    try:
        from datetime import timedelta
        start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT expense_date as d, SUM(amount) as total
               FROM expenses WHERE user_id = ? AND expense_date >= ?
               GROUP BY expense_date ORDER BY d""",
            (user_id, start),
        ).fetchall()
        return [(r["d"], float(r["total"])) for r in rows]
    finally:
        conn.close()
