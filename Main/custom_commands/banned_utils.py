import json
import re
import logging
from Main.database import is_user_banned, ban_user

logger = logging.getLogger(__name__)

def load_banned_data():
    try:
        with open('Main/DataSets/banned.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"banned_words": [], "banned_users": []}

def save_banned_data(data):
    with open('Main/DataSets/banned.json', 'w') as f:
        json.dump(data, f, indent=4)

def check_banned(user_id, prompt):
    if is_user_banned(user_id):
        return True, "You are banned from using this command. Please contact an admin if you believe this is an error."
    
    banned_data = load_banned_data()
    prompt_lower = prompt.lower()
    
    for word in banned_data['banned_words']:
        if re.search(r'\b' + re.escape(word.lower()) + r'\b', prompt_lower):
            ban_user(user_id, f"Used banned word: {word}")
            return True, f"Your prompt contains a banned word. You have been banned from using this command. Please contact an admin if you believe this is an error."
    
    return False, ""