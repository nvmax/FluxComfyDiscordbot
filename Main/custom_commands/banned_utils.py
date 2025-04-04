import re
import logging
from Main.database import (
    is_user_banned, ban_user, get_banned_words, add_user_warning, get_user_warnings
)

# Import content filter if available
try:
    from Main.content_filter import content_filter
    ENHANCED_FILTER = True
except ImportError:
    ENHANCED_FILTER = False
    print("Content filter module not found. Using basic banned word checking.")

logger = logging.getLogger(__name__)

def check_banned(user_id: str, prompt: str):
    """Check if a user is banned or if their prompt contains banned content"""
    if is_user_banned(user_id):
        return True, "You are banned from using this command. Please contact an admin if you believe this is an error."

    # Use enhanced content filter if available
    if ENHANCED_FILTER:
        is_banned, details = content_filter.check_content(prompt)

        if is_banned:
            # Determine which rule was violated
            if details['banned_words']:
                word = details['banned_words'][0]  # Use the first banned word found
                return handle_banned_word(user_id, prompt, word)

            elif details['regex_matches']:
                match = details['regex_matches'][0]  # Use the first regex match
                pattern_name = match['name']
                matched_text = match['matches'][0] if match['matches'] else "[pattern match]"

                warning_count = get_user_warnings(user_id)

                if warning_count >= 2:  # Third strike
                    ban_user(user_id, f"Violated regex pattern after two warnings: {pattern_name}")
                    return True, (f"🚫 You have been banned for violating content policy with '{matched_text}'.\n"
                                f"This was your third violation. Please contact an admin if you believe this is an error.")
                elif warning_count == 1:  # Second strike
                    add_user_warning(user_id, prompt, f"regex:{pattern_name}")
                    return False, (f"⚠️ FINAL WARNING: Your prompt contains prohibited content: '{matched_text}'.\n"
                                 f"This is your second warning. One more violation will result in a permanent ban.")
                else:  # First strike
                    add_user_warning(user_id, prompt, f"regex:{pattern_name}")
                    return False, (f"⚠️ WARNING: Your prompt contains prohibited content: '{matched_text}'.\n"
                                 f"This is your first warning. You have one more warning remaining before a permanent ban.")

            elif details['context_violations']:
                violation = details['context_violations'][0]  # Use the first context violation
                trigger_word = violation['trigger_word']

                if 'disallowed_context' in violation:
                    context = violation['disallowed_context']
                    warning_message = f"using '{trigger_word}' in disallowed context: '{context}'"
                else:
                    warning_message = f"using '{trigger_word}' without appropriate context"

                warning_count = get_user_warnings(user_id)

                if warning_count >= 2:  # Third strike
                    ban_user(user_id, f"Context violation after two warnings: {warning_message}")
                    return True, (f"🚫 You have been banned for {warning_message}.\n"
                                f"This was your third violation. Please contact an admin if you believe this is an error.")
                elif warning_count == 1:  # Second strike
                    add_user_warning(user_id, prompt, f"context:{trigger_word}")
                    return False, (f"⚠️ FINAL WARNING: Your prompt contains prohibited content by {warning_message}.\n"
                                 f"This is your second warning. One more violation will result in a permanent ban.")
                else:  # First strike
                    add_user_warning(user_id, prompt, f"context:{trigger_word}")
                    return False, (f"⚠️ WARNING: Your prompt contains prohibited content by {warning_message}.\n"
                                 f"This is your first warning. You have one more warning remaining before a permanent ban.")

            # Generic banned content message if we can't determine the specific reason
            return True, "Your prompt contains prohibited content and cannot be processed."
    else:
        # Fall back to basic banned word checking
        prompt_lower = prompt.lower()
        banned_words = get_banned_words()

        for word in banned_words:
            if re.search(r'\b' + re.escape(word.lower()) + r'\b', prompt_lower):
                return handle_banned_word(user_id, prompt, word)

    return False, ""

def handle_banned_word(user_id: str, prompt: str, word: str):
    """Handle a banned word violation"""
    warning_count = get_user_warnings(user_id)

    if warning_count >= 2:  # Third strike
        ban_user(user_id, f"Used banned word after two warnings: {word}")
        return True, (f"🚫 You have been banned for using the banned word '{word}'.\n"
                    f"This was your third violation. Please contact an admin if you believe this is an error.")
    elif warning_count == 1:  # Second strike
        add_user_warning(user_id, prompt, word)
        return False, (f"⚠️ FINAL WARNING: Your prompt contains the banned word '{word}'.\n"
                     f"This is your second warning. One more violation will result in a permanent ban.")
    else:  # First strike
        add_user_warning(user_id, prompt, word)
        return False, (f"⚠️ WARNING: Your prompt contains the banned word '{word}'.\n"
                     f"This is your first warning. You have one more warning remaining before a permanent ban.")