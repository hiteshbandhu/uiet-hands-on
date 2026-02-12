"""Task-related tools for the LLM."""
import db

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a new task with a deadline. Use when the user wants to record, add, or get a reminder for a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short description of the task"},
                    "deadline": {
                        "type": "string",
                        "description": "Deadline in ISO 8601 format (e.g. 2025-02-13T17:00:00). Parse natural language like 'tomorrow 5pm' into ISO.",
                    },
                },
                "required": ["title", "deadline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List the user's upcoming tasks. Use when they ask what tasks they have, what's due, or what's coming up.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete or remove a task. Use when the user wants to cancel or remove a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The ID of the task to delete (from list_tasks)"},
                },
                "required": ["task_id"],
            },
        },
    },
]


def execute_task_tool(tool_name: str, arguments: dict, user_id: int):
    """Execute a task tool and return the result."""
    if tool_name == "add_task":
        row = db.add_task(
            user_id=user_id,
            title=arguments["title"],
            deadline=arguments["deadline"],
        )
        return {"success": True, "task": dict(row), "message": f"Added task: {row['title']} (due {row['deadline']})"}

    if tool_name == "list_tasks":
        tasks = db.list_tasks(user_id)
        return {"tasks": tasks, "count": len(tasks)}

    if tool_name == "delete_task":
        deleted = db.delete_task(user_id, arguments["task_id"])
        return {"success": deleted, "message": "Task deleted" if deleted else "Task not found or already deleted"}

    raise ValueError(f"Unknown task tool: {tool_name}")
