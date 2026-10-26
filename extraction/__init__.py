"""Extraction module for PlaceGuard.

Handles LLM-based extraction of structured eligibility criteria from free-text
placement notices. Provider-agnostic design allows easy switching between
Gemini, OpenAI, Claude, or other LLM providers.
"""

from extraction.llm_client import GeminiClient, LLMClient, get_llm_client

__all__ = ["LLMClient", "GeminiClient", "get_llm_client"]
