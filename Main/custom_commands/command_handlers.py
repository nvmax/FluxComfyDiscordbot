import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import asyncio
import subprocess
import sys
import time
import uuid
import json
import os
import re
from Main.utils import load_json, generate_random_seed, save_json
from .banned_utils import check_banned
from .views import CreativityModal, LoRAView, LoraInfoView, ReduxPromptModal
from .image_processing import process_image_request
from config import ENABLE_PROMPT_ENHANCEMENT, AI_PROVIDER, fluxversion
from ..LMstudio_bot.ai_providers import AIProviderFactory
from .workflow_utils import update_workflow
from .models import RequestItem

logger = logging.getLogger(__name__)

async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for application commands"""
    try:
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
            return

        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        if isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                f"I need the following permission(s) to execute this command: {', '.join(error.missing_permissions)}",
                ephemeral=True
            )
            return

        # Log the error
        logger.error(f"Command error in {interaction.command.name}: {str(error)}", exc_info=True)
        
        # Send a user-friendly error message
        error_message = "An error occurred while processing your command."
        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=True)
        else:
            await interaction.response.send_message(error_message, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}", exc_info=True)

def has_admin_or_bot_manager_role():
    async def predicate(interaction: discord.Interaction):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = any(role.id == 1055096424235516936 for role in interaction.user.roles)
        if is_admin or has_role:
            return True
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

def check_channel():
    """Check if the command is being used in an allowed channel"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.client.allowed_channels:  # If no channels are specified, allow all
            return True
        
        if interaction.channel_id not in interaction.client.allowed_channels:
            try:
                await interaction.response.send_message("This command can only be used in specific channels.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("This command can only be used in specific channels.", ephemeral=True)
            return False
            
        return True
    return app_commands.check(predicate)

async def setup_commands(bot: commands.Bot):
    """Setup all commands for the bot"""
    # Register the error handler first
    bot.tree.on_error = on_app_command_error

    @bot.tree.command(name="lorainfo", description="View available Loras information")
    @check_channel()
    async def lorainfo(interaction: discord.Interaction):
        try:
            loras_data = load_json('lora.json')
            available_loras = loras_data.get('available_loras', [])
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
    @check_channel()
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
            
            # Check for banned words first, before any other processing
            is_banned, message = check_banned(str(interaction.user.id), prompt)
            if message:  # If there's a message, either a warning or ban
                await interaction.response.send_message(message, ephemeral=True)
                return  # Don't continue with image generation if banned word is detected
            
            # Show creativity modal or process directly based on prompt enhancement setting
            if ENABLE_PROMPT_ENHANCEMENT:
                # Show creativity modal without initializing AI provider yet
                creativity_modal = CreativityModal(interaction.client, resolution, prompt, upscale_factor, seed)
                await interaction.response.send_modal(creativity_modal)
            else:
                # If prompt enhancement is disabled, process directly
                await process_image_request(interaction, prompt, resolution, upscale_factor, seed)

        except Exception as e:
            logger.error(f"Error in comfy command: {str(e)}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    async def reduxprompt(
        interaction: discord.Interaction, 
        resolution: str,
        strength: str
    ):
        try:
            # Check if channel is allowed
            if interaction.channel_id not in bot.allowed_channels:
                await interaction.response.send_message(
                    "This command can only be used in specific channels.",
                    ephemeral=True
                )
                return

            logger.debug(f"Received reduxprompt command with resolution: {resolution}, strength: {strength}")

            # Show the modal for prompt input first
            modal = ReduxPromptModal(bot, resolution, strength)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in reduxprompt command: {str(e)}")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

    # Register the reduxprompt command with proper decorators
    reduxprompt = bot.tree.command(
        name="reduxprompt",
        description="Generate an image using a reference image and prompt"
    )(
        app_commands.describe(
            resolution="Choose the resolution",
            strength="Choose the strength level"
        )(
            app_commands.choices(
                resolution=[
                    app_commands.Choice(name=name, value=name)
                    for name in load_json('ratios.json')['ratios'].keys()
                ],
                strength=[
                    app_commands.Choice(name="Highest", value="highest"),
                    app_commands.Choice(name="High", value="high"),
                    app_commands.Choice(name="Medium", value="medium"),
                    app_commands.Choice(name="Low", value="low"),
                    app_commands.Choice(name="Lowest", value="lowest")
                ]
            )(reduxprompt)
        )
    )

    @bot.tree.command(name="reboot", description="Reboot the bot (Restricted to specific admin)")
    async def reboot(interaction: discord.Interaction):
        if interaction.user.id == 1055096424235516936:
            await interaction.followup.send("Rebooting bot...", ephemeral=True)
            await bot.close()
            import sys
            import os
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

    @bot.tree.command(name="remove_warning", description="Remove warnings from a user")
    @has_admin_or_bot_manager_role()
    @app_commands.describe(
        user="The user to remove warnings from"
    )
    async def remove_warning_command(interaction: discord.Interaction, user: discord.Member):
        try:
            # Defer the response first
            await interaction.response.defer(ephemeral=True)
            
            # Get current warnings
            current_warnings = get_user_warnings(str(user.id))
            
            if current_warnings == 0:
                await interaction.followup.send(
                    f"{user.mention} has no warnings to remove.",
                    ephemeral=True
                )
                return
                
            # Remove all warnings
            success, message = remove_user_warnings(str(user.id))
            
            if success:
                await interaction.followup.send(
                    f"Successfully removed all warnings from {user.mention}. ({message})",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Could not remove warnings from {user.mention}: {message}",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error in remove_warning command: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while removing warnings.",
                    ephemeral=True
                )
            else:
                try:
                    await interaction.followup.send(
                        "An error occurred while removing warnings.",
                        ephemeral=True
                    )
                except:
                    pass  # If both attempts fail, just log the error

    @bot.tree.command(name="check_warnings", description="Check all user warnings")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_warnings_command(interaction: discord.Interaction):
        """Command to check all warnings in the system"""
        try:
            # Defer the response first since we might need time to process
            await interaction.response.defer(ephemeral=True)
            
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
                            await button_interaction.response.send_message(
                                "You cannot use these buttons.", 
                                ephemeral=True
                            )
                            return
                            
                        self.current_page = (self.current_page - 1) % len(embeds)
                        embed = embeds[self.current_page]
                        embed.set_footer(text=f"Page {self.current_page + 1}/{len(embeds)}")
                        await button_interaction.response.edit_message(embed=embed)

                    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray)
                    async def next_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        if button_interaction.user.id != interaction.user.id:
                            await button_interaction.response.send_message(
                                "You cannot use these buttons.", 
                                ephemeral=True
                            )
                            return
                            
                        self.current_page = (self.current_page + 1) % len(embeds)
                        embed = embeds[self.current_page]
                        embed.set_footer(text=f"Page {self.current_page + 1}/{len(embeds)}")
                        await button_interaction.response.edit_message(embed=embed)

                    async def on_timeout(self):
                        # Disable buttons after timeout
                        for item in self.children:
                            item.disabled = True
                        try:
                            message = await interaction.original_response()
                            await message.edit(view=self)
                        except:
                            pass

                view = NavigationView()
                first_embed = embeds[0]
                first_embed.set_footer(text=f"Page 1/{len(embeds)}")
                await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
                    
        except Exception as e:
            logger.error(f"Error in check_warnings command: {str(e)}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"An error occurred while checking warnings: {str(e)}", 
                    ephemeral=True
                )
            else:
                await interaction.response.send(
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

    class CreativityModal(discord.ui.Modal, title='Select Creativity Level'):
        def __init__(self, bot, resolution, prompt, upscale_factor, seed):
            super().__init__()
            self.bot = bot
            self.resolution = resolution
            self.prompt = prompt
            self.upscale_factor = upscale_factor
            self.seed = seed  # Store the seed as an instance variable
            
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
                
                # Check for banned words first
                is_banned, message = check_banned(str(interaction.user.id), self.prompt)
                if message:  # If there's a warning or ban message
                    await interaction.followup.send(message, ephemeral=True)
                    if is_banned:  # If the user is banned, stop processing
                        return

                # Clean prompt of any existing LoRA trigger words and timestamps
                base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.prompt)
                lora_config = load_json('lora.json')
                
                # Remove existing LoRA trigger words from base prompt
                for lora in lora_config['available_loras']:
                    if lora.get('prompt'):
                        base_prompt = base_prompt.replace(lora['prompt'], '').strip()
                
                # Clean up multiple commas and whitespace
                base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
                
                if ENABLE_PROMPT_ENHANCEMENT and interaction.client.ai_provider:
                    try:
                        # Test AI provider connection
                        connection_ok = await interaction.client.ai_provider.test_connection()
                        if not connection_ok:
                            logger.error("AI provider connection test failed")
                            await interaction.followup.send(
                                "Could not connect to AI provider. Using original prompt.",
                                ephemeral=True
                            )
                            enhanced_prompt = base_prompt
                        else:
                            # Enhance the cleaned prompt
                            enhanced_prompt = await interaction.client.ai_provider.generate_response(
                                base_prompt,
                                temperature=float(creativity_level) / 10.0  # Convert 1-10 to 0.1-1.0
                            )
                            
                            if not enhanced_prompt:
                                enhanced_prompt = base_prompt
                                logger.warning("No enhanced prompt generated, using original")
                    except Exception as e:
                        logger.error(f"Error enhancing prompt: {e}", exc_info=True)
                        enhanced_prompt = base_prompt
                        await interaction.followup.send(
                            f"Error enhancing prompt: {str(e)}. Using original prompt.",
                            ephemeral=True
                        )
                else:
                    enhanced_prompt = base_prompt
                    if not interaction.client.ai_provider:
                        logger.info("AI provider not initialized, using original prompt")
                    else:
                        logger.info("Prompt enhancement disabled, using original prompt")

                # Check enhanced prompt for banned words
                is_banned, message = check_banned(str(interaction.user.id), enhanced_prompt)
                if message:  # If there's a warning or ban message
                    await interaction.followup.send(message, ephemeral=True)
                    if is_banned:  # If the user is banned, stop processing
                        return

                # Show the original and enhanced prompts (without LoRA trigger words)
                await interaction.followup.send(
                    f"Original prompt: {self.prompt}\n"
                    f"Enhanced prompt (before LoRA): {enhanced_prompt}\n"
                    "Proceeding to LoRA selection...",
                    ephemeral=True
                )
                
                logger.debug(f"Final prompt before LoRA selection: {enhanced_prompt}")
                
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
                    if lora_info and lora_info.get('add_prompt') and lora_info['add_prompt'].strip():
                        additional_prompts.append(lora_info['add_prompt'].strip())
                
                # Construct final prompt with new trigger words
                full_prompt = enhanced_prompt
                if additional_prompts:
                    if not full_prompt.endswith(','):
                        full_prompt += ','
                    full_prompt += ' ' + ', '.join(additional_prompts)
                
                full_prompt = full_prompt.strip(' ,')
                logger.debug(f"Final prompt with LoRA triggers: {full_prompt}")
                
                # Use the seed from instance variable, or generate new one if None
                current_seed = self.seed if self.seed is not None else generate_random_seed()
                
                workflow = load_json(f'{fluxversion}')
                request_uuid = str(uuid.uuid4())
                
                workflow = update_workflow(
                    workflow,
                    full_prompt,
                    self.resolution,
                    selected_loras,
                    self.upscale_factor,
                    current_seed
                )

                workflow_filename = f'{fluxversion}_{request_uuid}.json'
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
                    resolution=self.resolution,
                    loras=selected_loras,
                    upscale_factor=self.upscale_factor,
                    workflow_filename=workflow_filename,
                    seed=current_seed
                )
                await interaction.client.subprocess_queue.put(request_item)
                
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