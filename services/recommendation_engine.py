"""Recommendation engine: correlate expenses with habit patterns."""
from datetime import datetime, timedelta

import db


def get_recommendations(user_id: int) -> dict:
    """
    Analyze spending and habit patterns, return personalized recommendations.
    Returns: { "recommendations": [...], "spending_summary": {...}, "habit_summary": [...] }
    """
    recommendations = []

    # 1. Spending by category (last 7 vs previous 7 days)
    expenses_7d = db.list_expenses(user_id, "week")
    expenses_14d = db.list_expenses(user_id, "month")  # we'll filter to 14d
    now = datetime.utcnow()
    cutoff_7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    cutoff_14 = (now - timedelta(days=14)).strftime("%Y-%m-%d")

    recent = [e for e in expenses_14d if e["expense_date"] >= cutoff_7]
    previous = [e for e in expenses_14d if cutoff_14 <= e["expense_date"] < cutoff_7]

    def sum_by_category(exp_list):
        by_cat = {}
        for e in exp_list:
            cat = (e["category"] or "other").lower().strip()
            by_cat[cat] = by_cat.get(cat, 0) + float(e["amount"])
        return by_cat

    recent_by_cat = sum_by_category(recent)
    prev_by_cat = sum_by_category(previous)

    # 2. Detect categories that increased
    all_cats = set(recent_by_cat.keys()) | set(prev_by_cat.keys())
    for cat in all_cats:
        r_val = recent_by_cat.get(cat, 0)
        p_val = prev_by_cat.get(cat, 0)
        if p_val > 0 and r_val > p_val * 1.2:  # 20%+ increase
            pct = int((r_val / p_val - 1) * 100)
            recommendations.append(
                f"Spending on '{cat}' increased {pct}% in the last 7 days (vs previous 7). Consider cutting back."
            )

    # 3. Habit completion trends
    habits = db.list_habits(user_id)
    for h in habits:
        streak = h.get("streak", 0)
        if streak == 0 and habits:  # broken streak
            recommendations.append(
                f"Your habit '{h['name']}' has no active streak. Try completing it today to get back on track."
            )

    # 4. Cross-correlation: habit decline + expense increase
    # Simplified: if any habit has streak 0 and we have high spend categories, suggest
    if habits:
        low_streaks = [x for x in habits if x.get("streak", 0) <= 1]
        top_spend = sorted(recent_by_cat.items(), key=lambda t: -t[1])[:3]
        if low_streaks and top_spend:
            habit_names = ", ".join(s["name"] for s in low_streaks[:2])
            top_cat = top_spend[0][0]
            recommendations.append(
                f"While {habit_names} slipped, you spent most on '{top_cat}'. Reducing that could help free up time/money for your habits."
            )

    # 5. Generic if nothing else
    if not recommendations:
        total_7d = sum(recent_by_cat.values())
        if total_7d > 0:
            recommendations.append("Spending looks steady. Keep tracking to spot trends.")
        else:
            recommendations.append("Add some expenses to get personalized savings recommendations.")

    spending_summary = {
        "last_7_days": dict(recent_by_cat),
        "total_7d": sum(recent_by_cat.values()),
    }
    habit_summary = [{"name": h["name"], "streak": h.get("streak", 0)} for h in habits]

    return {
        "recommendations": recommendations,
        "spending_summary": spending_summary,
        "habit_summary": habit_summary,
    }
