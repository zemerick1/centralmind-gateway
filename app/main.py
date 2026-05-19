"""
CentralMind Gateway - Main FastAPI application.
"""

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


class WebhookRequest(BaseModel):
    # Generic + Aruba-specific fields
    alert_type: Optional[str] = None
    ap_name: Optional[str] = None
    site: Optional[str] = None
    client_mac: Optional[str] = None
    message: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None   # full original payload


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


@app.post("/webhook/aruba", dependencies=[Depends(verify_api_key)])
async def aruba_webhook(req: WebhookRequest):
    """Primary webhook for Aruba Central alerts."""
    logger.info(f"Received Aruba webhook: {req.alert_type or 'unknown'}")

    # Build smart prompt based on event type
    if req.alert_type and "ap" in (req.alert_type or "").lower():
        prompt = (
            f"AP alert received: {req.alert_type}. "
            f"AP: {req.ap_name or 'unknown'}, Site: {req.site or 'unknown'}. "
            "Please investigate current status, connected clients, and recent events. "
            "Then post a clear notification to the team."
        )
    else:
        prompt = (
            f"Network event received: {req.alert_type or req.message or 'unknown event'}. "
            "Analyze the situation using available tools and notify the team with key details and recommended actions."
        )

    context = req.model_dump(exclude_none=True)

    result = await run_agent(prompt, context=context)
    return {
        "status": "processed",
        "event_type": req.alert_type,
        "agent_result": result
    }


@app.post("/webhook", dependencies=[Depends(verify_api_key)])
async def generic_webhook(payload: Dict[str, Any]):
    """Generic webhook endpoint for any source."""
    prompt = f"Process this incoming event and take appropriate action: {payload}"
    result = await run_agent(prompt, context={"source": "generic_webhook", "payload": payload})
    return {"status": "processed", "agent_result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
