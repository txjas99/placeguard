"""Tests for configuration management."""

import pytest
from unittest.mock import patch

from config import Settings, validate_settings


def test_settings_defaults():
    """Test that settings have reasonable defaults."""
    # Prevent .env file from being loaded by passing empty env_file
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings(_env_file=None)
        
        assert settings.llm_provider == "gemini"
        assert settings.gemini_model == "models/gemini-1.5-flash"  # Full model path for LangChain
        assert settings.gemini_temperature == 0.1
        assert settings.jwt_algorithm == "HS256"


def test_settings_from_environment():
    """Test that settings load from environment variables."""
    test_env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "GEMINI_API_KEY": "test_key_123",
        "GEMINI_MODEL": "gemini-pro",
        "LLM_PROVIDER": "gemini",
        "DEBUG": "true",
    }
    
    with patch.dict("os.environ", test_env, clear=True):
        settings = Settings()
        
        assert settings.database_url == "postgresql://test:test@localhost/testdb"
        assert settings.gemini_api_key == "test_key_123"
        assert settings.gemini_model == "gemini-pro"
        assert settings.debug is True


def test_validate_settings_gemini_missing_key():
    """Test validation catches missing Gemini API key."""
    with patch("config.settings") as mock_settings:
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = None
        
        with pytest.raises(ValueError, match="GEMINI_API_KEY must be set"):
            validate_settings()


def test_validate_settings_success():
    """Test validation passes with correct settings."""
    with patch("config.settings") as mock_settings:
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = "valid_key"
        mock_settings.database_url = "postgresql://localhost/db"
        
        # Should not raise
        validate_settings()


def test_case_insensitive_env_vars():
    """Test that environment variables are case-insensitive."""
    test_env = {
        "llm_provider": "gemini",  # lowercase
        "GEMINI_API_KEY": "test_key",  # uppercase
        "Gemini_Model": "gemini-pro",  # mixed case
    }
    
    with patch.dict("os.environ", test_env, clear=True):
        settings = Settings()
        
        assert settings.llm_provider == "gemini"
        assert settings.gemini_api_key == "test_key"
        assert settings.gemini_model == "gemini-pro"
