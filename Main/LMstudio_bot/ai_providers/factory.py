import logging
from typing import Type
from .base import AIProvider
from .gemini.provider import GeminiProvider
from .lmstudio.provider import LMStudioProvider
from .openai.provider import OpenAIProvider
from .xai.provider import XAIProvider

logger = logging.getLogger(__name__)

class AIProviderFactory:
    """Factory class for creating AI provider instances."""
    
    _providers = {
        "gemini": GeminiProvider,
        "lmstudio": LMStudioProvider,
        "openai": OpenAIProvider,
        "xai": XAIProvider
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
        
        logger.info(f"Creating provider instance for: {provider_name}")
        try:
            provider_instance = provider_class()
            logger.info(f"Created provider instance: {provider_instance}")
            return provider_instance
        except Exception as e:
            logger.error(f"Failed to create provider {provider_name}: {e}", exc_info=True)
            raise
