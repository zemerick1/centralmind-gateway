"""Configuration for CentralMind Gateway."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # CentralMind MCP
    centralmind_command: str = Field(
        default="python -m centralmind",
        description="Command to start the CentralMind MCP server"
    )
    mcp_timeout: int = Field(default=60, description="Timeout for MCP calls in seconds")

    # LLM (via LiteLLM)
    llm_model: str = Field(
        default="xai/grok-3-latest",
        description="LiteLLM model name (e.g. xai/grok-3-latest, gemini/gemini-2.5-flash)"
    )
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=4000)

    xai_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)

    # Outputs
    output_webhook_url: Optional[str] = Field(default=None, description="Primary webhook (Teams, etc.)")
    slack_webhook_url: Optional[str] = Field(default=None)

    # Safety
    centralmind_api_mode: str = Field(default="readonly")
    log_level: str = Field(default="INFO")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    gateway_api_key: Optional[str] = Field(default=None)


settings = Settings()
