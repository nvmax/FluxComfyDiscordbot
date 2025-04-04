import sqlite3
import json
import logging
import time
import os
import re

logger = logging.getLogger(__name__)

DB_NAME = 'image_history.db'
BANNED_WORDS_FILE = os.path.join(os.path.dirname(__file__), 'banned.json')

def load_banned_words_from_json():
    try:
        with open(BANNED_WORDS_FILE, 'r') as f:
            words = json.load(f)
            # Normalize all words from the JSON file
            return [normalize_text(word) for word in words]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading banned words from JSON: {e}")
        return []

def save_banned_words_to_json(words):
    try:
        with open(BANNED_WORDS_FILE, 'w') as f:
            json.dump(sorted(list(set(words))), f, indent=4)
    except Exception as e:
        logger.error(f"Error saving banned words to JSON: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Existing tables remain the same
    c.execute('''CREATE TABLE IF NOT EXISTS image_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  prompt TEXT,
                  workflow JSON,
                  image_filename TEXT,
                  resolution TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  loras JSON,
                  upscale_factor INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS banned_users
                 (user_id TEXT PRIMARY KEY,
                  reason TEXT,
                  banned_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Tables for content filtering
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words
                 (word TEXT PRIMARY KEY,
                  added_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_warnings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  prompt TEXT,
                  word TEXT,
                  warned_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # New tables for enhanced content filtering
    c.execute('''CREATE TABLE IF NOT EXISTS regex_patterns
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  pattern TEXT,
                  description TEXT,
                  severity TEXT,
                  added_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS context_rules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trigger_word TEXT UNIQUE,
                  allowed_contexts TEXT,
                  disallowed_contexts TEXT,
                  description TEXT,
                  added_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS filter_violations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  prompt TEXT,
                  violation_type TEXT,
                  violation_details TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    conn.commit()

    # Load banned words from JSON and sync with database
    banned_words = load_banned_words_from_json()
    for word in banned_words:
        c.execute("INSERT OR IGNORE INTO banned_words (word) VALUES (?)", (word,))
    conn.commit()
    conn.close()

def add_to_history(user_id, prompt, workflow, image_filename, resolution, loras, upscale_factor):
    if image_filename.startswith('ComfyUI'):
        logger.debug(f"Skipping temporary file: {image_filename}")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT id FROM image_history
        WHERE user_id = ? AND prompt = ? AND
        datetime(timestamp, 'unixepoch') = datetime(?, 'unixepoch')
    """, (user_id, prompt, int(time.time())))

    existing_entry = c.fetchone()

    if existing_entry:
        logger.debug(f"Skipping duplicate entry for user_id={user_id}, prompt={prompt}")
    else:
        # Ensure loras is a list of up to 25 items
        loras_list = loras[:25] if isinstance(loras, list) else [loras]
        loras_json = json.dumps(loras_list)

        c.execute("INSERT INTO image_history (user_id, prompt, workflow, image_filename, resolution, loras, upscale_factor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user_id, prompt, json.dumps(workflow), image_filename, resolution, loras_json, upscale_factor))
        conn.commit()
        logger.debug(f"Added to history: user_id={user_id}, prompt={prompt}, image_filename={image_filename}, resolution={resolution}, loras={loras_json}, upscale_factor={upscale_factor}")

    conn.close()

def get_user_history(user_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM image_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    history = c.fetchall()
    conn.close()
    logger.debug(f"Retrieved history for user_id={user_id}: {len(history)} entries")
    return history

def get_image_info(image_filename):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM image_history WHERE image_filename = ?", (image_filename,))
    info = c.fetchone()
    conn.close()
    if info:
        loras = json.loads(info[7])
        logger.debug(f"Image info found for {image_filename}: {info}")
        return {
            'prompt': info[2],
            'resolution': info[5],
            'loras': loras[:4],  # Ensure we return up to 4 LoRAs
            'upscale_factor': info[8]
        }
    else:
        logger.warning(f"No image info found for {image_filename}")
    return None

def get_all_image_info():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM image_history")
        info = c.fetchall()
        logger.debug(f"Retrieved {len(info)} image entries")
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            logger.warning("image_history table does not exist. Returning empty list.")
            info = []
        else:
            raise
    finally:
        conn.close()
    return info

def update_image_info(image_filename, new_prompt=None, new_resolution=None, new_loras=None, new_upscale_factor=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    update_fields = []
    update_values = []

    if new_prompt is not None:
        update_fields.append("prompt = ?")
        update_values.append(new_prompt)

    if new_resolution is not None:
        update_fields.append("resolution = ?")
        update_values.append(new_resolution)

    if new_loras is not None:
        update_fields.append("loras = ?")
        new_loras_list = new_loras[:25] if isinstance(new_loras, list) else [new_loras]
        update_values.append(json.dumps(new_loras_list))

    if new_upscale_factor is not None:
        update_fields.append("upscale_factor = ?")
        update_values.append(new_upscale_factor)

    if update_fields:
        update_query = f"UPDATE image_history SET {', '.join(update_fields)} WHERE image_filename = ?"
        update_values.append(image_filename)

        c.execute(update_query, tuple(update_values))
        conn.commit()

        logger.debug(f"Updated image info for {image_filename}: prompt={new_prompt}, resolution={new_resolution}, loras={new_loras}, upscale_factor={new_upscale_factor}")
    else:
        logger.debug(f"No updates provided for {image_filename}")

    conn.close()

def get_banned_words():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT word FROM banned_words")
    words = [row[0] for row in c.fetchall()]
    conn.close()
    return words

def add_banned_word(word: str):
    """Add a new banned word to both database and JSON file"""
    # Normalize the word before storing
    normalized_word = normalize_text(word)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO banned_words (word) VALUES (?)", (normalized_word,))
    conn.commit()
    conn.close()

    # Update JSON file
    current_words = get_banned_words()
    save_banned_words_to_json(current_words)
    logger.debug(f"Added banned word and updated JSON: {word}")

def remove_banned_word(word: str):
    """Remove a banned word from both database and JSON file"""
    # Normalize the word before removing
    normalized_word = normalize_text(word)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM banned_words WHERE word = ?", (normalized_word,))
    conn.commit()
    conn.close()

    # Update JSON file
    current_words = get_banned_words()
    save_banned_words_to_json(current_words)
    logger.debug(f"Removed banned word and updated JSON: {word}")

def add_user_warning(user_id: str, prompt: str, word: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO user_warnings (user_id, prompt, word) VALUES (?, ?, ?)",
              (user_id, prompt, word))
    conn.commit()
    conn.close()

def remove_user_warnings(user_id: str):
    """Remove all warnings for a specific user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        # Check if user has warnings
        c.execute("SELECT COUNT(*) FROM user_warnings WHERE user_id = ?", (user_id,))
        warning_count = c.fetchone()[0]

        if warning_count == 0:
            conn.close()
            return False, "User has no warnings to remove"

        # Delete all warnings for the user
        c.execute("DELETE FROM user_warnings WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True, f"Removed {warning_count} warning(s)"
    except Exception as e:
        conn.close()
        return False, f"Error removing warnings: {str(e)}"

def get_user_warnings(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM user_warnings WHERE user_id = ?", (user_id,))
    warning_count = c.fetchone()[0]
    conn.close()
    return warning_count

def get_all_warnings():
    """Get all warnings from the database, grouped by user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        # Get all warnings with user info
        c.execute("""
            SELECT user_id, prompt, word, warned_at
            FROM user_warnings
            ORDER BY user_id, warned_at DESC
        """)
        warnings = c.fetchall()

        if not warnings:
            conn.close()
            return False, "No warnings found in the database"

        # Group warnings by user
        warning_dict = {}
        for warning in warnings:
            user_id, prompt, word, warned_at = warning
            if user_id not in warning_dict:
                warning_dict[user_id] = []
            warning_dict[user_id].append((prompt, word, warned_at))

        conn.close()
        return True, warning_dict
    except Exception as e:
        conn.close()
        return False, f"Error retrieving warnings: {str(e)}"

def delete_image_info(image_filename):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM image_history WHERE image_filename = ?", (image_filename,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        logger.debug(f"Deleted image info for {image_filename}")
    else:
        logger.warning(f"No image info found to delete for {image_filename}")

    return deleted_count > 0

def ban_user(user_id, reason):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO banned_users (user_id, reason) VALUES (?, ?)", (user_id, reason))
    conn.commit()
    conn.close()
    logger.info(f"Banned user {user_id} for reason: {reason}")

def unban_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        logger.info(f"Unbanned user {user_id}")
    else:
        logger.warning(f"Attempted to unban non-banned user {user_id}")
    return deleted

def get_ban_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT reason, banned_at FROM banned_users WHERE user_id = ?", (user_id,))
    info = c.fetchone()
    conn.close()
    if info:
        logger.debug(f"Retrieved ban info for user {user_id}")
        return {"reason": info[0], "banned_at": info[1]}
    else:
        logger.debug(f"No ban info found for user {user_id}")
        return None

def is_user_banned(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
    is_banned = c.fetchone() is not None
    conn.close()
    return is_banned

def get_all_banned_users():
    """
    Get all banned users from the database with their ban information.
    Returns a list of dictionaries containing user_id, reason, and banned_at.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, reason, banned_at FROM banned_users ORDER BY banned_at DESC")
    banned_users = [{"user_id": row[0], "reason": row[1], "banned_at": row[2]} for row in c.fetchall()]
    conn.close()
    return banned_users

# Function to load LoRA information from lora.json
def load_lora_info():
    try:
        with open('Main/DataSets/lora.json', 'r') as f:
            lora_data = json.load(f)
        return lora_data['available_loras']
    except Exception as e:
        logger.error(f"Error loading LoRA info: {str(e)}")
        return []

# You can call this function to get the LoRA information when needed
lora_info = load_lora_info()

def normalize_text(text: str) -> str:
    """
    Normalize text by removing special characters and converting to lowercase.
    This helps detect obfuscated words like 'Ch!ld' or 'C.h.i.l.d'
    """
    # Convert to lowercase
    text = text.lower()
    # Remove all non-alphanumeric characters
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Remove extra spaces
    text = ' '.join(text.split())
    return text

def contains_banned_word(text: str) -> tuple[bool, list[str]]:
    """
    Check if text contains any banned words, accounting for obfuscation attempts.
    Returns a tuple of (bool, list of matched words)
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT word FROM banned_words")
    banned_words = [row[0] for row in c.fetchall()]
    conn.close()

    # Normalize the input text
    normalized_text = normalize_text(text)
    found_words = []

    # Check each word in the normalized text against normalized banned words
    for banned_word in banned_words:
        normalized_banned = normalize_text(banned_word)
        if normalized_banned in normalized_text:
            found_words.append(banned_word)

    return bool(found_words), found_words
