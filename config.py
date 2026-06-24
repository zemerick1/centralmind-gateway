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
        default="centralmind",
        description="Command to start the CentralMind MCP server"
    )

    # LLM via LiteLLM
    llm_model: str = Field(default="xai/grok-3-latest")
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=3000)

    xai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Outputs
    output_webhook_url: Optional[str] = Field(default=None)
    slack_webhook_url: Optional[str] = Field(default=None)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")


settings = Settings()
