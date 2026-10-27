"""Tests for LLM client wrapper."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from extraction.llm_client import LangChainClient, get_llm_client


def test_get_llm_client_returns_gemini():
    """Test factory function returns correct client type."""
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = "test_key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.gemini_temperature = 0.1
        mock_settings.gemini_max_retries = 3
        
        # Patch the import inside get_llm_client
        with patch("langchain_google_genai.ChatGoogleGenerativeAI"):
            client = get_llm_client("gemini")
            assert isinstance(client, LangChainClient)


def test_get_llm_client_unsupported_provider():
    """Test factory function raises error for unknown provider."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_client("unknown_provider")


def test_gemini_client_requires_api_key():
    """Test get_llm_client raises error without API key."""
    with patch("extraction.llm_client.settings") as mock_settings:
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_api_key = None
        
        with pytest.raises(ValueError, match="Gemini API key not provided"):
            get_llm_client()


def test_gemini_generate_text():
    """Test text generation with LangChain client."""
    # Mock the LangChain chat model
    mock_model = Mock()
    mock_response = Mock()
    mock_response.content = "This is a generated response."
    mock_model.invoke.return_value = mock_response
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    result = client.generate("Test prompt")
    
    assert result == "This is a generated response."
    assert client.total_tokens_used > 0
    assert mock_model.invoke.called


def test_gemini_generate_structured():
    """Test structured JSON generation with LangChain client."""
    # Mock the LangChain chat model
    mock_model = Mock()
    mock_response = Mock()
    test_json = {"name": "Test", "value": 42}
    mock_response.content = json.dumps(test_json)
    mock_model.invoke.return_value = mock_response
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    result = client.generate_structured("Test prompt")
    
    assert result == test_json


def test_gemini_generate_structured_with_markdown():
    """Test JSON extraction from markdown code blocks."""
    # Mock the LangChain chat model
    mock_model = Mock()
    mock_response = Mock()
    test_json = {"name": "Test", "value": 42}
    mock_response.content = f"```json\n{json.dumps(test_json)}\n```"
    mock_model.invoke.return_value = mock_response
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    result = client.generate_structured("Test prompt")
    
    assert result == test_json


def test_gemini_retry_on_failure():
    """Test LangChain client handles API failures gracefully."""
    # LangChain's ChatGoogleGenerativeAI has built-in retry logic via max_retries parameter
    # This test verifies the client works when model eventually succeeds
    mock_model = Mock()
    mock_response = Mock()
    mock_response.content = "Success on retry"
    
    # Simulate: first call fails, second succeeds
    mock_model.invoke.side_effect = [
        Exception("API error"),
        mock_response,
    ]
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    
    # First call should fail
    with pytest.raises(Exception, match="API error"):
        client.generate("Test prompt")
    
    # Second call should succeed
    result = client.generate("Test prompt")
    assert result == "Success on retry"


def test_gemini_max_retries_exceeded():
    """Test that LangChain client propagates persistent failures."""
    # LangChain's max_retries is configured at the model level
    # Here we test the client behaves correctly when model fails
    mock_model = Mock()
    mock_model.invoke.side_effect = Exception("Persistent API error")
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    
    with pytest.raises(Exception, match="Persistent API error"):
        client.generate("Test prompt")


def test_token_counting():
    """Test approximate token counting."""
    mock_model = Mock()
    
    client = LangChainClient(model=mock_model, default_temperature=0.1)
    
    # Approximate: 4 chars ≈ 1 token
    text = "a" * 400
    tokens = client.count_tokens(text)
    assert tokens == 100
