"""
CentralMind Gateway - Refactored
The gateway's LLM now directly uses tools exposed by centralmind.
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

import httpx
import litellm
from fastapi import FastAPI

from config import settings
from mcp_client import mcp

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

litellm.set_verbose = settings.log_level.upper() == "DEBUG"


def format_tool_result(tool_name: str, result: Any) -> str:
    """Format tool results nicely for the LLM, especially errors."""
    if isinstance(result, dict) and "error" in result:
        error_msg = result.get("error", "Unknown error")
        return f"Tool '{tool_name}' failed with error: {error_msg}"

    if isinstance(result, dict):
        if result.get("status_code") in (404, 403, 401):
            return (
                f"Tool '{tool_name}' returned HTTP {result.get('status_code')}. "
                f"This endpoint may not exist for this device or monitoring may not be enabled. "
                f"Try a different related endpoint or broaden the search."
            )

    try:
        formatted = json.dumps(result, default=str, indent=2)
        if len(formatted) > 3500:
            formatted = formatted[:3500] + "\n... [truncated]"
        return formatted
    except Exception:
        return str(result)[:3500]


SYSTEM_PROMPT = """You are a precise infrastructure event processor.

Your job is to investigate alerts by finding **concrete, current data** about the reported issue — not just general API discovery.

Investigation Priorities:
- When given a device serial or name, prioritize finding recent events, alerts, or health data for that specific device.
- Look for endpoints that can show the **current state** of the reported problem (e.g. inconsistent ports, STP status, port configuration, recent topology changes).
- After using `search_*` tools, move quickly to `execute_*` calls on the most relevant endpoints.
- If initial queries return limited data or errors, try related areas (events, alerts, device health, port status, recent changes).
- Do not stop at high-level summaries. Attempt to identify the specific port/interface involved and its current settings when possible.
- Synthesize findings into clear root cause, impact, and actionable recommendations.

Be thorough. The goal is to explain **why** the inconsistency exists based on actual data from the device/platform.
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CentralMind Gateway...")
    await mcp.discover_tools()
    yield
    logger.info("Gateway shutdown complete.")


app = FastAPI(
    title="CentralMind Gateway",
    description="Webhook event processor using CentralMind MCP tools",
    version="0.3.0",
    lifespan=lifespan,
)


def get_llm_tools() -> list:
    """Build LLM tool definitions from centralmind + local tools."""
    tools = []

    # Add all tools discovered from centralmind
    for tool_name, tool_def in mcp._available_tools.items():
        tools.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_def.description or f"Tool: {tool_name}",
                "parameters": tool_def.inputSchema or {"type": "object", "properties": {}},
            }
        })

    # Add structured post_notification tool (some fields optional)
    tools.append({
        "type": "function",
        "function": {
            "name": "post_notification",
            "description": "Post a structured notification after completing investigation",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short, clear title for the alert"
                    },
                    "summary": {
                        "type": "string",
                        "description": "One-sentence summary of the issue"
                    },
                    "investigation_summary": {
                        "type": "string",
                        "description": "Key findings from the investigation"
                    },
                    "root_cause": {
                        "type": "string",
                        "description": "Likely root cause based on the data gathered (best effort is acceptable)"
                    },
                    "impact": {
                        "type": "string",
                        "description": "Impact assessment (e.g. Low / Medium / High, client impact)"
                    },
                    "recommended_actions": {
                        "type": "string",
                        "description": "Clear, actionable next steps"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                        "description": "Severity level of the issue"
                    }
                },
                "required": ["title", "summary", "investigation_summary"]
            },
        }
    })

    return tools


async def post_to_webhook(text: str, title: str | None = None) -> Dict[str, Any]:
    if not settings.output_webhook_url:
        return {"status": "logged", "reason": "no output_webhook_url configured"}

    payload = {"text": text}
    if title:
        payload["title"] = title

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.output_webhook_url, json=payload)
            return {"status": "success", "status_code": resp.status_code}
    except Exception as e:
        logger.error(f"Failed to post to webhook: {e}")
        return {"status": "failed", "error": str(e)}


async def run_event_processor(context: Dict[str, Any]) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Incoming event:\n{json.dumps(context, default=str, indent=2)}"},
    ]

    tools = get_llm_tools()
    max_iterations = 15
    iteration = 0
    final_text = ""

    while iteration < max_iterations:
        iteration += 1

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

            if not tool_calls:
                final_text = message.content or ""
                break

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls
            })

            for tool_call in tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")

                logger.info(f"[Iteration {iteration}] Tool called: {func_name}")

                if func_name == "post_notification":
                    title = args.get("title", "Infrastructure Alert")
                    summary = args.get("summary", "")
                    investigation = args.get("investigation_summary", "")
                    root_cause = args.get("root_cause", "")
                    impact = args.get("impact", "")
                    actions = args.get("recommended_actions", "")
                    severity = args.get("severity", "Medium")

                    notification_text = f"""**{title}** (Severity: {severity})

**Summary**: {summary}

**Investigation**:
{investigation}

**Root Cause**: {root_cause}

**Impact**: {impact}

**Recommended Actions**:
{actions}
"""
                    result = await post_to_webhook(notification_text, title)
                    logger.info(f"=== LLM Output ===\n{notification_text}\n==================")

                    return {
                        "final_answer": notification_text,
                        "iterations_used": iteration,
                    }

                else:
                    result = await mcp.call_tool(func_name, args)
                    formatted_result = format_tool_result(func_name, result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": formatted_result
                    })

        except Exception as e:
            logger.exception(f"Error during iteration {iteration}")
            return {"error": str(e)}

    if iteration >= max_iterations:
        logger.warning("Reached maximum tool calling iterations")
        if not final_text:
            final_text = "Investigation stopped after reaching maximum steps."

    return {
        "final_answer": final_text,
        "iterations_used": iteration,
    }


@app.post("/webhook")
async def webhook(payload: Dict[str, Any]):
    logger.info("Received webhook event")

    context = {
        "source": "webhook",
        "payload": payload,
    }

    result = await run_event_processor(context)
    return {"status": "processed", "result": result}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "discovered_tools": list(mcp._available_tools.keys()),
        "llm_model": settings.llm_model,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
