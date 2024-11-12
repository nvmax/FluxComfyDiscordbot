import os
import logging
import argparse
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/setup.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def run_gui():
    import setup_ui
    setup_ui.main()

def main():
    parser = argparse.ArgumentParser(description='FLUX ComfyUI Setup')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode instead of GUI')
    args = parser.parse_args()

    try:
        if args.cli:
            from setup_support import SetupManager
            setup_manager = SetupManager()
            setup_manager.run_setup()
        else:
            run_gui()
            
    except Exception as e:
        logging.error(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()