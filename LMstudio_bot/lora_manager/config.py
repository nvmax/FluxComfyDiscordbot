"""Configuration settings for the LoRA manager."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LM Studio Configuration
LMSTUDIO_HOST = os.getenv("LMSTUDIO_HOST")
LMSTUDIO_PORT = os.getenv("LMSTUDIO_PORT")
CHAT_ENDPOINT = f"http://{LMSTUDIO_HOST}:{LMSTUDIO_PORT}/v1/chat/completions"

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

# Prompt Enhancement Configuration
DEFAULT_CREATIVITY = 5
MIN_CREATIVITY = 1
MAX_CREATIVITY = 10

# Results Configuration
DEFAULT_RESULTS = 3
MIN_RESULTS = 1
MAX_RESULTS = 5  # Changed from 10 to 5 to match the Discord UI limits
