import os
import logging
import aiohttp
from typing import Optional
from ..base import AIProvider
from config import OPENAI_API_KEY, OPENAI_MODEL

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
        
        # Define word limits for each creativity level
        self.word_limits = {
            1: 0,      
            2: 10,     
            3: 20,     
            4: 30,    
            5: 40,     
            6: 50,     
            7: 60,     
            8: 70,     
            9: 80,     
            10: 90    
        }

    def _get_word_limit(self, temperature: float) -> int:
        """Get word limit based on temperature/creativity level."""
        # Convert temperature (0.1-1.0) to creativity level (1-10)
        creativity_level = round(temperature * 10)
        # Get word limit for this level
        return self.word_limits.get(creativity_level, 100)  # Default to 100 if level not found

    def _enforce_word_limit(self, text: str, limit: int) -> str:
        """Enforce word limit on generated text."""
        if limit == 0:
            return text
            
        words = text.split()
        if len(words) > limit:
            limited_text = ' '.join(words[:limit])
            logger.info(f"Truncated response from {len(words)} to {limit} words")
            return limited_text
        return text

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
            # Level 1 means no enhancement
            if temperature == 0.1:
                logger.info("Creativity level 1: Using original prompt")
                return prompt

            # Scale the system prompt based on temperature
            if temperature <= 0.2:  # Level 2
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make minimal enhancements:"
                    "\n1. Keep the original prompt almost entirely intact"
                    "\n2. Only add basic descriptive details if absolutely necessary"
                    "\n3. Do not change the core concept or style"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.3:  # Level 3
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation, make light enhancements:"
                    "\n1. Keep the main elements of the original prompt"
                    "\n2. Add minimal artistic style suggestions"
                    "\n3. Include basic descriptive details"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.4:  # Level 4
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make moderate enhancements:"
                    "\n1. Preserve the core concept"
                    "\n2. Add some artistic style elements"
                    "\n3. Include additional descriptive details"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.5:  # Level 5
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make balanced enhancements:"
                    "\n1. Keep the main theme while adding detail"
                    "\n2. Suggest complementary artistic styles"
                    "\n3. Add meaningful descriptive elements"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.6:  # Level 6
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make notable enhancements:"
                    "\n1. Expand on the original concept"
                    "\n2. Add specific artistic style recommendations"
                    "\n3. Include detailed visual descriptions"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.7:  # Level 7
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make significant enhancements:"
                    "\n1. Build upon the core concept"
                    "\n2. Add rich artistic style elements"
                    "\n3. Include comprehensive visual details"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.8:  # Level 8
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make extensive enhancements:"
                    "\n1. Elaborate on the original concept"
                    "\n2. Add detailed artistic direction"
                    "\n3. Include rich visual descriptions"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            elif temperature <= 0.9:  # Level 9
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make substantial enhancements:"
                    "\n1. Significantly expand the concept"
                    "\n2. Add comprehensive artistic direction"
                    "\n3. Include intricate visual details"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )
            else:  # Level 10
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make maximum enhancements:"
                    "\n1. Fully develop and expand the concept"
                    "\n2. Add extensive artistic direction"
                    "\n3. Include highly detailed visual descriptions"
                    "\n4. Return the prompt in a single sentence without any unnecessary information"
                )

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
