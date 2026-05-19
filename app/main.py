"""
CentralMind Gateway - Main FastAPI application.
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

from app.config import settings
from app.agent import run_agent
from app.tools.aruba import centralmind_client

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start CentralMind MCP connection on startup, clean up on shutdown."""
    logger.info("Starting CentralMind Gateway...")
    try:
        await centralmind_client.start()
        logger.info("CentralMind MCP connection established successfully.")
    except Exception as e:
        logger.error(f"Failed to start CentralMind MCP: {e}")
        # Continue anyway — some endpoints may still work

    yield

    logger.info("Shutting down CentralMind Gateway...")
    await centralmind_client.stop()


app = FastAPI(
    title="CentralMind Gateway",
    description="LLM-powered event gateway for Aruba Central using your CentralMind MCP server",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Request Models ---
class QueryRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if settings.gateway_api_key and x_api_key != settings.gateway_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "centralmind_connected": centralmind_client.session is not None,
        "llm_model": settings.llm_model,
    }


@app.post("/query", dependencies=[Depends(verify_api_key)])
async def query_endpoint(req: QueryRequest):
    """On-demand query endpoint — great for testing or integration."""
    logger.info(f"Received query: {req.prompt[:100]}...")
    result = await run_agent(req.prompt, context=req.context)
    return result


@app.post("/webhook", dependencies=[Depends(verify_api_key)])
async def webhook(payload: Dict[str, Any]):
    """
    Generic webhook endpoint. Accepts any JSON payload from any source.
    The LLM enriches the event data using CentralMind tools and produces
    an actionable summary.
    """
    logger.info(f"Received webhook: {json.dumps(payload, default=str)[:200]}...")

    prompt = (
        "An event was received via webhook. Analyze the payload below, "
        "use your tools to gather additional context from Aruba Central "
        "(e.g. device status, clients, site info), and produce a clear, "
        "actionable summary of the situation including business impact "
        "and recommended next steps.\n\n"
        f"Webhook payload:\n{json.dumps(payload, indent=2, default=str)}"
    )

    result = await run_agent(prompt, context=payload)
    return {"status": "processed", "agent_result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
