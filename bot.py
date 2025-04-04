import discord
from discord.ext import commands as discord_commands
import asyncio
import subprocess
import os
import platform
import uuid
from typing import Dict, Optional, Any

# Third-party imports
from discord import Interaction, Intents, app_commands
from discord.ext import commands as discord_commands
import discord

# Local application imports
from config import (
    DISCORD_TOKEN,
    intents,
    COMMAND_PREFIX,
    CHANNEL_IDS,
    ALLOWED_SERVERS,
    BOT_MANAGER_ROLE_ID,
    ENABLE_PROMPT_ENHANCEMENT,
    AI_PROVIDER,
    LMSTUDIO_HOST,
    LMSTUDIO_PORT
)
from Main.custom_commands import (
    RequestItem, ReduxRequestItem, ReduxPromptRequestItem,
    ImageControlView, setup_commands
)
from Main.database import init_db, get_all_image_info
from Main.custom_commands.web_handlers import handle_generated_image
from Main.utils import load_json, get_user_priority
from web_server import start_web_server
from Main.lora_monitor import setup_lora_monitor, cleanup_lora_monitor
from Main.queue_system import ImageGenerationQueue, QueuePriority, QueueItem
from Main.custom_commands.queue_commands import setup_queue_commands
from Main.custom_commands.analytics_commands import setup_analytics_commands
from Main.custom_commands.filter_commands import setup_filter_commands
from Main.analytics import analytics_manager
try:
    from Main.LMstudio_bot.ai_providers import AIProviderFactory
except ImportError:
    print("Warning: AIProviderFactory not found. Prompt enhancement will be disabled.")
    AIProviderFactory = None

import logging
import json
import uuid
from discord import app_commands
from Main.custom_commands.views import ReduxModal, ImageControlView

# Configure logging
import logging

# Force all loggers to INFO level
logging.getLogger().setLevel(logging.INFO)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.INFO)

logging.basicConfig(
    force=True,  # Override any existing configuration
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce discord.py websocket spam but keep it at INFO
discord_logger = logging.getLogger('discord.gateway')
discord_logger.setLevel(logging.INFO)

class MyBot(discord_commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self.subprocess_queue = asyncio.Queue()  # Keep for backward compatibility
        self.pending_requests = {}  # Keep for backward compatibility
        self.ai_provider = None
        self.allowed_channels = set(CHANNEL_IDS)
        self.resolution_options = []
        self.lora_options = []
        self.tree.on_error = self.on_tree_error
        setup_lora_monitor(self)

        # Initialize the enhanced queue system
        self.image_queue = ImageGenerationQueue(max_concurrent=3, rate_limit=10)
        self.user_priorities = {}  # User ID -> priority level

    def get_python_command(self):
        """Get the appropriate Python command based on the platform"""
        if platform.system() == "Windows":
            return "python"
        return "python3"

    async def process_redux_request(self, request_id: str, request_item) -> None:
        """Process a redux image generation request."""
        try:
            # Create temp directory with absolute path
            temp_dir = os.path.abspath(os.path.join('Main', 'DataSets', 'temp'))
            os.makedirs(temp_dir, exist_ok=True)

            # Use the filenames from the request item
            image1_path = os.path.join(temp_dir, request_item.image1_filename)
            image2_path = os.path.join(temp_dir, request_item.image2_filename)

            # Save images with request ID in filenames
            with open(image1_path, 'wb') as f:
                f.write(request_item.image1)
            with open(image2_path, 'wb') as f:
                f.write(request_item.image2)

            # Convert to absolute paths and use forward slashes
            image1_path = image1_path.replace('\\', '/')
            image2_path = image2_path.replace('\\', '/')

            logger.debug(f"Saved images at: {image1_path}, {image2_path}")

            python_cmd = self.get_python_command()

            subprocess.Popen([
                python_cmd,
                'comfygen.py',
                request_id,
                request_item.user_id,
                request_item.channel_id,
                request_item.interaction_id,
                request_item.original_message_id,
                'redux',
                request_item.resolution,
                str(request_item.strength1),
                str(request_item.strength2),
                request_item.workflow_filename,
                image1_path,
                image2_path
            ])

            logger.debug(f"Started redux processing for request {request_id}")

        except Exception as e:
            logger.error(f"Error in process_redux_request: {e}", exc_info=True)
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            raise

    async def process_subprocess_queue(self):
        while True:
            try:
                # Get request from old queue for backward compatibility
                request_item = await self.subprocess_queue.get()

                # Add to new queue system with appropriate priority
                priority = get_user_priority(self, str(request_item.user_id), QueuePriority.NORMAL)
                success, request_id, message = await self.image_queue.add_request(request_item, priority)

                if success:
                    # Store in pending_requests for backward compatibility
                    self.pending_requests[request_id] = request_item
                    logger.info(f"Added request to queue: {request_id} - {message}")
                else:
                    logger.warning(f"Failed to add request to queue: {message}")

                # Mark task as done in old queue
                self.subprocess_queue.task_done()

            except Exception as e:
                logger.error(f"Error in process_subprocess_queue: {e}")

    async def process_queue_item(self, queue_item):
        """Process a queue item from the enhanced queue system"""
        try:
            request_id = queue_item.request_id
            request_item = queue_item.request_item

            # Store in pending_requests for backward compatibility
            self.pending_requests[request_id] = request_item

            if isinstance(request_item, ReduxRequestItem):
                # Process Redux request
                await self.process_redux_request(request_id, request_item)
                return True
            elif isinstance(request_item, ReduxPromptRequestItem):
                # Process ReduxPrompt request
                python_cmd = self.get_python_command()
                subprocess.Popen([
                    python_cmd,
                    'comfygen.py',
                    request_id,
                    request_item.user_id,
                    request_item.channel_id,
                    request_item.interaction_id,
                    request_item.original_message_id,
                    'reduxprompt',
                    request_item.prompt,
                    request_item.resolution,
                    str(request_item.strength),
                    request_item.workflow_filename,
                    request_item.image_path  # Use the already saved image path
                ])
                return True
            else:
                # Standard request processing
                python_cmd = self.get_python_command()
                subprocess.Popen([
                    python_cmd,
                    'comfygen.py',
                    request_id,
                    request_item.user_id,
                    request_item.channel_id,
                    request_item.interaction_id,
                    request_item.original_message_id,
                    'standard',  # Indicate this is a standard request
                    request_item.prompt,
                    request_item.resolution,
                    json.dumps(request_item.loras),
                    str(request_item.upscale_factor),
                    request_item.workflow_filename,  # Pass the workflow filename
                    str(request_item.seed) if request_item.seed is not None else "None",
                    str(request_item.is_pulid).lower()  # Pass is_pulid flag
                ])
                return True

        except Exception as e:
            logger.error(f"Error processing queue item: {e}")
            return False

    async def setup_hook(self):
        """Setup hook that runs before the bot starts."""
        logger.info("=== Starting Bot Setup ===")
        logger.info("Initializing database...")
        init_db()

        logger.info("Setting up AI provider...")
        try:
            if ENABLE_PROMPT_ENHANCEMENT and AIProviderFactory:
                logger.info(f"Initializing AI provider. Provider: {AI_PROVIDER}")
                self.ai_provider = AIProviderFactory.get_provider(AI_PROVIDER)
                logger.info(f"AI provider type: {type(self.ai_provider)}")
                logger.info(f"AI provider attributes: {dir(self.ai_provider)}")
                logger.info(f"Initialized {AI_PROVIDER} provider for prompt enhancement")

                # Test the connection
                connection_ok = await self.ai_provider.test_connection()
                if connection_ok:
                    logger.info("AI provider connection test successful")
                else:
                    logger.error("AI provider connection test failed")
            else:
                logger.info("Prompt enhancement is disabled")
        except Exception as e:
            logger.error(f"Error initializing AI provider: {e}", exc_info=True)
            self.ai_provider = None

        logger.info("Loading configuration files...")
        try:
            ratios_data = load_json('ratios.json')
            self.resolution_options = list(ratios_data['ratios'].keys())
            logger.info(f"Loaded {len(self.resolution_options)} resolution options")

            lora_data = load_json('lora.json')
            self.lora_options = lora_data['available_loras']
            logger.info(f"Loaded {len(self.lora_options)} LoRA options")

            # Register redux command after options are loaded
            logger.info("Registering redux command...")

            @self.tree.command(
                name="redux",
                description="Generate an image using two reference images"
            )
            @app_commands.describe(
                resolution="Choose the resolution for the output image"
            )
            @app_commands.choices(resolution=[
                app_commands.Choice(name=str(name), value=str(name))
                for name in self.resolution_options
            ])
            async def redux(interaction: discord.Interaction, resolution: str):
                try:
                    # Check if channel is allowed
                    if interaction.channel_id not in self.allowed_channels:
                        await interaction.response.send_message(
                            "This command can only be used in specific channels.",
                            ephemeral=True
                        )
                        return

                    # Show the modal for image upload and strength settings
                    modal = ReduxModal(self, resolution)
                    await interaction.response.send_modal(modal)

                except Exception as e:
                    logger.error(f"Error in redux command: {e}", exc_info=True)
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
            raise

        logger.info("Setting up commands and views...")
        # Register commands
        await setup_commands(self)

        # Register persistent views
        from Main.custom_commands.views import PuLIDImageView, ReduxImageView, ImageControlView
        PuLIDImageView.register_view(self)
        ReduxImageView.register_view(self)
        ImageControlView.register_view(self)
        logger.info("Views registered successfully")

        # Start processing subprocess queue (for backward compatibility)
        logger.info("Starting subprocess queue...")
        self.bg_task = self.loop.create_task(self.process_subprocess_queue())

        # Start enhanced queue processing
        logger.info("Starting enhanced image queue...")
        self.queue_task = self.loop.create_task(self.image_queue.process_queue(self.process_queue_item))

        # Setup queue commands
        logger.info("Setting up queue commands...")
        await setup_queue_commands(self)

        # Setup analytics commands
        logger.info("Setting up analytics commands...")
        await setup_analytics_commands(self)

        # Setup filter commands
        logger.info("Setting up filter commands...")
        await setup_filter_commands(self)

        logger.info("Starting web server...")
        await start_web_server(self)

        # Sync commands with Discord
        logger.info("Syncing commands with Discord...")
        try:
            if not ALLOWED_SERVERS:
                logger.warning("No allowed servers configured, syncing globally")
                await self.tree.sync()
            else:
                for server_id in ALLOWED_SERVERS:
                    try:
                        guild = discord.Object(id=int(server_id))
                        await self.tree.sync(guild=guild)
                        logger.info(f"Synced commands to guild {server_id}")
                    except Exception as e:
                        logger.error(f"Failed to sync commands to guild {server_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)
            raise

    async def close(self):
        cleanup_lora_monitor(self)
        await super().close()

    async def on_ready(self):
        logger.info(f"=== Bot Ready: {self.user} ===")
        await self.change_presence(activity=discord.Game(name="with image generation"))
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Command is on cooldown. Try again in {error.retry_after:.2f}s",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"An error occurred: {str(error)}",
                ephemeral=True
            )

    async def reload_options(self):
        """Reload LoRA and Resolution options"""
        try:
            ratios_data = load_json('ratios.json')
            self.resolution_options = list(ratios_data['ratios'].keys())

            lora_data = load_json('lora.json')
            self.lora_options = lora_data['available_loras']
            logger.info("Successfully reloaded options")

            # Reinitialize AI provider if enabled
            if ENABLE_PROMPT_ENHANCEMENT:
                try:
                    self.ai_provider = AIProviderFactory.get_provider(AI_PROVIDER)
                    if await self.ai_provider.test_connection():
                        logger.info("Successfully reconnected to AI provider")
                    else:
                        logger.warning("Failed to reconnect to AI provider")
                except Exception as e:
                    logger.error(f"Failed to reinitialize AI provider: {e}")
                    self.ai_provider = None

        except Exception as e:
            logger.error(f"Error reloading options: {e}")
            raise

bot = MyBot()

async def main():
    logger.info("=== Starting Bot Process ===")
    if not DISCORD_TOKEN:
        logger.error("No Discord token found. Please check your .env file")
        return

    try:
        async with bot:
            logger.info("Initializing bot connection...")
            await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())