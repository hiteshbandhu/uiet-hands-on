"""Money/expense-related tools for the LLM."""
import db
from services.recommendation_engine import get_recommendations

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Log an expense. Use when the user says they spent money (e.g. 'Spent 50 on food', 'Bought lunch for 20').",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount spent"},
                    "category": {"type": "string", "description": "Category: food, transport, entertainment, shopping, bills, other"},
                    "description": {"type": "string", "description": "Optional note (e.g. 'lunch', 'groceries')"},
                    "expense_date": {"type": "string", "description": "Optional date in YYYY-MM-DD. Default today."},
                },
                "required": ["amount", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_expenses",
            "description": "List expenses for a period. Use when user asks what they spent, expenses for today/week/month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period: today, week, or month",
                        "default": "week",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": "Get spending breakdown by category. Use when user asks for a summary or breakdown of spending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "description": "today, week, or month", "default": "week"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Get personalized savings/habit recommendations. Use when user asks for advice on saving money, what to cut, or how to improve habits.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def execute_money_tool(tool_name: str, arguments: dict, user_id: int):
    """Execute a money tool and return the result."""
    if tool_name == "add_expense":
        row = db.add_expense(
            user_id=user_id,
            amount=float(arguments["amount"]),
            category=arguments["category"],
            description=arguments.get("description"),
            expense_date=arguments.get("expense_date"),
        )
        return {
            "success": True,
            "expense": dict(row),
            "message": f"Logged ${row['amount']} for {row['category']}",
        }

    if tool_name == "list_expenses":
        period = arguments.get("period", "week")
        expenses = db.list_expenses(user_id, period)
        total = sum(float(e["amount"]) for e in expenses)
        return {"expenses": expenses, "period": period, "count": len(expenses), "total": round(total, 2)}

    if tool_name == "get_spending_summary":
        period = arguments.get("period", "week")
        by_cat = db.get_spending_by_category(user_id, period)
        total = sum(by_cat.values())
        return {"by_category": by_cat, "period": period, "total": round(total, 2)}

    if tool_name == "get_recommendations":
        return get_recommendations(user_id)

    raise ValueError(f"Unknown money tool: {tool_name}")
