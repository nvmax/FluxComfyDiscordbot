import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import re
import sys

logger = logging.getLogger(__name__)

def load_env(root_dir: Path):
    """Load environment variables from .env file"""
    try:
        # List of potential .env file locations
        potential_paths = [
            root_dir / '.env',  # Original location
            Path(root_dir).parent / '.env',  # One level up
            Path(root_dir).parent.parent / '.env',  # Two levels up (root directory)
        ]
        
        # Try each location until we find a .env file
        for env_path in potential_paths:
            if env_path.exists():
                logger.info(f"Loading .env from: {env_path}")
                load_dotenv(env_path)
                return True
                
        logger.warning("No .env file found in any of the expected locations")
        return False
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
        return False

def update_env_file(key: str, value: str):
    """Update a value in the .env file"""
    try:
        # Get the correct base path whether running as exe or script
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_paths = [
                Path(sys.executable).parent.parent,  # Two levels up from exe
                Path(sys.executable).parent.parent.parent,  # Three levels up (root directory)
            ]
        else:
            # Running as script
            base_paths = [
                Path(__file__).parent.parent.parent,  # Project root when running as script
            ]
        
        # Try to find existing .env file
        env_path = None
        for base_path in base_paths:
            temp_path = base_path / '.env'
            if temp_path.exists():
                env_path = temp_path
                break
        
        # If no existing .env found, use the first base path
        if not env_path:
            env_path = base_paths[0] / '.env'
        
        # Read existing content
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Find and update the key
        key_found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                key_found = True
                break
        
        # Add key if not found
        if not key_found:
            lines.append(f"{key}={value}\n")
        
        # Write back to file
        with open(env_path, 'w') as f:
            f.writelines(lines)
            
        return True
        
    except Exception as e:
        logger.error(f"Error updating .env file: {e}")
        return False

def load_json_config(json_path: str) -> dict:
    """Load JSON configuration file"""
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"default": "", "available_loras": []}
    except Exception as e:
        logger.error(f"Error loading JSON config: {e}")
        return {"default": "", "available_loras": []}

def save_json_config(json_path: str, config: dict) -> bool:
    """Save configuration to JSON file"""
    try:
        # Ensure all entries in loras have IDs
        if "loras" in config:
            for lora in config["loras"]:
                if "id" not in lora:
                    logger.warning(f"Missing ID for lora: {lora.get('name', 'unknown')}")
        
        # Save with proper formatting
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON config: {e}")
        return False

def sanitize_filename(filename: str) -> str:
    """Remove or replace characters that are invalid in Windows filenames"""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    return sanitized[:240]  # Windows max path length is 260, leave room for directory
