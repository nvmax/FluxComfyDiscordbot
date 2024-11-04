import logging
import argparse
from setup_support import SetupManager
import setup_ui
import argparse
import os

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

def main():
    parser = argparse.ArgumentParser(description='FLUX ComfyUI Setup')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode instead of GUI')
    args = parser.parse_args()

    try:
        if args.cli:
            # CLI mode
            setup_manager = SetupManager()
            setup_manager.run_setup()
        else:
            # GUI mode (default)
            setup_ui.main()
            
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()