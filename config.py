import os
from dotenv import load_dotenv
import discord

load_dotenv()

# Server configurations
BOT_SERVER = os.getenv('BOT_SERVER', 'localhost')
server_address = os.getenv('server_address')

# Discord configurations
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX')
CHANNEL_IDS = [int(id) for id in os.getenv('CHANNEL_IDS').split(',')]
ALLOWED_SERVERS = [int(id) for id in os.getenv('ALLOWED_SERVERS').split(',')]
BOT_MANAGER_ROLE_ID = int(os.getenv('BOT_MANAGER_ROLE_ID'))
fluxversion = os.getenv('fluxversion')

# LMStudio Integration
ENABLE_PROMPT_ENHANCEMENT = os.getenv('ENABLE_PROMPT_ENHANCEMENT', 'false').lower() == 'true'
LMSTUDIO_HOST = os.getenv('LMSTUDIO_HOST', 'localhost')
LMSTUDIO_PORT = os.getenv('LMSTUDIO_PORT', '1234')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'lmstudio')  # Options: lmstudio, openai, xai
XAI_API_KEY = os.getenv('XAI_API_KEY', '')
XAI_MODEL = os.getenv('XAI_MODEL', 'grok-beta')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002')

# Discord intents
intents = discord.Intents.default()
intents.message_content = True

__all__ = [
    'BOT_SERVER',
    'server_address',
    'DISCORD_TOKEN',
    'COMMAND_PREFIX',
    'CHANNEL_IDS',
    'ALLOWED_SERVERS',
    'BOT_MANAGER_ROLE_ID',
    'fluxversion',
    'ENABLE_PROMPT_ENHANCEMENT',
    'LMSTUDIO_HOST',
    'LMSTUDIO_PORT',
    'AI_PROVIDER',
    'XAI_API_KEY',
    'XAI_MODEL',
    'OPENAI_API_KEY',
    'OPENAI_MODEL',
    'EMBEDDING_MODEL',
    'intents'
]