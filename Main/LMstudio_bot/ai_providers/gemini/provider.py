import os
import google.generativeai as genai
import logging
from ..base import AIProvider

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    """Gemini AI provider implementation."""
    
    def __init__(self):
        """Initialize Gemini provider with API key."""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        logger.info(f"Initialized Gemini provider with model: gemini-2.0-flash")

    @property
    def base_url(self) -> str:
        return "https://generativelanguage.googleapis.com"

    async def test_connection(self) -> bool:
        try:
            response = self.model.generate_content("test")
            return response.text is not None
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False

    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            # Immediately return original prompt if creativity level is 1 (temperature = 0.1)
            if abs(temperature - 0.1) < 0.001:  # Use small epsilon for float comparison
                logger.info("Creativity level 1: Using original prompt without enhancement")
                return prompt

            system_prompt = self.get_system_prompt(temperature)
 
            # Map temperature to Gemini's temperature range (0.0 to 1.0)
            gemini_temperature = temperature

            # Create the full prompt
            full_prompt = f"{system_prompt}\n\nOriginal prompt: {prompt}\n\nEnhanced prompt:"

            # Generate the response with the mapped temperature
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=gemini_temperature,
                    candidate_count=1,
                    max_output_tokens=1024,
                    stop_sequences=["\n"]
                )
            )

            # Extract and clean up the response
            enhanced_prompt = response.text.strip()

            # Enforce word limit
            word_limit = self._get_word_limit(temperature)
            enhanced_prompt = self._enforce_word_limit(enhanced_prompt, word_limit)

            # Log the enhancement
            logger.info(f"Enhanced prompt with temperature {temperature}: {enhanced_prompt}")

            return enhanced_prompt

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise Exception(f"Gemini API error: {str(e)}")
