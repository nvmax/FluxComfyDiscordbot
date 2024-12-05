import json
import logging
import random
import os

logger = logging.getLogger(__name__)

def load_json(filename):
    """Load JSON file with error handling and encoding fallback"""
    filepath = f'Main/DataSets/{filename}'
    
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
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
    filepath = f'Main/DataSets/{filename}'
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
