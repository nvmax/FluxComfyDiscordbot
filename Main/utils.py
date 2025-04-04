import json
import logging
import random
import os
import math
from typing import Any, Dict, Union, Optional

logger = logging.getLogger(__name__)

def load_json(filename):
    """Load JSON file with error handling and encoding fallback"""
    # Try both case variations of the directory name
    possible_paths = [
        os.path.join('Main', 'Datasets', filename),
        os.path.join('Main', 'DataSets', filename),
        filename  # Also try the direct path if provided
    ]

    filepath = None
    for path in possible_paths:
        if os.path.exists(path):
            filepath = path
            break

    if not filepath:
        logger.error(f"File not found: {filename} (tried paths: {', '.join(possible_paths)})")
        raise FileNotFoundError(f"JSON file not found: {filename}")

    try:
        # First try UTF-8
        with open(filepath, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in {filename}: {str(e)}")
                raise ValueError(f"Invalid JSON format in {filename}: {str(e)}")
    except UnicodeDecodeError:
        # Fallback to ISO-8859-1
        logger.warning(f"UTF-8 decode failed for {filename}, trying ISO-8859-1")
        with open(filepath, 'r', encoding='iso-8859-1') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in {filename}: {str(e)}")
                raise ValueError(f"Invalid JSON format in {filename}: {str(e)}")

def save_json(filename, data):
    """Save data to JSON file with error handling"""
    # Try both case variations of the directory name
    possible_paths = [
        os.path.join('Main', 'Datasets', filename),
        os.path.join('Main', 'DataSets', filename)
    ]

    filepath = None
    for path in possible_paths:
        if os.path.exists(os.path.dirname(path)):
            filepath = path
            break

    if not filepath:
        logger.error(f"Directory not found: {filename} (tried paths: {', '.join(possible_paths)})")
        raise FileNotFoundError(f"Directory not found: {filename}")

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        logger.debug(f"Successfully saved {filename}")
    except Exception as e:
        logger.error(f"Error saving {filename}: {str(e)}")
        raise

def generate_random_seed():
    """Generate a random seed for image generation"""
    return random.randint(0, 2**32 - 1)

def format_time_delta(seconds):
    """Format a time delta in seconds to a human-readable string"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f} hours"
    else:
        days = seconds / 86400
        return f"{days:.1f} days"

def get_user_priority(bot, user_id, default=1):
    """Get the priority level for a user"""
    if hasattr(bot, "user_priorities") and user_id in bot.user_priorities:
        return bot.user_priorities[user_id]
    return default
