import os
import logging
import argparse
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)
os.makedirs('Main/DataSets/temp', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Log to console
        logging.FileHandler('logs/setup.log', mode='w', encoding='utf-8')  # Log to file
    ]
)

# Set log level for all loggers
logging.getLogger().setLevel(logging.INFO)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.INFO)

logger = logging.getLogger(__name__)

def run_gui():
    import setup_ui
    setup_ui.main()

def main():
    parser = argparse.ArgumentParser(description='FLUX ComfyUI Setup')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode instead of GUI')
    args = parser.parse_args()

    print("\n!!!!!!!!!! STARTING SETUP !!!!!!!!!!")
    
    try:
        if args.cli:
            print("Running in CLI mode")
            from setup_support import SetupManager
            setup_manager = SetupManager()
            result = setup_manager.run_setup()
            print(f"\nSetup completed with result: {result}")
        else:
            print("Running in GUI mode")
            run_gui()
            
    except Exception as e:
        print(f"\nERROR: Setup failed: {str(e)}")
        logging.error(f"Setup failed: {str(e)}")
        raise
    
    print("\n!!!!!!!!!! SETUP FINISHED !!!!!!!!!!")

if __name__ == "__main__":
    main()