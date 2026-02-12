"""User settings tools: timezone and current time."""
from datetime import datetime

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
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in the user's saved timezone, or in a specified timezone. Use whenever the user asks 'what time is it' or for the current time in a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Optional IANA timezone or alias (e.g. Asia/Kolkata, IST). If omitted, use the user's saved timezone or UTC.",
                    }
                },
            },
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


def _get_effective_timezone(user_id: int, tz_override: str | None = None) -> str:
    """Return a valid timezone string using override, user setting, or UTC."""
    if tz_override:
        return _resolve_timezone(tz_override)
    # Prefer the user's explicit timezone; fall back to UTC
    return db.get_user_timezone_or_utc(user_id)


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
        if tz:
            msg = f"Your timezone is {tz}"
        else:
            # Make the implicit UTC default explicit for the model
            msg = "Timezone not set; using UTC by default. Set it for accurate reminders."
        return {"timezone": tz, "message": msg}

    if tool_name == "get_current_time":
        tz = _get_effective_timezone(user_id, arguments.get("timezone"))
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tz))
        # Both machine-friendly and human-friendly formats
        return {
            "timezone": tz,
            "iso": now.isoformat(),
            "formatted": now.strftime("%Y-%m-%d %H:%M"),
        }

    raise ValueError(f"Unknown settings tool: {tool_name}")
