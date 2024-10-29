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

# Discord intents
intents = discord.Intents.default()
intents.message_content = True