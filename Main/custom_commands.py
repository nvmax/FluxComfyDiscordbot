from discord import app_commands
from discord.ext import commands as discord_commands
from typing import Optional
import asyncio
import logging
import uuid
import time
import discord

from custom_commands.views import OptionsView, ImageControlView, LoRASelectView
from custom_commands.models import RequestItem
from custom_commands.command_handlers import setup_commands
from custom_commands.web_handlers import handle_generated_image
from custom_commands.banned_utils import check_banned
from custom_commands.workflow_utils import update_workflow
from utils import load_json, save_json, generate_random_seed
from aiohttp import web


logger = logging.getLogger(__name__)

def in_allowed_channel():
    async def predicate(interaction: discord.Interaction):
        allowed_channels = interaction.client.allowed_channels
        if interaction.channel_id not in allowed_channels:
            await interaction.response.send_message("This command can only be used in specific channels.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

@app_commands.command(name="comfy", description="Generate an image based on a prompt.")
@in_allowed_channel()
@app_commands.describe(
    prompt="Enter your prompt",
    resolution="Choose the resolution",
    upscale_factor="Choose upscale factor (1-4, default is 1)",
    seed="Enter a seed for reproducibility (optional)"
)
@app_commands.choices(resolution=[
    app_commands.Choice(name=name, value=name) for name in load_json('ratios.json')['ratios'].keys()
])
@app_commands.choices(upscale_factor=[
    app_commands.Choice(name=str(i), value=i) for i in range(1, 5)
])
async def comfy(interaction: discord.Interaction, prompt: str, resolution: str, upscale_factor: int = 1, seed: Optional[int] = None):
    try:
        logger.info(f"Comfy command invoked by {interaction.user.id}")
        
        is_banned, ban_message = check_banned(str(interaction.user.id), prompt)
        if is_banned:
            await interaction.response.send_message(ban_message, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        logger.debug("Creating LoRA selection view")
        
        lora_view = LoRASelectView(interaction.client, [])
        lora_message = await interaction.followup.send("Please select the LoRAs you want to use:", view=lora_view)
        lora_view.interaction = await interaction.original_response()
        
        def check(i: discord.Interaction):
            return (i.data["component_type"] == 3 and 
                   i.user.id == interaction.user.id and 
                   i.message.id == lora_message.id)
        
        try:
            logger.debug("Waiting for LoRA selection")
            lora_interaction = await interaction.client.wait_for('interaction', timeout=300.0, check=check)
            selected_loras = lora_view.lora_select.values
            logger.debug(f"Selected LoRAs: {selected_loras}")
            
            await lora_interaction.response.defer(ephemeral=True)
            await lora_message.delete()
        except asyncio.TimeoutError:
            logger.warning("LoRA selection timed out")
            await lora_message.edit(content="LoRA selection timed out. Please try again.", view=None)
            return
        except Exception as e:
            logger.error(f"Error during LoRA selection: {str(e)}", exc_info=True)
            await interaction.followup.send(f"An error occurred during LoRA selection: {str(e)}", ephemeral=True)
            return

        additional_prompts = []
        lora_config = load_json('lora.json')
        for lora in selected_loras:
            lora_info = next((l for l in lora_config['available_loras'] if l['file'] == lora), None)
            if lora_info and lora_info.get('add_prompt'):
                additional_prompts.append(lora_info['add_prompt'])
        
        full_prompt = f"{prompt} {' '.join(additional_prompts)}".strip()
        
        if seed is None:
            seed = generate_random_seed()

        workflow = load_json('flux3.json')
        request_uuid = str(uuid.uuid4())
        current_timestamp = int(time.time())
        
        workflow = update_workflow(workflow, 
                               f"{full_prompt} (Timestamp: {current_timestamp})", 
                               resolution, 
                               selected_loras, 
                               upscale_factor,
                               seed)

        workflow_filename = f'flux3_{request_uuid}.json'
        save_json(workflow_filename, workflow) 

        original_message = await interaction.followup.send("Generating image... 0% complete", ephemeral=False)

        request_item = RequestItem(
            id=str(interaction.id),
            user_id=str(interaction.user.id),
            channel_id=str(interaction.channel.id),
            interaction_id=str(interaction.id),
            original_message_id=str(original_message.id),
            prompt=full_prompt,
            resolution=resolution,
            loras=selected_loras,
            upscale_factor=upscale_factor,
            workflow_filename=workflow_filename,
            seed=seed
        )
        await interaction.client.subprocess_queue.put(request_item)

    except Exception as e:
        logger.error(f"Error in comfy command: {str(e)}", exc_info=True)
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

async def update_progress(request):
    data = await request.json()
    request_id = data['request_id']
    progress = data['progress']
    if request_id in request.app['bot'].pending_requests:
        request_item = request.app['bot'].pending_requests[request_id]
        await update_progress_message(request.app['bot'], request_item, progress)
    return web.Response(text="Progress updated")

async def update_progress_message(bot, request_item, progress):
    try:
        channel = await bot.fetch_channel(int(request_item.channel_id))
        message = await channel.fetch_message(int(request_item.original_message_id))
        
        if progress % 10 == 0:
            await message.edit(content=f"Generating image... {progress}% complete")
            logger.debug(f"Updated progress message: {progress}%")
    except discord.errors.NotFound:
        logger.warning(f"Message {request_item.original_message_id} not found")
    except Exception as e:
        logger.error(f"Error updating progress message: {str(e)}")

async def setup(bot: discord_commands.Bot):
    try:
        await setup_commands(bot)
        bot.tree.add_command(comfy)
        logger.info("Successfully added comfy command")
    except Exception as e:
        logger.error(f"Error setting up commands: {str(e)}", exc_info=True)