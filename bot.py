import discord
from discord.ext import commands as discord_commands
import asyncio
import subprocess
import os
from config import (
    DISCORD_TOKEN, intents, COMMAND_PREFIX, 
    CHANNEL_IDS, ALLOWED_SERVERS, BOT_MANAGER_ROLE_ID
)
from Main.custom_commands import RequestItem, ImageControlView, setup_commands
from Main.database import init_db, get_all_image_info
from config import DISCORD_TOKEN, intents, COMMAND_PREFIX, CHANNEL_IDS, ALLOWED_SERVERS, BOT_MANAGER_ROLE_ID
from Main.custom_commands.web_handlers import handle_generated_image
from Main.utils import load_json
from web_server import start_web_server
import logging
import json
import uuid
## import comfygen.py from main directory



logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MyBot(discord_commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self.subprocess_queue = asyncio.Queue()
        self.pending_requests = {}
        self.allowed_channels = CHANNEL_IDS
        self.resolution_options = []
        self.lora_options = []
        self.tree.on_error = self.on_tree_error

    async def setup_hook(self):
        init_db()
        try:
            ratios_data = load_json('ratios.json')
            self.resolution_options = list(ratios_data['ratios'].keys())

            lora_data = load_json('lora.json')
            self.lora_options = lora_data['available_loras']
            logger.info("Loaded LoRA and Resolution options")
        except Exception as e:
            logger.error(f"Error loading options: {str(e)}")

        await setup_commands(self)
        self.loop.create_task(self.process_subprocess_queue())
        await start_web_server(self)

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

    async def process_subprocess_queue(self):
        while True:
            try:
                request_item = await self.subprocess_queue.get()
                request_id = str(uuid.uuid4())
                self.pending_requests[request_id] = request_item
                logger.debug(f"Processing subprocess queue: {request_item}")
                await asyncio.sleep(5)

                subprocess.Popen([
                    'python', 'comfygen.py',  # Now in root
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
            await self.tree.sync()
            logger.info("Successfully synced application commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_tree_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        logger.error(f"Command error occurred: {str(error)}")
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"Command is on cooldown. Try again in {error.retry_after:.2f}s", ephemeral=True)
        else:
            await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)

bot = MyBot()

async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
