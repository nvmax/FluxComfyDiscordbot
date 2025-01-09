from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class AIProvider(ABC):
    """Base class for all AI providers."""
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the provider."""
        pass

    @abstractmethod
    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate an enhanced prompt using the provider's API."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Get the base URL for the provider's API."""
        pass
