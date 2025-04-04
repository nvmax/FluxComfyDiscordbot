import logging
from typing import Type
from .base import AIProvider
from .gemini.provider import GeminiProvider
from .lmstudio.provider import LMStudioProvider
from .openai.provider import OpenAIProvider
from .xai.provider import XAIProvider
from .anthropic.provider import AnthropicProvider
from .mistral.provider import MistralProvider

class AIProviderFactory:
    """Factory class for creating AI provider instances."""

    _providers = {
        "gemini": GeminiProvider,
        "lmstudio": LMStudioProvider,
        "openai": OpenAIProvider,
        "xai": XAIProvider,
        "anthropic": AnthropicProvider,
        "mistral": MistralProvider
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> AIProvider:
        """
        Get an instance of the specified AI provider.

        Args:
            provider_name: Name of the provider to instantiate

        Returns:
            An instance of the specified provider

        Raises:
            ValueError: If the provider name is not recognized
        """
        provider_name = provider_name.lower() if provider_name else ""

        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")

        try:
            provider_instance = provider_class()
            return provider_instance
        except Exception as e:
            raise
