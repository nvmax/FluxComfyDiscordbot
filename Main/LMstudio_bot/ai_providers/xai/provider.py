import os
import aiohttp
import logging
from typing import Optional
from ..base import AIProvider

logger = logging.getLogger(__name__)

class XAIProvider(AIProvider):
    """XAI provider implementation."""
    
    def __init__(self):
        """Initialize XAI provider with API key."""
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable is not set")
        self.model = "grok-2-latest"  # Using latest Grok model
        logger.info(f"Initialized XAI provider with model: {self.model}")

    @property
    def base_url(self) -> str:
        """Get the base URL for the XAI API."""
        return "https://api.x.ai/v1"

    async def test_connection(self) -> bool:
        """Test the connection to XAI API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Test with a simple completion request
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"XAI connection test failed: {e}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate an enhanced prompt using XAI API."""
        try:
            # Immediately return original prompt if creativity level is 1 (temperature = 0.1)
            if abs(temperature - 0.1) < 0.001:  # Use small epsilon for float comparison
                logger.info("Creativity level 1: Using original prompt without enhancement")
                return prompt

            system_prompt = self.get_system_prompt(temperature)

            # Get word limit for this creativity level
            word_limit = self._get_word_limit(temperature)
            # Add word limit instruction to system prompt
            word_limit_instruction = f"\n\nIMPORTANT: Your response must not exceed {word_limit} words. Be concise and precise."

            system_prompt = system_prompt + word_limit_instruction

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Original prompt: {prompt}\n\nEnhanced prompt:"}
                ],
                "temperature": temperature,
                "max_tokens": 1024,
                "n": 1,
                "stop": ["\n"]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"XAI API error: HTTP {response.status} - {error_text}")
                        raise Exception(f"XAI API error: HTTP {response.status} - {error_text}")
                    
                    data = await response.json()
                    if not data.get("choices") or not data["choices"][0].get("message"):
                        raise Exception("Invalid response format from XAI API")
                        
                    enhanced_prompt = data["choices"][0]["message"]["content"].strip()
                    
                    # Enforce word limit
                    enhanced_prompt = self._enforce_word_limit(enhanced_prompt, word_limit)
                    
                    #logger.info(f"Enhanced prompt with temperature {temperature} (limit {word_limit} words): {enhanced_prompt}")
                    
                    return enhanced_prompt

        except Exception as e:
            logger.error(f"XAI API error: {e}", exc_info=True)
            raise Exception(f"XAI API error: {str(e)}")
