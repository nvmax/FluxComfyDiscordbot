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

    # Define word limits for each creativity level
    word_limits = {
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

    def get_system_prompt(self, temperature: float) -> str:

        # Level 1 means no enhancement
        if temperature == 0.1:
            logger.info("Creativity level 1: Using original prompt")
            return ""

        # Scale the system prompt based on temperature
        if temperature <= 0.2:  # Level 2
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make minimal enhancements:"
                "\n1. Keep the original prompt almost entirely intact"
                "\n2. Only add basic descriptive details if absolutely necessary"
                "\n3. Do not change the core concept or style"
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.3:  # Level 3
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation, make light enhancements:"
                "\n1. Keep the original prompt almost entirely intact"
                "\n2. Add minimal artistic style suggestions"
                "\n3. Include basic descriptive details"
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.4:  # Level 4
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make moderate enhancements:"
                "\n1. Keep the original prompt almost entirely intact add some detail"
                "\n2. Add some artistic style elements"
                "\n3. Include additional descriptive details"
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.5:  # Level 5
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make balanced enhancements:"
                "\n1. Keep the original prompt almost entirely intact add flavor and enhance the concept"
                "\n2. Suggest complementary artistic styles"
                "\n3. Add meaningful descriptive elements"    
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.6:  # Level 6
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make notable enhancements:"
                "\n1. Keep the original prompt almost entirely intact,Expand on the original concept"
                "\n2. Add specific artistic style recommendations"
                "\n3. Include detailed visual descriptions"
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.7:  # Level 7
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make significant enhancements:"
                "\n1. Keep the original prompt almost entirely intact,Build upon the core concept"
                "\n2. Add rich artistic style elements"
                "\n3. Include comprehensive visual details"
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.8:  # Level 8
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make extensive enhancements:"
                "\n1. Keep the original prompt almost entirely intact,Elaborate on the original concept"
                "\n2. Add detailed artistic direction"
                "\n3. Include rich visual descriptions"    
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        elif temperature <= 0.9:  # Level 9
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make substantial enhancements:"
                "\n1. Keep the original prompt almost entirely intact,Significantly expand the concept"
                "\n2. Add comprehensive artistic direction"
                "\n3. Include intricate visual details"    
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )
        else:  # Level 10
            system_prompt = (
                "You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation. For this prompt, make maximum enhancements:"
                "\n1. Keep the original prompt almost entirely intact,Fully develop and expand the concept"
                "\n2. Add extensive artistic direction"
                "\n3. Include highly detailed visual descriptions"    
                "\n4. Return the prompt in a single sentence without any unnecessary information must be under 1999 characters"
            )

        return system_prompt
        