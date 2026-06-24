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


SYSTEM_PROMPT = """You are a precise infrastructure event processor.

You have access to MCP tools that let you search infrastructure API specifications and execute live API calls.

When you need more context, use the search and execute tools by providing appropriate JavaScript code.

Be factual. Cite what you queried. Default to read-only operations.

When ready, post a clear actionable notification using the post_notification tool."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CentralMind Gateway...")
    await mcp.start()
    yield
    await mcp.stop()
    logger.info("Gateway shutdown complete.")


app = FastAPI(
    title="CentralMind Gateway",
    description="Minimal webhook event processor using CentralMind MCP",
    version="0.2.0",
    lifespan=lifespan,
)


def get_mcp_tools() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search infrastructure API specs using JavaScript code",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "JavaScript function to explore the spec"}
                    },
                    "required": ["code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute",
                "description": "Execute a live infrastructure API call using JavaScript",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "JavaScript using platform.request(...) style"}
                    },
                    "required": ["code"],
                },
            },
        },
    ]


def get_output_tools() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "post_notification",
                "description": "Post a notification (logs by default, posts externally if configured)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "title": {"type": "string"},
                    },
                    "required": ["text"],
                },
            },
        }
    ]


async def post_to_webhook(text: str, title: str | None = None):
    if not settings.output_webhook_url:
        return {"status": "skipped"}
    payload = {"text": text}
    if title:
        payload["title"] = title
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.output_webhook_url, json=payload)
        return {"status": "success", "status_code": resp.status_code}


async def post_to_slack(text: str):
    if not settings.slack_webhook_url:
        return {"status": "skipped"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.slack_webhook_url, json={"text": text})
        return {"status": "success"}


async def run_event_processor(context: Dict[str, Any]):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Event context:\n{json.dumps(context, default=str)}"},
    ]

    tools = get_mcp_tools() + get_output_tools()

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
            args = json.loads(tool_call.function.arguments or "{}")

            if func_name == "search":
                result = await mcp.call_search(args.get("code", ""))
            elif func_name == "execute":
                result = await mcp.call_execute(args.get("code", ""))
            elif func_name == "post_notification":
                text = args.get("text", "")
                title = args.get("title")

                # Default: log the output
                logger.info("=== LLM Output ===")
                if title:
                    logger.info(f"Title: {title}")
                logger.info(text)
                logger.info("==================")

                result = {"status": "logged"}

                if settings.output_webhook_url:
                    result["webhook"] = await post_to_webhook(text, title)
                if settings.slack_webhook_url:
                    result["slack"] = await post_to_slack(text)

            else:
                result = {"error": f"Unknown tool {func_name}"}

            results.append({"tool": func_name, "result": result})

        if tool_calls:
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            for r in results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(r["result"], default=str)[:3000]
                })

            final_response = await litellm.acompletion(
                model=settings.llm_model,
                messages=messages,
                temperature=0.1,
                max_tokens=1500,
            )
            final_text = final_response.choices[0].message.content or final_text

        return {
            "final_answer": final_text,
            "tool_results": results,
        }

    except Exception as e:
        logger.exception("Processing failed")
        return {"error": str(e)}


@app.post("/webhook")
async def webhook(payload: Dict[str, Any]):
    context = {"source": "webhook", "payload": payload}
    result = await run_event_processor(context)
    return {"status": "processed", "result": result}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mcp_connected": bool(mcp.session),
        "search_tools": mcp.search_tools,
        "execute_tools": mcp.execute_tools,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
