"""User settings tools: timezone."""
import db

# Common timezone aliases for user convenience
TZ_ALIASES = {
    "IST": "Asia/Kolkata",
    "EST": "America/New_York",
    "PST": "America/Los_Angeles",
    "CST": "America/Chicago",
    "GMT": "Europe/London",
    "AEST": "Australia/Sydney",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_timezone",
            "description": "Save the user's timezone. Use when they say their timezone, location, or 'I'm in India', 'set timezone to X'. Accepts IANA names (Asia/Kolkata, America/New_York) or common aliases (IST, EST).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone (e.g. Asia/Kolkata, America/New_York) or alias (IST, EST, PST)",
                    },
                },
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timezone",
            "description": "Get the user's current timezone. Call before adding tasks to interpret 'tomorrow 5pm' correctly. Returns None if not set.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _resolve_timezone(tz: str) -> str:
    """Resolve alias to IANA name, validate, return IANA name."""
    tz = (tz or "").strip()
    if not tz:
        raise ValueError("Timezone cannot be empty")
    resolved = TZ_ALIASES.get(tz.upper(), tz)
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(resolved)  # Validate
        return resolved
    except Exception:
        raise ValueError(f"Invalid timezone: {tz}")


def execute_settings_tool(tool_name: str, arguments: dict, user_id: int):
    """Execute a settings tool."""
    if tool_name == "set_timezone":
        try:
            tz = _resolve_timezone(arguments["timezone"])
            db.set_user_timezone(user_id, tz)
            return {"success": True, "timezone": tz, "message": f"Timezone set to {tz}"}
        except ValueError as e:
            return {"success": False, "error": str(e)}

    if tool_name == "get_timezone":
        tz = db.get_user_timezone(user_id)
        return {"timezone": tz, "message": f"Your timezone is {tz}" if tz else "Timezone not set (using UTC). Set it for accurate reminders."}

    raise ValueError(f"Unknown settings tool: {tool_name}")
