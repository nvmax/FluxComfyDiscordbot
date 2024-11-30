"""Prompt enhancement using LM Studio."""
from typing import Dict, Any
import requests
from .config import (
    CHAT_ENDPOINT,
    DEFAULT_CREATIVITY,
    MAX_CREATIVITY,
    MIN_CREATIVITY
)
import re

class PromptEnhancer:
    def __init__(self):
        """Initialize the prompt enhancer."""
        self.endpoint = CHAT_ENDPOINT

    def _process_text_in_quotes(self, prompt: str) -> str:
        """
        Process the prompt to add 'with text:' before quoted text.
        Example: sign saying "hello" -> sign saying with text: "hello"
        """
        def replace_quote(match):
            # Get the text before the quote
            before_quote = match.string[:match.start()].strip()
            # Only add 'with text:' if it's not already there
            if not before_quote.endswith('with text:'):
                return f'with text: {match.group(0)}'
            return match.group(0)
        
        # Find all quoted text and process them
        pattern = r'"[^"]*"'
        return re.sub(pattern, replace_quote, prompt)

    def _extract_important_keywords(self, prompt: str) -> set:
        """
        Extract important keywords from the user's prompt.
        Excludes common words and focuses on descriptive terms.
        """
        # Convert to lowercase and split into words
        words = prompt.lower().split()
        
        # Common words to exclude
        common_words = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        # Keep words that are not in common_words and are at least 3 characters long
        return {word for word in words if word not in common_words and len(word) >= 3}

    def _ensure_keywords_present(self, enhanced_prompt: str, original_keywords: set) -> str:
        """
        Ensure all important keywords from the original prompt are present in the enhanced prompt.
        Add any missing keywords in a natural way.
        """
        enhanced_words = enhanced_prompt.lower().split()
        missing_keywords = [word for word in original_keywords if word not in enhanced_words]
        
        if not missing_keywords:
            return enhanced_prompt
            
        # Add missing keywords in a natural way
        if len(missing_keywords) == 1:
            return f"{enhanced_prompt}, with {missing_keywords[0]}"
        elif len(missing_keywords) == 2:
            return f"{enhanced_prompt}, with {missing_keywords[0]} and {missing_keywords[1]}"
        else:
            keywords_str = ", ".join(missing_keywords[:-1]) + f", and {missing_keywords[-1]}"
            return f"{enhanced_prompt}, with {keywords_str}"

    def enhance_prompt(self, user_prompt: str, lora_info: Dict[str, Any], 
                      creativity: int = DEFAULT_CREATIVITY) -> str:
        """
        Enhance the user's prompt based on the LoRA's characteristics.
        
        Args:
            user_prompt: Original user prompt
            lora_info: LoRA information dictionary
            creativity: Level of modification (1-10)
        """
        try:
            # Extract important keywords from the original prompt
            original_keywords = self._extract_important_keywords(user_prompt)
            
            # Process any quoted text in the prompt first
            processed_prompt = self._process_text_in_quotes(user_prompt)
            
            # Validate and clamp creativity value
            creativity = max(MIN_CREATIVITY, min(MAX_CREATIVITY, creativity))
            
            # For creativity level 1, return the processed prompt without enhancement
            if creativity == 1:
                return processed_prompt
            
            # Adjust temperature based on creativity level
            temperature = 0.3 + ((creativity - 1) * 0.075)
            
            system_prompt = """A specialist at enhancing user prompts to turn them into Amazing Imaging Prompts. 
            
            IMPORTANT RULES:
            1. Only output the enhanced prompt, nothing else
            2. Do not explain your changes or add any commentary
            3. Do not mention the LoRA name in the prompt
            4. Keep the prompt concise and focused
            5. Preserve the key elements and descriptive terms from the original prompt"""

            user_message = f"""Original prompt: "{processed_prompt}"
            Important keywords to preserve: {', '.join(original_keywords)}
            LoRA capabilities: {lora_info['description']}
            Keywords that work well: {', '.join(lora_info.get('keywords', []))}
            Categories: {', '.join(lora_info.get('categories', []))}
            
            Enhance this prompt to creativity level {creativity}, making sure to preserve the important keywords. Output ONLY the enhanced prompt."""

            response = requests.post(
                self.endpoint,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": temperature,
                    "max_tokens": 200
                }
            )
            response.raise_for_status()
            enhanced_prompt = response.json()["choices"][0]["message"]["content"].strip()
            
            # Remove any quotes that might be in the response
            enhanced_prompt = enhanced_prompt.strip('"\'')
            
            # Additional cleanup to ensure no LoRA name is present
            lora_name_parts = lora_info['name'].lower().replace('_', ' ').split()
            enhanced_prompt_words = enhanced_prompt.lower().split()
            
            # Remove any words that appear in the LoRA name
            if any(part in enhanced_prompt_words for part in lora_name_parts):
                enhanced_prompt = ' '.join(word for word in enhanced_prompt.split() 
                                         if word.lower() not in lora_name_parts)
            
            # Ensure all original keywords are present
            enhanced_prompt = self._ensure_keywords_present(enhanced_prompt, original_keywords)
            
            return enhanced_prompt
        except requests.exceptions.RequestException as e:
            print(f"Error enhancing prompt: {e}")
            return user_prompt
        except Exception as e:
            print(f"Unexpected error in prompt enhancement: {e}")
            return user_prompt
