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

    def _get_word_limit(self, temperature: float) -> int:
        """Get word limit based on temperature/creativity level."""
        # Convert temperature (0.1-1.0) to creativity level (1-10)
        creativity_level = round(temperature * 10)
        # Get word limit for this level
        return self.word_limits.get(creativity_level, 90)  # Default to 90 if level not found

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

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            # Level 1 means no enhancement
            if temperature == 0.1:
                logger.info("Creativity level 1: Using original prompt")
                return prompt

            headers = {"Content-Type": "application/json"}
            url = f"{self.base_url}/v1/chat/completions"
            
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
