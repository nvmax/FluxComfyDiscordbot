import os
import aiohttp
import logging
from typing import Optional
from ..base import AIProvider

logger = logging.getLogger(__name__)

class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider implementation."""
    
    def __init__(self):
        """Initialize Anthropic provider with API key."""
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        logger.info(f"Initialized Anthropic provider with model: {self.model}")

    @property
    def base_url(self) -> str:
        """Get the base URL for the Anthropic API."""
        return "https://api.anthropic.com/v1"

    async def test_connection(self) -> bool:
        """Test the connection to the Anthropic API."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            # Simple test message
            payload = {
                "model": self.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages", 
                    headers=headers, 
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.info("Anthropic API connection test successful")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Anthropic API connection test failed: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Anthropic API connection test failed: {e}")
            return False

    def get_system_prompt(self, temperature: float) -> str:
        """Get the system prompt based on temperature/creativity level."""
        creativity_level = int(temperature * 10)
        word_limit = self._get_word_limit(temperature)
        
        if creativity_level <= 1:
            return "You are a helpful assistant that enhances image generation prompts."
            
        return f"""You are an AI assistant specialized in enhancing prompts for image generation.
        
Your task is to enhance the given prompt to create more detailed and visually appealing images.

Guidelines:
1. Maintain the original intent and subject of the prompt
2. Add descriptive details about lighting, style, mood, and composition
3. Include artistic references if appropriate (e.g., "in the style of...")
4. Keep the enhanced prompt concise and focused (maximum {word_limit} additional words)
5. Do NOT include any explanations or commentary - ONLY return the enhanced prompt
6. Do NOT use bullet points or numbered lists
7. Format as a single paragraph of comma-separated descriptive phrases
8. Avoid adding NSFW or inappropriate content

Creativity level: {creativity_level}/10 (higher means more creative additions)"""

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate an enhanced prompt using Anthropic's API."""
        try:
            # Immediately return original prompt if creativity level is 1 (temperature = 0.1)
            if abs(temperature - 0.1) < 0.001:  # Use small epsilon for float comparison
                logger.info("Creativity level 1: Using original prompt without enhancement")
                return prompt

            system_prompt = self.get_system_prompt(temperature)

            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            url = f"{self.base_url}/messages"

            payload = {
                "model": self.model,
                "max_tokens": 1024,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": f"Enhance this image prompt: {prompt}"}
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Anthropic API error: HTTP {response.status} - {error_text}")
                    
                    data = await response.json()
                    
                    if not data.get("content") or not data["content"][0].get("text"):
                        raise Exception("Invalid response format from Anthropic API")
                    
                    enhanced_prompt = data["content"][0]["text"].strip()
                    word_limit = self._get_word_limit(temperature)
                    enhanced_prompt = self._enforce_word_limit(enhanced_prompt, word_limit)
                    logger.info(f"Enhanced prompt with temperature {temperature}: {enhanced_prompt}")
                    
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Error generating response from Anthropic: {e}")
            # Return the original prompt if there's an error
            return prompt
            
    def _get_word_limit(self, temperature: float) -> int:
        """Get the word limit based on temperature."""
        creativity_level = int(temperature * 10)
        if creativity_level < 1:
            creativity_level = 1
        elif creativity_level > 10:
            creativity_level = 10
            
        return self.word_limits.get(creativity_level, 50)
        
    def _enforce_word_limit(self, text: str, word_limit: int) -> str:
        """Enforce the word limit on the generated text."""
        if word_limit <= 0:
            return text
            
        words = text.split()
        if len(words) <= word_limit:
            return text
            
        return ' '.join(words[:word_limit])
