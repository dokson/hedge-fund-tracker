"""
This package contains the various AI client implementations.

By importing the classes here, we can simplify imports in other parts of the application,
allowing `from app.ai.clients import GoogleAIClient, GroqClient`, etc.
"""
from app.ai.clients.base_client import AIClient
from app.ai.clients.base_openai_client import OpenAIClient
from app.ai.clients.github_client import GitHubClient
from app.ai.clients.google_client import GoogleAIClient
from app.ai.clients.groq_client import GroqClient
from app.ai.clients.openrouter_client import OpenRouterClient

# Defines the public API of this package
__all__ = ["AIClient", "GitHubClient", "GoogleAIClient", "GroqClient", "OpenAIClient", "OpenRouterClient"]
