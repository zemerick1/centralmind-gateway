"""
Simple, observable LLM agent for CentralMind Gateway.
Uses LiteLLM for multi-provider support + tool calling.

Design: The gateway does NOT re-define MCP tools. It fetches them
from the CentralMind MCP server at runtime, converts them to OpenAI
function-calling format, and forwards calls back. This keeps the
gateway thin and ensures tool descriptions stay in sync with the
MCP server.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import litellm
from app.config import settings
from app.tools.aruba import centralmind_client

logger = logging.getLogger(__name__)

# Enable LiteLLM debug if needed
litellm.set_verbose = settings.log_level.upper() == "DEBUG"


def _resolve_api_key() -> Optional[str]:
    """Resolve the correct API key for the configured LLM model."""
    model = settings.llm_model.lower()
    if "gemini" in model or "google" in model:
        return settings.gemini_api_key or settings.google_api_key
    elif "xai" in model or "grok" in model:
        return settings.xai_api_key
    elif "anthropic" in model or "claude" in model:
        return settings.anthropic_api_key
    elif "openai" in model or "gpt" in model:
        return settings.openai_api_key
    return None


def _mcp_tool_to_openai(mcp_tool) -> dict:
    """Convert an MCP Tool object to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        }
    }


async def _get_mcp_tools() -> List[dict]:
    """Fetch tool definitions from the CentralMind MCP server."""
    if not centralmind_client.session:
        await centralmind_client.start()

    result = await centralmind_client.session.list_tools()
    return [_mcp_tool_to_openai(t) for t in result.tools]


SYSTEM_PROMPT = """You are a helpful, precise network operations assistant for HPE Aruba Central.

You have tools provided by the CentralMind MCP server. Use them exactly as described.
All code you write MUST be an async arrow function that returns its result.

Rules:
1. Always be factual and cite what you queried.
2. Default to readonly operations unless explicitly told otherwise.
3. Always search for the correct endpoint first before executing.
4. Keep responses concise but complete.
"""


async def run_agent(
    user_prompt: str,
    context: Optional[Dict[str, Any]] = None,
    available_tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run a single-turn agent with tool calling.
    Returns the final answer + any side effects.
    """
    context = context or {}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context: {json.dumps(context, default=str)}\n\nTask: {user_prompt}"}
    ]

    # Fetch tools directly from the MCP server
    tools = await _get_mcp_tools()
    logger.info(f"Loaded {len(tools)} tools from MCP: {[t['function']['name'] for t in tools]}")

    try:
        results = []
        max_iterations = 5

        for iteration in range(max_iterations):
            response = await litellm.acompletion(
                model=settings.llm_model,
                api_key=_resolve_api_key(),
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )

            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            # No tool calls = LLM is done, return final answer
            if not tool_calls:
                return {
                    "final_answer": message.content or "",
                    "tool_results": results,
                    "model": settings.llm_model,
                    "iterations": iteration + 1,
                }

            # Process tool calls and feed results back
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls,
            })

            for tool_call in tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                logger.info(f"Agent [{iteration+1}/{max_iterations}] calling tool: {func_name}")

                result = await centralmind_client.call_tool(func_name, args)
                results.append({"tool": func_name, "result": result})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)[:4000]
                })

        # If we hit max iterations, do one final pass without tools to force a summary
        logger.warning(f"Agent hit max iterations ({max_iterations}), forcing final answer")
        response = await litellm.acompletion(
            model=settings.llm_model,
            api_key=_resolve_api_key(),
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
        )
        final_text = response.choices[0].message.content or ""

        return {
            "final_answer": final_text,
            "tool_results": results,
            "model": settings.llm_model,
            "iterations": max_iterations,
        }

    except Exception as e:
        logger.exception("Agent run failed")
        return {
            "final_answer": f"Error processing request: {str(e)}",
            "tool_results": [],
            "error": str(e)
        }
