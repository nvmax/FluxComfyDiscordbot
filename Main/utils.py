import json
import logging
import random

logger = logging.getLogger(__name__)

def load_json(filename):
    try:
        with open(f'Main/DataSets/{filename}', 'r', encoding='utf-8') as file:
            return json.load(file)
    except UnicodeDecodeError:
        with open(f'Main/DataSets/{filename}', 'r', encoding='iso-8859-1') as file:
            return json.load(file)

def save_json(filename, data):
    with open(f'Main/DataSets/{filename}', 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def generate_random_seed():
    return random.randint(0, 2**32 - 1)

