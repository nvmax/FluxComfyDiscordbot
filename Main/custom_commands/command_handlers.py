import discord
from discord import app_commands
from discord.ext import commands as discord_commands
from typing import Optional
import asyncio
import logging
import uuid
import time
import sqlite3
import re
from typing import Optional
from config import BOT_MANAGER_ROLE_ID, CHANNEL_IDS, ENABLE_PROMPT_ENHANCEMENT

from Main.database import (
    DB_NAME, ban_user, unban_user, get_ban_info, 
    add_banned_word, remove_banned_word,
    get_banned_words, remove_user_warnings,
    get_all_warnings, get_user_warnings
)
from Main.utils import load_json, save_json, generate_random_seed
from Main.custom_commands.views import OptionsView, ImageControlView, LoRAView, LoraInfoView
from Main.custom_commands.models import RequestItem
from Main.custom_commands.banned_utils import check_banned
from Main.custom_commands.workflow_utils import update_workflow
from aiohttp import web
from config import fluxversion

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
            await interaction.followup.send_message("This command can only be used in specific channels.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

class CreativityModal(discord.ui.Modal, title='Select Creativity Level'):
    def __init__(self, bot, prompt, resolution, upscale_factor, seed):
        super().__init__()
        self.bot = bot
        self.original_prompt = prompt
        self.resolution = resolution
        self.upscale_factor = upscale_factor
        self.seed = seed
        
        self.creativity = discord.ui.TextInput(
            label='Creativity Level (1-10)',
            style=discord.TextStyle.short,
            placeholder='Enter a number between 1 and 10',
            required=True,
            min_length=1,
            max_length=2
        )
        
        self.note = discord.ui.TextInput(
            label='Note',
            style=discord.TextStyle.paragraph,
            default='Creativity levels affect how much your prompt will be enhanced, 1: No changes, 5: Moderate enhancement, 10: Extreme creative changes',
            required=False,
            custom_id='note_field'
        )
        
        self.add_item(self.creativity)
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            creativity_level = int(self.creativity.value)
            if not 1 <= creativity_level <= 10:
                await interaction.followup.send(
                    "Creativity level must be between 1 and 10, Default is 1.", 
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)
            
            # Use PromptEnhancer directly
            from LMstudio_bot.lora_manager.prompt_enhancer import PromptEnhancer
            enhancer = PromptEnhancer()
            
            # Clean prompt of any existing LoRA trigger words and timestamps
            base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.original_prompt)
            lora_config = load_json('lora.json')
            
            # Remove existing LoRA trigger words from base prompt
            for lora in lora_config['available_loras']:
                if lora.get('prompt'):
                    base_prompt = base_prompt.replace(lora['prompt'], '').strip()
            
            # Clean up multiple commas and whitespace
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Enhance the cleaned prompt
            enhanced_prompt = enhancer.enhance_prompt(
                base_prompt,
                {"name": "default", "description": "Default prompt enhancement", "keywords": []},
                creativity=creativity_level
            )
            
            if not enhanced_prompt:
                enhanced_prompt = base_prompt
                logger.warning("No enhanced prompt generated, using original")

            # Show the original and enhanced prompts (without LoRA trigger words)
            await interaction.followup.send(
                f"Original prompt: {self.original_prompt}\n"
                f"Enhanced prompt (before LoRA): {enhanced_prompt}\n"
                "Proceeding to LoRA selection...",
                ephemeral=True
            )

            # Pass the enhanced prompt to process_image_request
            # LoRA trigger words will be added there after selection
            await process_image_request(
                interaction,
                enhanced_prompt,
                self.resolution,
                self.upscale_factor,
                self.seed
            )

        except ValueError:
            await interaction.followup.send(
                "Please enter a valid number between 1 and 10 for creativity level.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in creativity modal: {str(e)}", exc_info=True)
            await interaction.followup.send(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

async def process_image_request(interaction, prompt, resolution, upscale_factor, seed):
    """Process the image generation request"""
    try:
        # First clean the prompt of any existing LoRA trigger words
        lora_config = load_json('lora.json')
        cleaned_prompt = prompt.strip()
        
        # Remove any existing LoRA trigger words from the prompt
        for lora in lora_config['available_loras']:
            if lora.get('add_prompt'):
                trigger_word = lora['add_prompt'].strip()
                # Remove trigger word and any trailing commas/spaces
                cleaned_prompt = re.sub(f',?\s*{re.escape(trigger_word)},?\s*', '', cleaned_prompt, flags=re.IGNORECASE)
        
        # Clean up any duplicate commas and extra whitespace
        cleaned_prompt = re.sub(r'\s*,\s*,\s*', ', ', cleaned_prompt.strip(' ,')).strip()
        
        logger.debug(f"Cleaned prompt (before LoRA selection): {cleaned_prompt}")
        
        # Show LoRA selection view
        lora_view = LoRAView(interaction.client)
        lora_message = await interaction.followup.send(
            "Please select the LoRAs you want to use:",
            view=lora_view,
            ephemeral=True
        )
        
        # Wait for LoRA selection
        await lora_view.wait()
        
        if not hasattr(lora_view, 'has_confirmed') or not lora_view.has_confirmed:
            await lora_message.edit(content="Selection cancelled or timed out.", view=None)
            return
            
        selected_loras = lora_view.selected_loras
        logger.debug(f"Selected LoRAs: {selected_loras}")
        
        try:
            await lora_message.delete()
        except discord.NotFound:
            pass
        
        # Get LoRA trigger words for currently selected LoRAs
        additional_prompts = []
        for lora_file in selected_loras:
            lora_info = next(
                (l for l in lora_config['available_loras'] if l['file'] == lora_file),
                None
            )
            logger.debug(f"Processing LoRA: {lora_file}, Info: {lora_info}")
            if lora_info and lora_info.get('add_prompt') and lora_info['add_prompt'].strip():
                additional_prompts.append(lora_info['add_prompt'].strip())
                logger.debug(f"Added trigger word: {lora_info['add_prompt'].strip()}")
        
        logger.debug(f"New trigger words to add: {additional_prompts}")
        
        # Construct final prompt with new trigger words
        full_prompt = cleaned_prompt
        if additional_prompts:
            if not full_prompt.endswith(','):
                full_prompt += ','
            full_prompt += ' ' + ', '.join(additional_prompts)
        
        full_prompt = full_prompt.strip(' ,')
        logger.debug(f"Final prompt with new LoRA triggers: {full_prompt}")
        
        # Show the user the prompt changes
        #prompt_message = (
        #    f"Prompt changes:\n\n"
        #    f"Original Prompt: {prompt}\n"
        #    f"Cleaned Prompt (without LoRA triggers): {cleaned_prompt}\n"
        #    f"Added LoRA Triggers: {', '.join(additional_prompts) if additional_prompts else 'None'}\n"
        #    f"Final Combined Prompt: {full_prompt}"
        #)
        
        #await interaction.followup.send(
        #    prompt_message,
        #    ephemeral=True
        #)
        
        if seed is None:
            seed = generate_random_seed()
        
        workflow = load_json(fluxversion)
        request_uuid = str(uuid.uuid4())
        
        workflow = update_workflow(
            workflow,
            full_prompt,
            resolution,
            selected_loras,
            upscale_factor,
            seed
        )

        workflow_filename = f'flux3_{request_uuid}.json'
        save_json(workflow_filename, workflow)

        original_message = await interaction.followup.send(
            "🔄 Starting generation process...",
            ephemeral=False
        )

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
        logger.error(f"Error during image generation setup: {str(e)}", exc_info=True)
        error_message = str(e)
        if len(error_message) > 1900:
            error_message = error_message[:1900] + "..."
        await interaction.followup.send(f"An error occurred during setup: {error_message}", ephemeral=True)

async def setup_commands(bot: discord_commands.Bot):
    @bot.tree.command(name="lorainfo", description="View available Loras information")
    @in_allowed_channel()
    async def lorainfo(interaction: discord.Interaction):
        try:
            # Load loras from the JSON file
            loras_data = load_json('lora.json')  # load_json will prepend Main/DataSets/
            available_loras = loras_data.get('available_loras', [])
            
            # Create and show the view
            view = LoraInfoView(available_loras)
            await interaction.response.send_message(
                content=view.get_page_content(),
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in lorainfo command: {str(e)}")
            await interaction.response.send_message("An error occurred while fetching Lora information.", ephemeral=True)

    @bot.tree.command(name="comfy", description="Generate an image based on a prompt.")
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
    async def comfy(interaction: discord.Interaction, prompt: str, resolution: str, 
                    upscale_factor: int = 1, seed: Optional[int] = None):
        try:
           
            logger.info(f"Comfy command invoked by {interaction.user.id}")
            
            # Check for banned status first
            is_banned, ban_message = check_banned(str(interaction.user.id), prompt)
            if is_banned:
                await interaction.followup.send(ban_message, ephemeral=True)
                return

            if ENABLE_PROMPT_ENHANCEMENT:
                if not interaction.client.ai_provider:
                    try:
                        interaction.client.ai_provider = AIProviderFactory.get_provider(AI_PROVIDER)
                    except Exception as e:
                        logger.error(f"Failed to initialize AI provider: {e}")
                        await interaction.followup.send(
                            "Prompt enhancement is enabled but the AI provider could not be initialized. "
                            "Please contact an administrator.",
                            ephemeral=True
                        )
                        return
                            
                # Send creativity selection modal
                creativity_modal = CreativityModal(bot, prompt, resolution, upscale_factor, seed)
                await interaction.response.send_modal(creativity_modal)
                return
            else:
                # Process normally without prompt enhancement
                await process_image_request(interaction, prompt, resolution, upscale_factor, seed)

        except Exception as e:
            logger.error(f"Error in comfy command: {str(e)}")
            if not interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="reboot", description="Reboot the bot (Restricted to specific admin)")
    async def reboot(interaction: discord.Interaction):
        if interaction.user.id == BOT_MANAGER_ROLE_ID:
            await interaction.followup.send("Rebooting bot...", ephemeral=True)
            await bot.close()
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            await interaction.followup.send("You don't have permission.", ephemeral=True)

    @bot.tree.command(name="add_banned_word", description="Add a word to the banned list")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_banned_word_command(interaction: discord.Interaction, word: str):
        word = word.lower()
        add_banned_word(word)
        await interaction.followup.send(f"Added '{word}' to the banned words list.", ephemeral=True)

    @bot.tree.command(name="remove_banned_word", description="Remove a word from the banned list")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_banned_word_command(interaction: discord.Interaction, word: str):
        word = word.lower()
        remove_banned_word(word)
        await interaction.response.send_message(f"Removed '{word}' from the banned words list.", ephemeral=True)

    @bot.tree.command(name="list_banned_words", description="List all banned words")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_banned_words(interaction: discord.Interaction):
        banned_words = get_banned_words()
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
            banned_list = "\n".join([
                f"User ID: {user[0]}, Reason: {user[1]}, Banned at: {user[2]}" 
                for user in banned_users
            ])
            await interaction.response.send_message(f"Banned users:\n{banned_list}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no banned users.", ephemeral=True)

    @bot.tree.command(name="remove_warning", description="Remove all warnings from a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_warning_command(interaction: discord.Interaction, user: discord.User):
        try:
            success, message = remove_user_warnings(str(user.id))
            if success:
                await interaction.followup.send(
                    f"Successfully removed all warnings from {user.name} ({user.id}).\n{message}", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Could not remove warnings from {user.name} ({user.id}).\n{message}", 
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in remove_warning command: {str(e)}")
            await interaction.followup.send(
                f"An error occurred while removing warnings: {str(e)}", 
                ephemeral=True
            )

    @bot.tree.command(name="check_warnings", description="Check all user warnings")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_warnings_command(interaction: discord.Interaction):
        try:
            success, result = get_all_warnings()
            
            if not success:
                await interaction.followup.send(result, ephemeral=True)
                return
            
            embeds = []
            
            for user_id, warnings in result.items():
                try:
                    user = await interaction.client.fetch_user(int(user_id))
                    user_name = user.name
                except:
                    user_name = f"Unknown User ({user_id})"
                
                embed = discord.Embed(
                    title=f"Warnings for {user_name}",
                    color=discord.Color.yellow()
                )
                embed.set_footer(text=f"User ID: {user_id}")
                
                warning_count = len(warnings)
                if warning_count == 1:
                    status = "🟡 Active - First Warning"
                elif warning_count == 2:
                    status = "🔴 Final Warning"
                else:
                    status = "⚫ Unknown Status"

                embed.add_field(
                    name="Warning Status",
                    value=f"{status}\n{warning_count}/2 warnings",
                    inline=False
                )
                
                for idx, (prompt, word, warned_at) in enumerate(warnings, 1):
                    embed.add_field(
                        name=f"Warning {idx} - {warned_at}",
                        value=f"**Banned Word Used:** {word}\n**Full Prompt:** {prompt}",
                        inline=False
                    )
                embeds.append(embed)
            
            if len(embeds) == 0:
                await interaction.followup.send("No warnings found in the database.", ephemeral=True)
                return
                
            # If only one embed, send it without navigation
            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0], ephemeral=True)
            else:
                # Create navigation view for multiple embeds
                class NavigationView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=180)  # 3 minute timeout
                        self.current_page = 0

                    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray)
                    async def previous_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        if button_interaction.user.id != interaction.user.id:
                            await button_interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
                            return
                        self.current_page = (self.current_page - 1) % len(embeds)
                        embed = embeds[self.current_page]
                        embed.set_footer(text=f"Page {self.current_page + 1}/{len(embeds)}")
                        await button_interaction.response.edit_message(embed=embed)

                    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray)
                    async def next_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        if button_interaction.user.id != interaction.user.id:
                            await button_interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
                            return
                        self.current_page = (self.current_page + 1) % len(embeds)
                        embed = embeds[self.current_page]
                        embed.set_footer(text=f"Page {self.current_page + 1}/{len(embeds)}")
                        await button_interaction.response.edit_message(embed=embed)

                    async def on_timeout(self):
                        # Disable buttons after timeout
                        for item in self.children:
                            item.disabled = True
                        # Try to update the message with disabled buttons
                        try:
                            await interaction.edit_original_response(view=self)
                        except:
                            pass

                view = NavigationView()
                first_embed = embeds[0]
                first_embed.set_footer(text=f"Page 1/{len(embeds)}")
                await interaction.response.send_message(embed=first_embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in check_warnings command: {str(e)}")
            await interaction.response.send_message(
                f"An error occurred while checking warnings: {str(e)}", 
                ephemeral=True
            )

    @bot.tree.command(name="sync", description="Sync bot commands")
    @has_admin_or_bot_manager_role()
    async def sync_commands(interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            synced = await bot.tree.sync()
            await interaction.followup.send(f"Synced {len(synced)} commands.")
            logger.info(f"Synced {len(synced)} commands")
        except discord.app_commands.errors.CheckFailure as e:
            logger.error(f"Check failure in sync_commands: {str(e)}", exc_info=True)
            await interaction.followup.send("You don't have permission to use this command.", 
                                          ephemeral=True)
        except Exception as e:
            logger.error(f"Error in sync_commands: {str(e)}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="reload_options", description="Reload LoRA and Resolution options")
    @has_admin_or_bot_manager_role()
    async def reload_options_command(interaction: discord.Interaction):
        try:
            await bot.reload_options()
            await interaction.followup.send("LoRA and Resolution options have been reloaded.",
                                            ephemeral=True)
        except Exception as e:
            logger.error(f"Error reloading options: {str(e)}", exc_info=True, stack_info=True)
            await interaction.followup.send(f"Error reloading options: {str(e)}", ephemeral=True)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for application commands"""
        try:
            error_message = str(error)
            if len(error_message) > 1900:  # Leave room for formatting
                error_message = error_message[:1900] + "..."

            if isinstance(error, app_commands.CommandOnCooldown):
                response_message = f"This command is on cooldown. Try again in {error.retry_after:.2f}s"
            elif isinstance(error, app_commands.MissingPermissions):
                response_message = "You don't have permission to use this command."
            else:
                response_message = f"An error occurred while executing the command: {error_message}"

            # Check if interaction has been responded to
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(response_message, ephemeral=True)
                except discord.HTTPException:
                    # If the followup fails, try to send a simplified error message
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            else:
                try:
                    await interaction.followup.send_message(response_message, ephemeral=True)
                except discord.HTTPException:
                    await interaction.followup.send_message("An error occurred. Please try again.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in error handler: {str(e)}", exc_info=True)