import os
import aiohttp
import logging
from ..base import AIProvider

logger = logging.getLogger(__name__)

class LMStudioProvider(AIProvider):
    """LMStudio AI provider implementation."""
    
    def __init__(self):
        self.host = os.getenv('LMSTUDIO_HOST', 'localhost')
        self.port = os.getenv('LMSTUDIO_PORT', '1234')
        if not self.host or not self.port:
            raise ValueError("LMSTUDIO_HOST and LMSTUDIO_PORT must be set")

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def test_connection(self) -> bool:
        try:
            headers = {"Content-Type": "application/json"}
            url = f"{self.base_url}/v1/chat/completions"
            
            payload = {
                "messages": [
                    {"role": "user", "content": "test"}
                ],
                "temperature": 0.7
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"LMStudio connection test failed: {e}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            system_prompt = self.get_system_prompt(temperature)

            headers = {"Content-Type": "application/json"}
            url = f"{self.base_url}/v1/chat/completions"

            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Enhance this image prompt: {prompt}"}
                ],
                "temperature": temperature
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        enhanced_prompt = data['choices'][0]['message']['content'].strip()
                        
                        # Get and enforce word limit based on temperature
                        word_limit = self._get_word_limit(temperature)
                        enhanced_prompt = self._enforce_word_limit(enhanced_prompt, word_limit)
                        
                        logger.info(f"Enhanced prompt with creativity level {round(temperature * 10)}")
                        return enhanced_prompt
                    else:
                        error_text = await response.text()
                        logger.error(f"Error from LMStudio API: {error_text}")
                        return prompt  # Return original prompt on error
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return prompt  # Return original prompt on error
