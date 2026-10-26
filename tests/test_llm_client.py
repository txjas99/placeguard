"""Tests for LLM client wrapper."""

import json
from unittest.mock import MagicMock, patch

import pytest

from extraction.llm_client import GeminiClient, get_llm_client


def test_get_llm_client_returns_gemini():
    """Test factory function returns correct client type."""
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        with patch("extraction.llm_client.genai"):
            client = get_llm_client("gemini")
            assert isinstance(client, GeminiClient)


def test_get_llm_client_unsupported_provider():
    """Test factory function raises error for unknown provider."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_client("unknown_provider")


def test_gemini_client_requires_api_key():
    """Test GeminiClient raises error without API key."""
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = None
        
        with pytest.raises(ValueError, match="Gemini API key not provided"):
            GeminiClient()


@patch("extraction.llm_client.genai")
def test_gemini_generate_text(mock_genai):
    """Test text generation with Gemini."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.text = "This is a generated response."
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        client = GeminiClient()
        result = client.generate("Test prompt")
        
        assert result == "This is a generated response."
        assert client.total_tokens_used > 0


@patch("extraction.llm_client.genai")
def test_gemini_generate_structured(mock_genai):
    """Test structured JSON generation with Gemini."""
    # Mock the API response with JSON
    test_json = {"name": "Test", "value": 42}
    mock_response = MagicMock()
    mock_response.text = json.dumps(test_json)
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        client = GeminiClient()
        result = client.generate_structured("Test prompt")
        
        assert result == test_json


@patch("extraction.llm_client.genai")
def test_gemini_generate_structured_with_markdown(mock_genai):
    """Test JSON extraction from markdown code blocks."""
    test_json = {"name": "Test", "value": 42}
    mock_response = MagicMock()
    mock_response.text = f"```json\n{json.dumps(test_json)}\n```"
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        client = GeminiClient()
        result = client.generate_structured("Test prompt")
        
        assert result == test_json


@patch("extraction.llm_client.genai")
def test_gemini_retry_on_failure(mock_genai):
    """Test retry logic on API failure."""
    # First two calls fail, third succeeds
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = [
        Exception("API error 1"),
        Exception("API error 2"),
        MagicMock(text="Success on third try"),
    ]
    mock_genai.GenerativeModel.return_value = mock_model
    
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        with patch("extraction.llm_client.time.sleep"):  # Skip actual sleep
            client = GeminiClient()
            result = client.generate("Test prompt")
            
            assert result == "Success on third try"
            assert mock_model.generate_content.call_count == 3


@patch("extraction.llm_client.genai")
def test_gemini_max_retries_exceeded(mock_genai):
    """Test that exception is raised after max retries."""
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("Persistent API error")
    mock_genai.GenerativeModel.return_value = mock_model
    
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        with patch("extraction.llm_client.time.sleep"):
            client = GeminiClient()
            
            with pytest.raises(RuntimeError, match="Gemini API failed after 3 attempts"):
                client.generate("Test prompt")


def test_token_counting():
    """Test approximate token counting."""
    with patch("extraction.llm_client.genai"):
        with patch("extraction.llm_client.settings") as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            mock_settings.gemini_model = "gemini-1.5-flash"
            mock_settings.gemini_temperature = 0.1
            mock_settings.gemini_max_retries = 3
            
            client = GeminiClient()
            
            # Approximate: 4 chars ≈ 1 token
            text = "a" * 400
            tokens = client.count_tokens(text)
            assert tokens == 100
