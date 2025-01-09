"""Prompt enhancement using LM Studio."""
from typing import Dict, Any
import requests
import re
from .config import (
    CHAT_ENDPOINT,
    DEFAULT_CREATIVITY,
    MAX_CREATIVITY,
    MIN_CREATIVITY
)

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

    # """def _extract_important_keywords(self, prompt: str) -> set:
    #     """
    #     Extract important keywords from the user's prompt.
    #     Excludes common words and focuses on descriptive terms.
    #     """
    #     # Convert to lowercase and split into words
    #     words = prompt.lower().split()
        
    #     # Common words to exclude
    #     common_words = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
    #     # Keep words that are not in common_words and are at least 3 characters long
    #     return {word for word in words if word not in common_words and len(word) >= 3}"""

    # """def _ensure_keywords_present(self, enhanced_prompt: str, original_keywords: set) -> str:
    #     """
    #     Ensure all important keywords from the original prompt are present in the enhanced prompt.
    #     Add any missing keywords in a natural way, preserving their original context.
    #     """
    #     # Tokenize original keywords into a list to maintain order
    #     original_keywords = list(original_keywords)
    #     enhanced_words = enhanced_prompt.split()
    #     enhanced_lower = [word.lower() for word in enhanced_words]

    #     # Identify missing keywords
    #     missing_keywords = [word for word in original_keywords if word.lower() not in enhanced_lower]

    #     if not missing_keywords:
    #         return enhanced_prompt  # If no keywords are missing, return the prompt as-is

    #     # Process each missing keyword
    #     for missing in missing_keywords:
    #         for i, word in enumerate(original_keywords):
    #             if word.lower() == missing.lower():
    #                 # Find the next or previous word in the original prompt for context
    #                 context_before = original_keywords[i - 1] if i > 0 else None
    #                 context_after = original_keywords[i + 1] if i < len(original_keywords) - 1 else None

    #                 # Check if context matches in the enhanced prompt
    #                 inserted = False
    #                 if context_before:
    #                     for j, enhanced_word in enumerate(enhanced_words):
    #                         if context_before.lower() in enhanced_word.lower():
    #                             enhanced_words.insert(j + 1, missing)
    #                             inserted = True
    #                             break
    #                 if not inserted and context_after:
    #                     for j, enhanced_word in enumerate(enhanced_words):
    #                         if context_after.lower() in enhanced_word.lower():
    #                             enhanced_words.insert(j, missing)
    #                             inserted = True
    #                             break
    #                 if not inserted:
    #                     # Append at the end as a last resort (unlikely to be needed)
    #                     enhanced_words.append(missing)

    #     # Reconstruct the enhanced prompt
    #     return " ".join(enhanced_words)"""

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
            # For creativity level 1, return the original prompt without any processing
            if creativity == 1:
                return user_prompt
            
            # Process any quoted text in the prompt first
            processed_prompt = self._process_text_in_quotes(user_prompt)
            
            # Validate and clamp creativity value
            creativity = max(MIN_CREATIVITY, min(MAX_CREATIVITY, creativity))
            
            # Adjust temperature based on creativity level
            temperature = 0.3 + ((creativity - 1) * 0.075)
            
            system_prompt = """You are an expert in crafting detailed, imaginative, and visually descriptive prompts for AI image generation, Your goal is to enhance the user's input to create vivid and precise prompts that guide the AI to produce stunning and accurate visuals." 
            
            IMPORTANT RULES:
            1. Only output the enhanced prompt, nothing else
            2. Do not explain your changes or add any commentary
            3. Do not mention the LoRA name in the prompt
            4. Keep the prompt concise and focused
            5. IMPORTANT: Preserve the key words and elements and descriptive terms from the original prompt"""

            user_message = f"""Original prompt: "{processed_prompt}"
            Enhance this prompt to creativity level {creativity}. Output ONLY the enhanced prompt."""

            response = requests.post(
                self.endpoint,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": temperature,
                    "max_tokens": 500
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
            
            # Comment out the keyword preservation since the function is disabled
            # enhanced_prompt = self._ensure_keywords_present(enhanced_prompt, original_keywords)
            
            return enhanced_prompt
        except requests.exceptions.RequestException as e:
            print(f"Error enhancing prompt: {e}")
            return user_prompt
        except Exception as e:
            print(f"Unexpected error in prompt enhancement: {e}")
            return user_prompt
