import sqlite3
import json
import logging
import time

logger = logging.getLogger(__name__)

DB_NAME = 'image_history.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
        # Ensure loras is a list of up to 4 items
        loras_list = loras[:4] if isinstance(loras, list) else [loras]
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
        new_loras_list = new_loras[:4] if isinstance(new_loras, list) else [new_loras]
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