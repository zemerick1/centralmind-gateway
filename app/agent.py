"""
Simple, observable LLM agent for CentralMind Gateway.
Uses LiteLLM for multi-provider support + tool calling.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import litellm
from app.config import settings
from app.tools.aruba import centralmind_client
from app.tools.output import post_to_webhook, post_to_slack

logger = logging.getLogger(__name__)

# Enable LiteLLM debug if needed
litellm.set_verbose = settings.log_level.upper() == "DEBUG"


SYSTEM_PROMPT = """You are a helpful, precise network operations assistant for HPE Aruba Central.

You have access to powerful tools:
- Aruba Central via CentralMind MCP (search + execute)
- Posting to notification channels (Teams, Slack, webhooks)

Rules:
1. Always be factual and cite what you queried.
2. Default to readonly operations unless explicitly told otherwise.
3. When posting notifications, make them clear, actionable, and include key details.
4. If you need more data from Aruba Central, use the search/execute tools first.
5. Keep responses concise but complete.

Current context will be provided with each request.
"""


async def run_agent(
    user_prompt: str,
    context: Optional[Dict[str, Any]] = None,
    available_tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run a single-turn agent with tool calling.
    Returns the final answer + any side effects (e.g. posts made).
    """
    context = context or {}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context: {json.dumps(context, default=str)}\n\nTask: {user_prompt}"}
    ]

    # Define available tools for the LLM
    tools = [
        {
            "type": "function",
            "function": {
                "name": "aruba_search",
                "description": "Search Aruba Central OpenAPI spec using JavaScript code (returns matching endpoints)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "JavaScript function that explores spec.paths"}
                    },
                    "required": ["code"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "aruba_execute",
                "description": "Execute a live Aruba Central API call using JavaScript (respects readonly mode)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "JavaScript using central.request({...})"}
                    },
                    "required": ["code"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "post_notification",
                "description": "Post a message to the primary output channel (Teams/Slack/webhook)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "title": {"type": "string", "description": "Optional title for Teams"}
                    },
                    "required": ["text"]
                }
            }
        },
    ]

    try:
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        results = []
        final_text = message.content or ""

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            logger.info(f"Agent calling tool: {func_name} with args: {args}")

            if func_name == "aruba_search":
                result = await centralmind_client.call_tool("search_central", {"code": args["code"]})
            elif func_name == "aruba_execute":
                result = await centralmind_client.call_tool("execute_central", {"code": args["code"]})
            elif func_name == "post_notification":
                result = await post_to_webhook({"text": args["text"]}, title=args.get("title"))
                # Also try Slack if configured
                if settings.slack_webhook_url:
                    await post_to_slack(args["text"])
            else:
                result = {"error": f"Unknown tool {func_name}"}

            results.append({"tool": func_name, "result": result})

            # Feed result back to LLM for final answer (optional second turn)
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)[:4000]  # truncate if huge
            })

        # Final LLM pass if we used tools
        if tool_calls:
            final_response = await litellm.acompletion(
                model=settings.llm_model,
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            )
            final_text = final_response.choices[0].message.content or final_text

        return {
            "final_answer": final_text,
            "tool_results": results,
            "model": settings.llm_model,
        }

    except Exception as e:
        logger.exception("Agent run failed")
        return {
            "final_answer": f"Error processing request: {str(e)}",
            "tool_results": [],
            "error": str(e)
        }
