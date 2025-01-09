import re
import logging
from Main.database import (
    is_user_banned, ban_user, get_banned_words, add_user_warning, get_user_warnings
)

logger = logging.getLogger(__name__)

def check_banned(user_id: str, prompt: str):
    if is_user_banned(user_id):
        return True, "You are banned from using this command. Please contact an admin if you believe this is an error."
    
    prompt_lower = prompt.lower()
    banned_words = get_banned_words()
    
    for word in banned_words:
        if re.search(r'\b' + re.escape(word.lower()) + r'\b', prompt_lower):
            warning_count = get_user_warnings(user_id)
            
            if warning_count >= 2:  # Third strike
                ban_user(user_id, f"Used banned word after two warnings: {word}")
                return True, (f"🚫 You have been banned for using the banned word '{word}'.\n"
                            f"This was your third violation. Please contact an admin if you believe this is an error.")
            elif warning_count == 1:  # Second strike
                add_user_warning(user_id, prompt, word)
                return False, (f"⚠️ FINAL WARNING: Your prompt contains the banned word '{word}'.\n"
                             f"This is your second warning. One more violation will result in a permanent ban.\n"
                             f"Banned words list: {', '.join(banned_words)}")
            else:  # First strike
                add_user_warning(user_id, prompt, word)
                return False, (f"⚠️ WARNING: Your prompt contains the banned word '{word}'.\n"
                             f"This is your first warning. You have one more warnings remaining before a permanent ban.\n"
                             f"Banned words list: {', '.join(banned_words)}")
    
    return False, ""