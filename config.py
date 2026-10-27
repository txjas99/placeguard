"""Centralized configuration management using Pydantic Settings.

All configuration comes from environment variables with validation.
Create a .env file in the project root with required settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://placeguard:placeguard@localhost:5432/placeguard"
    database_echo: bool = False  # Set to True for SQL query logging
    
    # LLM Configuration
    llm_provider: str = "gemini"  # gemini | openai | claude
    
    # Gemini settings
    gemini_api_key: str | None = None
    gemini_model: str = "models/gemini-1.5-flash"  # Full model path for LangChain
    gemini_temperature: float = 0.1  # Low temperature for deterministic extraction
    gemini_max_retries: int = 3
    gemini_timeout: int = 30  # seconds
    
    # OpenAI settings (for future use)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    
    # Claude settings (for future use)
    claude_api_key: str | None = None
    claude_model: str = "claude-3-haiku-20240307"
    
    # API Configuration
    jwt_secret: str = "CHANGE_THIS_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    # Application
    debug: bool = False
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()


def validate_settings() -> None:
    """Validate critical settings are properly configured.
    
    Raises:
        ValueError: If required settings are missing or invalid
    """
    if settings.llm_provider == "gemini" and not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY must be set when using Gemini provider. "
            "Get your key from https://makersuite.google.com/app/apikey"
        )
    
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set when using OpenAI provider")
    
    if settings.llm_provider == "claude" and not settings.claude_api_key:
        raise ValueError("CLAUDE_API_KEY must be set when using Claude provider")
    
    if not settings.database_url:
        raise ValueError("DATABASE_URL must be set")
