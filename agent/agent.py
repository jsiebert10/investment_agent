import json
import os

import anthropic
from dotenv import load_dotenv

from agent.tools import analyze_sentiment, get_stock_data, nyt_search

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Definición de tools para Claude ──────────────────────────
# Esto es el "contrato": le dices a Claude qué tools existen,
# qué hacen, y qué parámetros esperan. Claude nunca ve el código.

TOOLS = [
    {
        "name": "nyt_search",
        "description": "Search recent New York Times articles about a company or ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. AAPL",
                },
                "company_name": {
                    "type": "string",
                    "description": "Company name, e.g. Apple",
                },
            },
            "required": ["ticker", "company_name"],
        },
    },
    {
        "name": "get_stock_data",
        "description": "Get current price, financial metrics and analyst recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. AAPL",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "analyze_sentiment",
        "description": "Analyze the sentiment of a list of news articles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "description": "List of articles with headline and snippet",
                    "items": {"type": "object"},
                }
            },
            "required": ["articles"],
        },
    },
]

# ── El dispatcher: conecta nombre → función real ──────────────

TOOL_FUNCTIONS = {
    "nyt_search": nyt_search,
    "get_stock_data": get_stock_data,
    "analyze_sentiment": analyze_sentiment,
}


def run_tool(name: str, inputs: dict) -> str:
    """Runs the tool and returns the result as a JSON string."""
    try:
        func = TOOL_FUNCTIONS[name]
        result = func(**inputs)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_agent(ticker: str, company_name: str, on_tool_call=None) -> str:
    """
    Runs the full agent for a given ticker.
    on_tool_call: optional callback to show progress in the UI.
    """
    from agent.prompts import SYSTEM_PROMPT

    messages = [
        {
            "role": "user",
            "content": f"Analyze {ticker} ({company_name}) as an investment opportunity.",
        }
    ]

    print(f"\n[Agent] Analyzing {ticker}...\n")

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "No response."

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Tool] Calling {block.name} with {block.input}")

                    if on_tool_call:
                        on_tool_call(block.name, block.input)

                    result = run_tool(block.name, block.input)
                    print(f"[Tool] Result: {result[:120]}...\n")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
