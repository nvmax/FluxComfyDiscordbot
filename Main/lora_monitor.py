from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import json
import os
import time
from typing import Optional, Dict, List
from pathlib import Path
from threading import Lock, Timer

logger = logging.getLogger(__name__)

class DebounceTimer:
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback
        self.timer = None
        self.lock = Lock()

    def debounce(self):
        with self.lock:
            if self.timer is not None:
                self.timer.cancel()
            self.timer = Timer(self.timeout, self.callback)
            self.timer.start()

class LoraFileHandler(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_valid_config = None
        self.lock = Lock()
        self.debouncer = DebounceTimer(0.5, self.reload_lora_config)  # 500ms debounce
        self.processing = False

    def is_valid_json(self, file_path: str) -> bool:
        try:
            if not os.path.exists(file_path):
                return False
                
            if os.path.getsize(file_path) == 0:
                logger.error("lora.json is empty")
                return False
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logger.error("lora.json is empty after trimming whitespace")
                    return False
                    
                config = json.loads(content)
                
            if not isinstance(config, dict):
                return False
            if 'available_loras' not in config:
                return False
            if not isinstance(config['available_loras'], list):
                return False
                
            for lora in config['available_loras']:
                if not all(key in lora for key in ['id', 'name', 'file', 'weight']):
                    logger.error(f"Invalid LoRA entry structure: {lora}")
                    return False
                    
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False

    def reload_lora_config(self) -> bool:
        with self.lock:
            if self.processing:
                return False
            self.processing = True
            
        try:
            lora_path = Path('Main/DataSets/lora.json')
            if not self.is_valid_json(str(lora_path)):
                logger.error("Invalid lora.json file")
                if self.last_valid_config:
                    with open(lora_path, 'w', encoding='utf-8') as f:
                        json.dump(self.last_valid_config, f, indent=2)
                    logger.info("Restored last valid configuration")
                return False

            with open(lora_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
                
            self.last_valid_config = new_config
            self.bot.lora_options = new_config.get('available_loras', [])
            logger.info(f"Reloaded LoRA config with {len(self.bot.lora_options)} entries")
            return True

        except Exception as e:
            logger.error(f"Error reloading LoRA config: {e}")
            if self.last_valid_config:
                try:
                    with open(lora_path, 'w', encoding='utf-8') as f:
                        json.dump(self.last_valid_config, f, indent=2)
                    logger.info("Restored last valid configuration after error")
                except Exception as restore_error:
                    logger.error(f"Failed to restore configuration: {restore_error}")
            return False
        finally:
            self.processing = False

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('lora.json'):
            self.debouncer.debounce()

def setup_lora_monitor(bot) -> None:
    """Set up the LoRA file monitoring system"""
    try:
        event_handler = LoraFileHandler(bot)
        observer = Observer()
        
        datasets_path = Path('Main/DataSets')
        if not datasets_path.exists():
            logger.error(f"DataSets directory not found: {datasets_path}")
            return
            
        observer.schedule(event_handler, str(datasets_path), recursive=False)
        
        # Load initial configuration
        event_handler.reload_lora_config()
        
        observer.start()
        logger.info("LoRA file monitor started successfully")
        
        # Store observer and handler in bot instance for cleanup
        bot.lora_observer = observer
        bot.lora_handler = event_handler
        
    except Exception as e:
        logger.error(f"Failed to setup LoRA monitor: {e}")

def cleanup_lora_monitor(bot):
    """Clean up LoRA monitor resources"""
    try:
        if hasattr(bot, 'lora_handler'):
            if hasattr(bot.lora_handler, 'debouncer'):
                if bot.lora_handler.debouncer.timer:
                    bot.lora_handler.debouncer.timer.cancel()
        
        if hasattr(bot, 'lora_observer'):
            bot.lora_observer.stop()
            bot.lora_observer.join()
            
    except Exception as e:
        logger.error(f"Error during LoRA monitor cleanup: {e}")