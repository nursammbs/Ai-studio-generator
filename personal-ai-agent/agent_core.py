from __future__ import annotations

import ast
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Return titles, snippets, and URLs that the user should verify.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Specific search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search",
            "description": "Search public GitHub repositories by topic or keywords.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Repository search keywords"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression. Use this for calculations rather than mental arithmetic.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local time in Makassar, Indonesia (Asia/Makassar).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


_ALLOWED_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)
_MATH_FUNCTIONS = {
    "abs": abs, "min": min, "max": max, "round": round,
    "sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
}
_MATH_CONSTANTS = {"pi": math.pi, "e": math.e}


def calculate(expression: str):
    """Evaluate arithmetic without eval(), imports, attributes, or arbitrary code."""
    if not expression or len(expression) > 200:
        raise ValueError("Expression is empty or too long.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid arithmetic expression.") from exc

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name) and node.id in (_MATH_FUNCTIONS | _MATH_CONSTANTS):
            return _MATH_FUNCTIONS.get(node.id, _MATH_CONSTANTS.get(node.id))
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINARY):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent is too large.")
            value = {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left / right,
                ast.FloorDiv: lambda: left // right,
                ast.Mod: lambda: left % right,
                ast.Pow: lambda: left ** right,
            }[type(node.op)]()
            if isinstance(value, (int, float)) and (abs(value) > 1e100 or (isinstance(value, float) and not math.isfinite(value))):
                raise ValueError("Result is outside the allowed range.")
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _MATH_FUNCTIONS:
            if node.keywords:
                raise ValueError("Named arguments are not supported.")
            args = [visit(arg) for arg in node.args]
            return _MATH_FUNCTIONS[node.func.id](*args)
        raise ValueError("Unsupported expression. Only basic arithmetic and approved math functions are allowed.")

    result = visit(tree)
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("Result is not finite.")
    return result


def web_search(query: str, limit: int = 5):
    query = (query or "").strip()
    if not query:
        return {"error": "Search query is empty."}
    try:
        from ddgs import DDGS
        rows = DDGS().text(query, max_results=max(1, min(limit, 8)))
        return [
            {
                "title": str(row.get("title", "")),
                "url": str(row.get("href", "")),
                "snippet": str(row.get("body", ""))[:1200],
            }
            for row in rows
        ]
    except Exception as exc:
        return {"error": f"Web search failed: {type(exc).__name__}: {exc}"}


def github_search(query: str, limit: int = 5):
    query = (query or "").strip()
    if not query:
        return {"error": "GitHub search query is empty."}
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "per_page": max(1, min(limit, 8))},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Personal-AI-Workbench"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            {
                "name": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "description": (item.get("description") or "")[:800],
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language"),
            }
            for item in payload.get("items", [])
        ]
    except (requests.RequestException, ValueError) as exc:
        return {"error": f"GitHub search failed: {type(exc).__name__}: {exc}"}


def get_current_time():
    return datetime.now(ZoneInfo("Asia/Makassar")).isoformat(timespec="seconds")


def execute_tool(name: str, arguments: dict):
    """Only explicitly registered tools can be run. No shell or arbitrary Python tool."""
    arguments = arguments if isinstance(arguments, dict) else {}
    if name == "calculator":
        return {"result": calculate(str(arguments.get("expression", "")))}
    if name == "web_search":
        return web_search(str(arguments.get("query", "")))
    if name == "github_search":
        return github_search(str(arguments.get("query", "")))
    if name == "get_current_time":
        return {"time": get_current_time(), "timezone": "Asia/Makassar"}
    return {"error": f"Tool not allowed: {name}"}


def run_agent(messages: list[dict], base_url: str, model: str, max_rounds: int = 4):
    """Call Ollama's chat API with a bounded tool-calling loop. Mutates messages by appending turns."""
    if not model.strip():
        raise ValueError("Enter a model name in the sidebar.")
    endpoint = base_url.rstrip("/") + "/api/chat"
    tools_used = []
    for _ in range(max(1, min(max_rounds, 6))):
        try:
            response = requests.post(
                endpoint,
                json={"model": model, "messages": messages, "tools": TOOL_SCHEMAS, "stream": False},
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                "Could not reach Ollama. Check that Ollama is running, the URL is correct, "
                "and the model is downloaded. Details: " + str(exc)
            ) from exc
        except ValueError as exc:
            raise RuntimeError("Ollama returned an invalid response.") from exc

        assistant_message = payload.get("message") or {}
        messages.append(assistant_message)
        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            return str(assistant_message.get("content", "")).strip(), tools_used

        for call in tool_calls:
            fn = call.get("function") or {}
            name = str(fn.get("name", ""))
            arguments = fn.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            result = execute_tool(name, arguments)
            tools_used.append({"name": name, "arguments": arguments, "result": result})
            messages.append({
                "role": "tool",
                "tool_name": name,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # One final model turn after the bounded tool-call rounds.
    try:
        response = requests.post(
            endpoint, json={"model": model, "messages": messages, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        assistant_message = payload.get("message") or {}
        messages.append(assistant_message)
        return str(assistant_message.get("content", "")).strip(), tools_used
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError("The model could not finish its response: " + str(exc)) from exc
