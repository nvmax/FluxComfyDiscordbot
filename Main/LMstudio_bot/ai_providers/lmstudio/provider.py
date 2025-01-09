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
                )
            elif temperature <= 0.3:  # Level 3
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation, make light enhancements:"
                    "\n1. Keep the main elements of the original prompt"
                    "\n2. Add minimal artistic style suggestions"
                    "\n3. Include basic descriptive details"
                )
            elif temperature <= 0.4:  # Level 4
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make moderate enhancements:"
                    "\n1. Preserve the core concept"
                    "\n2. Add some artistic style elements"
                    "\n3. Include additional descriptive details"
                )
            elif temperature <= 0.5:  # Level 5
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make balanced enhancements:"
                    "\n1. Keep the main theme while adding detail"
                    "\n2. Suggest complementary artistic styles"
                    "\n3. Add meaningful descriptive elements"
                )
            elif temperature <= 0.6:  # Level 6
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make notable enhancements:"
                    "\n1. Expand on the original concept"
                    "\n2. Add specific artistic style recommendations"
                    "\n3. Include detailed visual descriptions"
                )
            elif temperature <= 0.7:  # Level 7
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make significant enhancements:"
                    "\n1. Build upon the core concept"
                    "\n2. Add rich artistic style elements"
                    "\n3. Include comprehensive visual details"
                )
            elif temperature <= 0.8:  # Level 8
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make extensive enhancements:"
                    "\n1. Elaborate on the original concept"
                    "\n2. Add detailed artistic direction"
                    "\n3. Include rich visual descriptions"
                )
            elif temperature <= 0.9:  # Level 9
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make substantial enhancements:"
                    "\n1. Significantly expand the concept"
                    "\n2. Add comprehensive artistic direction"
                    "\n3. Include intricate visual details"
                )
            else:  # Level 10
                system_prompt = (
                    "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make maximum enhancements:"
                    "\n1. Fully develop and expand the concept"
                    "\n2. Add extensive artistic direction"
                    "\n3. Include highly detailed visual descriptions"
                )
            
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Enhance this prompt according to the specified creativity level: {prompt}"
                    }
                ],
                "temperature": temperature
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")
                    
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LMStudio API error: {e}", exc_info=True)
            raise Exception(f"LMStudio API error: {str(e)}")
