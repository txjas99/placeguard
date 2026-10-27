"""Provider-agnostic LLM client wrapper using LangChain for PlaceGuard.

Supports multiple LLM providers through LangChain with a unified interface:
- Gemini (Google AI) - Free tier available
- OpenAI (GPT-4, etc.)
- Claude (Anthropic)

Design principle: Swap providers by changing config, not code.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from config import settings


class LLMClient(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text completion from prompt.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON output from prompt.
        
        Args:
            prompt: Input prompt
            schema: JSON schema for output validation (optional)
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON dict
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text (approximate)."""
        pass


class LangChainClient(LLMClient):
    """LangChain-based LLM client with provider flexibility."""
    
    def __init__(
        self,
        model: BaseChatModel,
        default_temperature: float = 0.1,
    ):
        """Initialize LangChain client.
        
        Args:
            model: LangChain chat model instance
            default_temperature: Default temperature for generation
        """
        self.model = model
        self.default_temperature = default_temperature
        self.total_tokens_used = 0
    
    def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text using LangChain."""
        temp = temperature if temperature is not None else self.default_temperature
        
        # Create a new model instance with the desired temperature
        model_kwargs = {"temperature": temp}
        if max_tokens:
            model_kwargs["max_tokens"] = max_tokens
        
        # Use the model directly
        messages = [HumanMessage(content=prompt)]
        response = self.model.invoke(messages, config={"temperature": temp})
        
        # Track tokens (approximate)
        self.total_tokens_used += self.count_tokens(prompt) + self.count_tokens(
            response.content
        )
        
        return response.content
    
    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON output using LangChain.
        
        Uses JsonOutputParser to ensure valid JSON output.
        """
        temp = temperature if temperature is not None else self.default_temperature
        
        # Enhance prompt to request JSON output
        json_prompt = f"""{prompt}

IMPORTANT: Respond with ONLY valid JSON. No markdown, no explanation, just the JSON object.
"""
        
        if schema:
            json_prompt += f"\n\nExpected JSON schema:\n{json.dumps(schema, indent=2)}"
        
        # Use JsonOutputParser for structured output
        parser = JsonOutputParser()
        
        # Create chain: model -> parser
        messages = [HumanMessage(content=json_prompt)]
        response = self.model.invoke(messages, config={"temperature": temp})
        
        # Track tokens
        self.total_tokens_used += self.count_tokens(json_prompt) + self.count_tokens(
            response.content
        )
        
        # Parse JSON
        try:
            parsed = parser.parse(response.content)
            
            # Basic schema validation if provided
            if schema and "required" in schema:
                for field in schema["required"]:
                    if field not in parsed:
                        raise ValueError(f"Missing required field: {field}")
            
            return parsed
        
        except Exception as e:
            raise ValueError(
                f"Failed to parse JSON from LLM response. "
                f"Raw response: {response.content[:200]}... Error: {e}"
            ) from e
    
    def count_tokens(self, text: str) -> int:
        """Approximate token count (4 chars ≈ 1 token)."""
        return len(text) // 4


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Factory function to get the appropriate LLM client.
    
    Args:
        provider: LLM provider name (defaults to settings.llm_provider)
        
    Returns:
        Configured LLMClient instance
        
    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    provider = provider or settings.llm_provider
    provider = provider.lower()
    
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY environment variable. "
                "Get your key from: https://makersuite.google.com/app/apikey"
            )
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            max_retries=settings.gemini_max_retries,
        )
        
        return LangChainClient(
            model=model,
            default_temperature=settings.gemini_temperature,
        )
    
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable."
            )
        
        from langchain_openai import ChatOpenAI
        
        model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.gemini_temperature,  # Use configured temp
        )
        
        return LangChainClient(
            model=model,
            default_temperature=settings.gemini_temperature,
        )
    
    elif provider == "claude":
        if not settings.claude_api_key:
            raise ValueError(
                "Claude API key not provided. Set CLAUDE_API_KEY environment variable."
            )
        
        from langchain_anthropic import ChatAnthropic
        
        model = ChatAnthropic(
            model=settings.claude_model,
            api_key=settings.claude_api_key,
            temperature=settings.gemini_temperature,  # Use configured temp
        )
        
        return LangChainClient(
            model=model,
            default_temperature=settings.gemini_temperature,
        )
    
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: gemini, openai, claude"
        )


# Convenience exports for backward compatibility
GeminiClient = lambda: get_llm_client("gemini")
OpenAIClient = lambda: get_llm_client("openai")
ClaudeClient = lambda: get_llm_client("claude")
