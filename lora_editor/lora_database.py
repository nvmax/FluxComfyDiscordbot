import sqlite3
import logging
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class LoraHistoryEntry:
    file_name: str
    display_name: str
    trigger_words: str
    weight: dict
    is_active: bool = True
    id: Optional[int] = None

class LoraDatabase:
    def __init__(self, db_path: str = "lora_history.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS lora_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    trigger_words TEXT,
                    weight_min REAL NOT NULL DEFAULT 0.5,
                    weight_max REAL NOT NULL DEFAULT 1.0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                conn.commit()
                logger.debug("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def add_lora(self, entry: LoraHistoryEntry) -> bool:
        """Add or update a LoRA entry in the history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Handle weight values
                if isinstance(entry.weight, dict):
                    weight_min = entry.weight.get('min', 0.5)
                    weight_max = entry.weight.get('max', 1.0)
                else:
                    # Legacy support
                    weight_val = float(entry.weight)
                    weight_min = weight_val * 0.5
                    weight_max = weight_val
                
                c.execute('''INSERT OR REPLACE INTO lora_history 
                           (file_name, display_name, trigger_words, weight_min, weight_max, is_active)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (entry.file_name, entry.display_name, entry.trigger_words, 
                         weight_min, weight_max, entry.is_active))
                conn.commit()
                logger.debug(f"Added/Updated LoRA: {entry.file_name}")
                return True
        except Exception as e:
            logger.error(f"Error adding LoRA to history: {e}")
            return False

    def get_lora_history(self, include_inactive: bool = False) -> List[LoraHistoryEntry]:
        """Get all LoRA entries from history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                if include_inactive:
                    c.execute('SELECT * FROM lora_history ORDER BY created_at DESC')
                else:
                    c.execute('SELECT * FROM lora_history WHERE is_active = 1 ORDER BY created_at DESC')
                
                entries = []
                for row in c.fetchall():
                    # Create weight dictionary from min/max values
                    weight = {
                        "min": row[4],  # weight_min
                        "max": row[5]   # weight_max
                    }
                    
                    entries.append(LoraHistoryEntry(
                        id=row[0],
                        file_name=row[1],
                        display_name=row[2],
                        trigger_words=row[3],
                        weight=weight,
                        is_active=bool(row[6])
                    ))
                return entries
        except Exception as e:
            logger.error(f"Error getting LoRA history: {e}")
            return []


    def deactivate_lora(self, file_name: str) -> bool:
        """Deactivate a LoRA entry (soft delete)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('UPDATE lora_history SET is_active = 0 WHERE file_name = ?', 
                         (file_name,))
                conn.commit()
                return c.rowcount > 0
        except Exception as e:
            logger.error(f"Error deactivating LoRA: {e}")
            return False

    def reactivate_lora(self, file_name: str) -> bool:
        """Reactivate a previously deactivated LoRA entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('UPDATE lora_history SET is_active = 1 WHERE file_name = ?', 
                         (file_name,))
                conn.commit()
                return c.rowcount > 0
        except Exception as e:
            logger.error(f"Error reactivating LoRA: {e}")
            return False

    def sync_with_json(self, json_data: Dict) -> bool:
        """Sync the database with the LoRA configuration JSON"""
        try:
            current_entries = set()
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Add/Update entries from JSON
                for lora in json_data.get('available_loras', []):
                    file_name = lora.get('file')
                    if not file_name:
                        continue
                        
                    current_entries.add(file_name)
                    weight_data = lora.get('weight', {})
                    
                    # Handle both new and old weight formats
                    if isinstance(weight_data, dict):
                        weight_min = weight_data.get('min', 0.5)
                        weight_max = weight_data.get('max', 1.0)
                    else:
                        weight_min = float(weight_data) * 0.5
                        weight_max = float(weight_data)
                    
                    # Update database entry
                    c.execute('''INSERT OR REPLACE INTO lora_history 
                               (file_name, display_name, trigger_words, weight_min, weight_max, is_active)
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (file_name, lora.get('name', ''), lora.get('add_prompt', ''),
                             weight_min, weight_max, True))
                
                # Deactivate entries not in JSON
                c.execute('UPDATE lora_history SET is_active = 0 WHERE file_name NOT IN ({})'.format(
                    ','.join('?' * len(current_entries)) if current_entries else '""'
                ), tuple(current_entries))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error syncing with JSON: {e}")
            return False

    def export_to_json(self) -> Dict:
        """Export active LoRA entries to JSON format"""
        try:
            entries = self.get_lora_history(include_inactive=False)
            loras = []
            for i, entry in enumerate(entries, 1):
                loras.append({
                    'id': i,
                    'name': entry.display_name,
                    'file': entry.file_name,
                    'weight': entry.weight,  # Already in correct format
                    'add_prompt': entry.trigger_words,
                    'URL': ''  # Default empty URL for database entries
                })
            return {'default': '', 'available_loras': loras}
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return {'default': '', 'available_loras': []}
        
    def get_lora_by_filename(self, file_name: str) -> Optional[LoraHistoryEntry]:
        """Get a specific LoRA entry by filename"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM lora_history WHERE file_name = ?', (file_name,))
                row = c.fetchone()
                if row:
                    weight = {
                        "min": row[4],  # weight_min
                        "max": row[5]   # weight_max
                    }
                    return LoraHistoryEntry(
                        id=row[0],
                        file_name=row[1],
                        display_name=row[2],
                        trigger_words=row[3],
                        weight=weight,
                        is_active=bool(row[6])
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting LoRA by filename: {e}")
            return None