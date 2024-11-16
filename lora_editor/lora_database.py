import sqlite3
import logging
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os

root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class LoraHistoryEntry:
    file_name: str
    display_name: str
    trigger_words: str
    weight: float
    url: str = ""
    is_active: bool = True
    id: Optional[int] = None
    display_order: int = 0

class LoraDatabase:
    def __init__(self, db_path: str = "lora_history.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Drop existing table to reset IDs
                c.execute('DROP TABLE IF EXISTS lora_history')
                
                # Create table
                c.execute('''CREATE TABLE IF NOT EXISTS lora_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    trigger_words TEXT,
                    weight REAL NOT NULL,
                    url TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                # Reset the SQLite sequence
                c.execute("DELETE FROM sqlite_sequence WHERE name='lora_history'")
                
                conn.commit()
                logger.debug("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def add_lora(self, entry: LoraHistoryEntry, order: int = None) -> Optional[LoraHistoryEntry]:
        """Add or update a LoRA entry in the history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # If no order specified, put it at the end
                if order is None:
                    c.execute('SELECT MAX(display_order) FROM lora_history')
                    max_order = c.fetchone()[0]
                    order = (max_order or 0) + 1
                
                # Check if entry already exists
                c.execute('SELECT id FROM lora_history WHERE file_name = ?', (entry.file_name,))
                existing_id = c.fetchone()
                
                if existing_id:
                    # Update existing entry, preserving the original ID
                    c.execute('''UPDATE lora_history 
                               SET display_name = ?, trigger_words = ?, weight = ?, url = ?, 
                               is_active = ?, display_order = ?
                               WHERE file_name = ?''',
                            (entry.display_name, entry.trigger_words, entry.weight, 
                             entry.url, entry.is_active, order, entry.file_name))
                    entry.id = existing_id[0]
                else:
                    # For new entries, use the provided ID if available
                    if entry.id is not None:
                        c.execute('''INSERT INTO lora_history 
                                   (id, file_name, display_name, trigger_words, weight, url, is_active, display_order)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                (entry.id, entry.file_name, entry.display_name, entry.trigger_words,
                                 entry.weight, entry.url, entry.is_active, order))
                    else:
                        # If no ID provided, let SQLite auto-generate one
                        c.execute('''INSERT INTO lora_history 
                                   (file_name, display_name, trigger_words, weight, url, is_active, display_order)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                (entry.file_name, entry.display_name, entry.trigger_words,
                                 entry.weight, entry.url, entry.is_active, order))
                        entry.id = c.lastrowid
                
                conn.commit()
                logger.debug(f"Added/Updated LoRA: {entry.file_name} with ID {entry.id}")
                return entry
                
        except Exception as e:
            logger.error(f"Error adding LoRA to history: {e}")
            return None

    def get_lora_history(self, include_inactive: bool = False) -> List[LoraHistoryEntry]:
        """Get all LoRA entries from history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                if include_inactive:
                    c.execute('''SELECT id, file_name, display_name, trigger_words, weight, url, is_active, display_order 
                               FROM lora_history 
                               ORDER BY display_order ASC''')
                else:
                    c.execute('''SELECT id, file_name, display_name, trigger_words, weight, url, is_active, display_order 
                               FROM lora_history 
                               WHERE is_active = 1
                               ORDER BY display_order ASC''')
                
                entries = []
                for row in c.fetchall():
                    entries.append(LoraHistoryEntry(
                        id=row[0],
                        file_name=row[1],
                        display_name=row[2],
                        trigger_words=row[3],
                        weight=row[4],
                        url=row[5] if len(row) > 5 else "",
                        is_active=bool(row[6] if len(row) > 6 else True),
                        display_order=row[7]
                    ))
                return entries
        except Exception as e:
            logger.error(f"Error getting LoRA history: {e}")
            return []

    def get_lora_by_filename(self, file_name: str) -> Optional[LoraHistoryEntry]:
        """Get a specific LoRA entry by filename"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM lora_history WHERE file_name = ?', (file_name,))
                row = c.fetchone()
                if row:
                    return LoraHistoryEntry(
                        id=row[0],
                        file_name=row[1],
                        display_name=row[2],
                        trigger_words=row[3],
                        weight=row[4],
                        url=row[5] if len(row) > 5 else "",
                        is_active=bool(row[6] if len(row) > 6 else True),
                        display_order=row[7]
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting LoRA by filename: {e}")
            return None

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

    def sync_with_json(self, config: dict):
        """Sync database with JSON configuration"""
        try:
            if "available_loras" not in config:
                logger.warning("No available_loras found in config")
                return
                
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Add each lora from the JSON to the database
                for lora in config["available_loras"]:
                    # Handle both old 'prompt' and new 'add_prompt' keys
                    trigger_words = lora.get("add_prompt", lora.get("prompt", ""))
                    entry = LoraHistoryEntry(
                        file_name=lora["file"],
                        display_name=lora["name"],
                        trigger_words=trigger_words,
                        weight=float(lora.get("weight", 1.0)),
                        url=lora.get("url", ""),
                        is_active=True,
                        id=lora.get("id"),  # Use the ID from JSON directly
                        display_order=lora.get("display_order", 0)
                    )
                    # Pass the ID to add_lora
                    self.add_lora(entry, order=entry.display_order)
                    
            conn.commit()
            logger.info(f"Synced {len(config['available_loras'])} entries from JSON")
            
        except Exception as e:
            logger.error(f"Error syncing with JSON: {e}")
            raise

    def export_to_json(self) -> Dict:
        """Export active LoRA entries to JSON format"""
        try:
            entries = self.get_lora_history(include_inactive=False)
            loras = []
            for entry in entries:
                loras.append({
                    'id': entry.id,  # Use the original ID from the database
                    'name': entry.display_name,
                    'file': entry.file_name,
                    'weight': entry.weight,
                    'add_prompt': entry.trigger_words,
                    'url': entry.url,
                    'display_order': entry.display_order
                })
            return {'default': '', 'available_loras': loras}
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return {'default': '', 'available_loras': []}

    def update_entry(self, old_file_name: str, entry: dict) -> bool:
        """Update an existing LoRA entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''UPDATE lora_history 
                           SET file_name = ?, display_name = ?, trigger_words = ?, 
                               weight = ?, url = ?, is_active = ?, display_order = ?
                           WHERE file_name = ?''',
                        (entry["file_name"], entry["display_name"], entry["trigger_words"],
                         entry["weight"], entry["url"], entry["is_active"], entry["display_order"], old_file_name))
                conn.commit()
                logger.debug(f"Updated LoRA: {old_file_name} -> {entry['file_name']}")
                return True
        except Exception as e:
            logger.error(f"Error updating LoRA entry: {e}")
            return False

    def delete_entry(self, file_name: str) -> bool:
        """Delete a LoRA entry from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('DELETE FROM lora_history WHERE file_name = ?', (file_name,))
                conn.commit()
                logger.debug(f"Deleted LoRA: {file_name}")
                return True
        except Exception as e:
            logger.error(f"Error deleting LoRA entry: {e}")
            return False