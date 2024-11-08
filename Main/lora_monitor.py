from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import json
import os
import time
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

class LoraFileHandler(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_modified = 0
        self.cooldown = 1  # Cooldown in seconds to prevent multiple reloads

    def reload_lora_config(self) -> bool:
        try:
            current_time = time.time()
            if current_time - self.last_modified < self.cooldown:
                return False

            self.last_modified = current_time
            
            # Load new lora configuration
            lora_path = Path('Main/DataSets/lora.json')
            if not lora_path.exists():
                logger.error("lora.json not found")
                return False

            with open(lora_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)

            # Update bot's lora options
            self.bot.lora_options = new_config.get('available_loras', [])
            logger.info(f"Reloaded LoRA config with {len(self.bot.lora_options)} entries")
            return True

        except Exception as e:
            logger.error(f"Error reloading LoRA config: {e}")
            return False

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('lora.json'):
            if self.reload_lora_config():
                logger.info("LoRA configuration reloaded successfully")

def setup_lora_monitor(bot) -> None:
    """Set up the LoRA file monitoring system"""
    try:
        event_handler = LoraFileHandler(bot)
        observer = Observer()
        
        # Watch the DataSets directory
        datasets_path = Path('Main/DataSets')
        observer.schedule(event_handler, str(datasets_path), recursive=False)
        observer.start()
        
        logger.info("LoRA file monitor started successfully")
        
        # Store observer in bot instance for cleanup
        bot.lora_observer = observer
        
    except Exception as e:
        logger.error(f"Failed to setup LoRA monitor: {e}")