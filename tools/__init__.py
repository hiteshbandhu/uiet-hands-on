"""Tool definitions and execution for LLM function calling."""
import json
from tools.tasks import TOOLS as TASK_TOOLS, execute_task_tool
from tools.habits import TOOLS as HABIT_TOOLS, execute_habit_tool
from tools.money import TOOLS as MONEY_TOOLS, execute_money_tool
from tools.settings import TOOLS as SETTINGS_TOOLS, execute_settings_tool

TOOLS_SCHEMA = TASK_TOOLS + HABIT_TOOLS + MONEY_TOOLS + SETTINGS_TOOLS
AVAILABLE_FUNCTIONS = {
    "add_task": execute_task_tool,
    "list_tasks": execute_task_tool,
    "delete_task": execute_task_tool,
    "add_habit": execute_habit_tool,
    "list_habits": execute_habit_tool,
    "complete_habit": execute_habit_tool,
    "get_habit_streak": execute_habit_tool,
    "add_expense": execute_money_tool,
    "list_expenses": execute_money_tool,
    "get_spending_summary": execute_money_tool,
    "get_recommendations": execute_money_tool,
    "set_timezone": execute_settings_tool,
    "get_timezone": execute_settings_tool,
}


def execute_tool(tool_name: str, arguments: dict, user_id: int) -> str:
    """Execute a tool and return the result as a string."""
    if tool_name not in AVAILABLE_FUNCTIONS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    fn = AVAILABLE_FUNCTIONS[tool_name]
    try:
        result = fn(tool_name, arguments, user_id)
        if isinstance(result, (dict, list)):
            return json.dumps(result, default=str)
        return str(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
