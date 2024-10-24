import discord
from discord import app_commands
from discord.ext import commands as discord_commands
from config import BOT_MANAGER_ROLE_ID, CHANNEL_IDS
import logging
import os
import sys
import uuid
import time
import sqlite3
from typing import Optional
from config import BOT_MANAGER_ROLE_ID, CHANNEL_IDS

from Main.database import (
    DB_NAME, ban_user, unban_user, 
    get_ban_info, is_user_banned
)
from Main.utils import load_json, save_json, generate_random_seed
from Main.custom_commands.views import OptionsView, LoRAView
from Main.custom_commands.models import RequestItem
from Main.custom_commands.banned_utils import check_banned, load_banned_data, save_banned_data
from Main.custom_commands.workflow_utils import update_workflow

logger = logging.getLogger(__name__)

def has_admin_or_bot_manager_role():
    async def predicate(interaction: discord.Interaction):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = any(role.id == BOT_MANAGER_ROLE_ID for role in interaction.user.roles)
        if is_admin or has_role:
            return True
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

def in_allowed_channel():
    async def predicate(interaction: discord.Interaction):
        if interaction.channel_id not in CHANNEL_IDS:
            await interaction.response.send_message("This command can only be used in specific channels.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

async def setup_commands(bot: discord.Client):
    @bot.tree.command(name="comfy", description="Generate an image based on a prompt")
    @in_allowed_channel()
    @app_commands.describe(
        prompt="Enter your prompt",
        resolution="Choose the resolution",
        upscale_factor="Choose upscale factor (1-4, default is 1)",
        seed="Enter a seed for reproducibility (optional)"
    )
    @app_commands.choices(resolution=[
        app_commands.Choice(name=name, value=name) 
        for name in load_json('ratios.json')['ratios'].keys()
    ])
    @app_commands.choices(upscale_factor=[
        app_commands.Choice(name=str(i), value=i) for i in range(1, 5)
    ])
    async def comfy(interaction: discord.Interaction, prompt: str, resolution: str, 
                   upscale_factor: int = 1, seed: Optional[int] = None):
        try:
            is_banned, ban_message = check_banned(str(interaction.user.id), prompt)
            if is_banned:
                await interaction.response.send_message(ban_message, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            
            view = LoRAView(interaction.client)
            msg = await interaction.followup.send("Please select LoRAs to use:", view=view, ephemeral=True)
            
            timeout = await view.wait()
            if timeout:
                await msg.delete()
                return

            selected_loras = view.selected_loras
            await msg.delete()

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

    @bot.tree.command(name="reboot", description="Reboot the bot (Restricted to specific admin)")
    async def reboot(interaction: discord.Interaction):
        if interaction.user.id == BOT_MANAGER_ROLE_ID:
            await interaction.response.send_message("Rebooting bot...", ephemeral=True)
            await bot.close()
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            await interaction.response.send_message("You don't have permission.", ephemeral=True)

    @bot.tree.command(name="add_banned_word", description="Add a word to the banned list")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_banned_word(interaction: discord.Interaction, word: str):
        banned_data = load_banned_data()
        if word.lower() not in banned_data['banned_words']:
            banned_data['banned_words'].append(word.lower())
            save_banned_data(banned_data)
            await interaction.response.send_message(f"Added '{word}' to the banned words list.", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{word}' is already in the banned words list.", ephemeral=True)

    @bot.tree.command(name="remove_banned_word", description="Remove a word from the banned list")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_banned_word(interaction: discord.Interaction, word: str):
        banned_data = load_banned_data()
        if word.lower() in banned_data['banned_words']:
            banned_data['banned_words'].remove(word.lower())
            save_banned_data(banned_data)
            await interaction.response.send_message(f"Removed '{word}' from the banned words list.", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{word}' is not in the banned words list.", ephemeral=True)

    @bot.tree.command(name="list_banned_words", description="List all banned words")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_banned_words(interaction: discord.Interaction):
        banned_data = load_banned_data()
        banned_words = banned_data['banned_words']
        if banned_words:
            await interaction.response.send_message(f"Banned words: {', '.join(banned_words)}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no banned words.", ephemeral=True)

    @bot.tree.command(name="ban_user", description="Ban a user from using the comfy command")
    @app_commands.checks.has_permissions(administrator=True)
    async def ban_user_command(interaction: discord.Interaction, user: discord.User, reason: str):
        ban_user(str(user.id), reason)
        await interaction.response.send_message(f"Banned {user.name} from using the comfy command. Reason: {reason}", ephemeral=True)

    @bot.tree.command(name="unban_user", description="Unban a user from using the comfy command")
    @app_commands.checks.has_permissions(administrator=True)
    async def unban_user_command(interaction: discord.Interaction, user: discord.User):
        if unban_user(str(user.id)):
            await interaction.response.send_message(f"Unbanned {user.name} from using the comfy command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{user.name} is not banned from using the comfy command.", ephemeral=True)

    @bot.tree.command(name="whybanned", description="Check why a user was banned")
    @app_commands.checks.has_permissions(administrator=True)
    async def whybanned(interaction: discord.Interaction, user: discord.User):
        ban_info = get_ban_info(str(user.id))
        if ban_info:
            await interaction.response.send_message(
                f"{user.name} was banned on {ban_info['banned_at']} for the following reason: {ban_info['reason']}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"{user.name} is not banned.", ephemeral=True)

    @bot.tree.command(name="list_banned_users", description="List all banned users")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_banned_users(interaction: discord.Interaction):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, reason, banned_at FROM banned_users")
        banned_users = c.fetchall()
        conn.close()

        if banned_users:
            banned_list = "\n".join([f"User ID: {user[0]}, Reason: {user[1]}, Banned at: {user[2]}" 
                                   for user in banned_users])
            await interaction.response.send_message(f"Banned users:\n{banned_list}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no banned users.", ephemeral=True)

    @bot.tree.command(name="sync", description="Sync bot commands")
    @has_admin_or_bot_manager_role()
    async def sync_commands(interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            synced = await bot.tree.sync()
            await interaction.followup.send(f"Synced {len(synced)} commands.")
            logger.info(f"Synced {len(synced)} commands")
        except discord.app_commands.errors.CheckFailure as e:
            logger.error(f"Check failure in sync_commands: {str(e)}")
            await interaction.response.send_message("You don't have permission to use this command.", 
                                                  ephemeral=True)
        except Exception as e:
            logger.error(f"Error in sync_commands: {str(e)}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="reload_options", description="Reload LoRA and Resolution options")
    @has_admin_or_bot_manager_role()
    async def reload_options_command(interaction: discord.Interaction):
        try:
            await bot.reload_options()
            await interaction.response.send_message("LoRA and Resolution options have been reloaded.", 
                                                  ephemeral=True)
        except Exception as e:
            logger.error(f"Error reloading options: {str(e)}", exc_info=True)
            await interaction.response.send_message(f"Error reloading options: {str(e)}", ephemeral=True)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.2f}s", 
                ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.", 
                ephemeral=True
            )
        else:
            logger.error(f"Command error: {str(error)}", exc_info=True)
            await interaction.response.send_message(
                f"An error occurred while executing the command: {str(error)}", 
                ephemeral=True
            )

    logger.info("All commands have been set up successfully")