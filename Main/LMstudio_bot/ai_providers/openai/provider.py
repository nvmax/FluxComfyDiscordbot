import os
import logging
import aiohttp
from typing import Optional
from ..base import AIProvider

logger = logging.getLogger(__name__)

class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""
    
    def __init__(self):
        """Initialize OpenAI provider with API key."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.model = "gpt-4-turbo-preview"  # Using latest GPT-4 model
        logger.info(f"Initialized OpenAI provider with model: {self.model}")

    @property
    def base_url(self) -> str:
        return "https://api.openai.com/v1"

    async def test_connection(self) -> bool:
        """Test the connection to OpenAI API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "temperature": 0.7,
                "max_tokens": 50
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info("OpenAI connection test successful")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI connection test failed with status {response.status}: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}", exc_info=True)
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate an enhanced prompt using OpenAI's API."""
        try:
            # Immediately return original prompt if creativity level is 1 (temperature = 0.1)
            if abs(temperature - 0.1) < 0.001:  # Use small epsilon for float comparison
                logger.info("Creativity level 1: Using original prompt without enhancement")
                return prompt

            system_prompt = self.get_system_prompt(temperature)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/chat/completions"
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
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"OpenAI API error: HTTP {response.status} - {error_text}")
                    
                    data = await response.json()
                    
                    if not data.get("choices") or not data["choices"][0].get("message"):
                        raise Exception("Invalid response format from OpenAI API")
                    
                    enhanced_prompt = data["choices"][0]["message"]["content"].strip()
                    word_limit = self._get_word_limit(temperature)
                    enhanced_prompt = self._enforce_word_limit(enhanced_prompt, word_limit)
                    logger.info(f"Enhanced prompt with temperature {temperature}: {enhanced_prompt}")
                    
            return enhanced_prompt

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise Exception(f"OpenAI API error: {str(e)}")
