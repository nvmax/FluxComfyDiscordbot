import discord
from discord.ext import commands as discord_commands
import asyncio
import subprocess
import os
import platform
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
from Main.custom_commands import RequestItem, ImageControlView, setup_commands
from Main.database import init_db, get_all_image_info
from Main.custom_commands.web_handlers import handle_generated_image
from Main.utils import load_json
from web_server import start_web_server
from Main.lora_monitor import setup_lora_monitor, cleanup_lora_monitor
try:
    from LMstudio_bot.ai_providers import AIProviderFactory
except ImportError:
    print("Warning: AIProviderFactory not found. Prompt enhancement will be disabled.")
    AIProviderFactory = None

import logging
import json
import uuid


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce discord.py websocket spam
discord_logger = logging.getLogger('discord.gateway')
discord_logger.setLevel(logging.WARNING)

class MyBot(discord_commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self.subprocess_queue = asyncio.Queue()
        self.pending_requests = {}
        self.allowed_channels = CHANNEL_IDS
        self.resolution_options = []
        self.lora_options = []
        self.tree.on_error = self.on_tree_error
        setup_lora_monitor(self)
        
        # Initialize AI provider if prompt enhancement is enabled
        self.ai_provider = None
        if ENABLE_PROMPT_ENHANCEMENT:
            try:
                self.ai_provider = AIProviderFactory.get_provider(AI_PROVIDER)
                logger.info(f"Initialized {AI_PROVIDER} provider for prompt enhancement")
            except Exception as e:
                logger.error(f"Failed to initialize AI provider: {e}")

    def get_python_command(self):
        """Get the appropriate Python command based on the platform"""
        if platform.system() == "Windows":
            return "python"
        return "python3"

    async def setup_hook(self):
        init_db()
        try:
            ratios_data = load_json('ratios.json')
            self.resolution_options = list(ratios_data['ratios'].keys())

            lora_data = load_json('lora.json')
            self.lora_options = lora_data['available_loras']
            
            # Test AI provider connection if enabled
            if ENABLE_PROMPT_ENHANCEMENT and self.ai_provider:
                try:
                    if await self.ai_provider.test_connection():
                        logger.info("AI provider connection test successful")
                    else:
                        logger.warning("AI provider connection test failed")
                except Exception as e:
                    logger.error(f"AI provider connection test error: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading options: {str(e)}")

        # Set up commands first
        await setup_commands(self)
        self.loop.create_task(self.process_subprocess_queue())
        await start_web_server(self)

        # Sync commands after setup
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands during setup")
        except Exception as e:
            logger.error(f"Failed to sync commands during setup: {e}")

        image_info = get_all_image_info()
        for info in image_info:
            self.add_view(ImageControlView(
                self,
                original_prompt=info[2],
                image_filename=info[4],
                original_resolution=info[5],
                original_loras=json.loads(info[7]),
                original_upscale_factor=info[8]
            ))

    async def close(self):
        cleanup_lora_monitor(self)
        await super().close()

    async def process_subprocess_queue(self):
        while True:
            try:
                request_item = await self.subprocess_queue.get()
                request_id = str(uuid.uuid4())
                self.pending_requests[request_id] = request_item
                await asyncio.sleep(5)

                python_cmd = self.get_python_command()
                
                subprocess.Popen([
                    python_cmd,
                    'comfygen.py',  
                    request_id,
                    request_item.user_id,
                    request_item.channel_id,
                    request_item.interaction_id,
                    request_item.original_message_id,
                    request_item.prompt,
                    request_item.resolution,
                    json.dumps(request_item.loras),
                    str(request_item.upscale_factor),
                    request_item.workflow_filename,
                    str(request_item.seed)
                ])
                self.subprocess_queue.task_done()
            except Exception as e:
                logger.error(f"Error in process_subprocess_queue: {e}")

    async def on_ready(self):
        logger.info(f"Bot {self.user} is ready")
        await self.change_presence(activity=discord.Game(name="with image generation"))
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands after ready")
        except Exception as e:
            logger.error(f"Failed to sync commands after ready: {e}")

    async def on_tree_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Command is on cooldown. Try again in {error.retry_after:.2f}s",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"An error occurred: {str(error)}",
                ephemeral=True
            )

    async def enhance_prompt(self, prompt: str, creativity: int) -> str:
        """
        Enhance the prompt using the configured AI provider.
        Returns the original prompt if enhancement fails or is disabled.
        """
        if not ENABLE_PROMPT_ENHANCEMENT or not self.ai_provider:
            return prompt

        try:
            prompt_enhancer = PromptEnhancer()
            enhanced_prompt = prompt_enhancer.enhance_prompt(prompt, creativity=creativity)
            if enhanced_prompt:
                logger.debug(f"Enhanced prompt from '{prompt}' to '{enhanced_prompt}'")
                return enhanced_prompt
            
            return prompt
            
        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}")
            return prompt

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
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())