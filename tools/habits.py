"""Habit-related tools for the LLM."""
import db

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_habit",
            "description": "Create a new habit to track. Use when the user wants to start or track a new habit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the habit (e.g. 'meditation', 'running')"},
                    "frequency": {
                        "type": "string",
                        "description": "How often: 'daily' or 'weekly'. Default daily.",
                        "default": "daily",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_habits",
            "description": "List the user's habits with their current streak. Use when they ask about their habits.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_habit",
            "description": "Mark a habit as done for today. Use when the user says they did it (e.g. 'I ran today', 'did meditation').",
            "parameters": {
                "type": "object",
                "properties": {
                    "habit_id": {"type": "integer", "description": "ID from list_habits. Prefer this if known."},
                    "name": {"type": "string", "description": "Habit name if habit_id not available. Use fuzzy match."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_habit_streak",
            "description": "Get the current streak for a habit. Use when the user asks how long their streak is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "habit_id": {"type": "integer", "description": "The habit ID from list_habits"},
                },
                "required": ["habit_id"],
            },
        },
    },
]


def execute_habit_tool(tool_name: str, arguments: dict, user_id: int):
    """Execute a habit tool and return the result."""
    if tool_name == "add_habit":
        row = db.add_habit(
            user_id=user_id,
            name=arguments["name"],
            frequency=arguments.get("frequency", "daily"),
        )
        return {"success": True, "habit": dict(row), "message": f"Added habit: {row['name']}"}

    if tool_name == "list_habits":
        habits = db.list_habits(user_id)
        return {"habits": habits, "count": len(habits)}

    if tool_name == "complete_habit":
        habit_id = arguments.get("habit_id")
        name = arguments.get("name")
        if not habit_id and not name:
            return {"success": False, "error": "Need habit_id or name"}
        habit = db.get_habit_by_id_or_name(user_id, habit_id=habit_id, name=name)
        if not habit:
            return {"success": False, "error": f"Habit not found (id={habit_id}, name={name})"}
        ok = db.complete_habit(habit["id"], user_id)
        return {"success": True, "habit": habit["name"], "message": f"Marked {habit['name']} as done for today"}

    if tool_name == "get_habit_streak":
        habit_id = arguments.get("habit_id")
        if not habit_id:
            return {"success": False, "error": "habit_id required"}
        habit = db.get_habit_by_id_or_name(user_id, habit_id=habit_id)
        if not habit:
            return {"success": False, "error": f"Habit {habit_id} not found"}
        streak = db.get_habit_streak_count(habit_id)
        return {"habit": habit["name"], "streak": streak}

    raise ValueError(f"Unknown habit tool: {tool_name}")
