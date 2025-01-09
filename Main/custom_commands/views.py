import logging
import discord
from discord import app_commands, SelectOption
from discord.ui import View, Select, Button, Modal, TextInput
from typing import Optional, List
import uuid
import time
import json
import asyncio
import re
import os
from .banned_utils import check_banned
from .image_processing import process_image_request
from Main.utils import load_json, save_json, generate_random_seed
from .workflow_utils import update_workflow, update_reduxprompt_workflow
from config import fluxversion
from .models import RequestItem, ReduxRequestItem, ReduxPromptRequestItem
from Main.LMstudio_bot.ai_providers.base import AIProvider

logger = logging.getLogger(__name__)

class PaginatedLoRASelect(Select):
    def __init__(self, lora_options: List[dict], page: int = 0, selected_loras: List[str] = None):
        self.all_options = []
        selected_loras = selected_loras or []
        
        # Calculate page slicing
        start_idx = page * 25
        end_idx = min(start_idx + 25, len(lora_options))
        page_options = lora_options[start_idx:end_idx]
        
        # Create options only for current page
        for lora in page_options:
            self.all_options.append(
                SelectOption(
                    label=lora['name'],
                    value=lora['file'],
                    default=bool(lora['file'] in selected_loras)
                )
            )
        
        total_pages = (len(lora_options) - 1) // 25 + 1
        super().__init__(
            placeholder=f"Select LoRAs (Page {page + 1}/{total_pages})",
            min_values=0,
            max_values=len(self.all_options),
            options=self.all_options
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        try:
            # Get current page options
            current_page_values = {option.value for option in self.options}
            
            # Determine which selections set to use
            selections = (view.all_selections if hasattr(view, 'all_selections') 
                        else view.all_selected_loras if hasattr(view, 'all_selected_loras') 
                        else set())
            
            # Remove all options from current page from selections
            selections = {
                selection for selection in selections 
                if selection not in current_page_values
            }
            
            # Add only currently selected values
            selections.update(self.values)
            
            # Update the view's selection set
            if hasattr(view, 'all_selections'):
                view.all_selections = selections
            else:
                view.all_selected_loras = selections
            
            # Update page selections tracking
            if hasattr(view, '_page_selections'):
                view._page_selections[view.page] = set(self.values)
            
            # Update confirm button
            for child in view.children:
                if isinstance(child, Button) and "confirm" in str(child.custom_id):
                    child.label = f"Confirm Selection ({len(selections)} LoRAs)"
                    break
                    
            # Recreate the select with updated defaults
            new_select = PaginatedLoRASelect(
                view.bot.lora_options,
                view.page,
                list(selections)
            )
            
            # Replace the old select with the new one
            for i, child in enumerate(view.children):
                if isinstance(child, PaginatedLoRASelect):
                    new_select.callback = child.callback
                    view.remove_item(child)
                    view.add_item(new_select)
                    break
            
            # Update the view
            await interaction.response.edit_message(view=view)
            
            logger.debug(f"Updated selections: {selections}")
            logger.debug(f"Current page values: {self.values}")
            
        except Exception as e:
            logger.error(f"Error in LoRA select callback: {str(e)}", exc_info=True)
            await interaction.response.defer()


class LoRAView(View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.page = 0
        self.all_selections = set()
        self.selected_loras = []
        self.has_confirmed = False
        self._page_selections = {}
        self.update_view()

    def update_view(self):
        """Update view with current selections"""
        self.clear_items()
        
        # Create new select menu with current selections
        self.lora_select = PaginatedLoRASelect(
            self.bot.lora_options,
            self.page,
            list(self.all_selections)  # Pass all selections to show defaults
        )
        self.add_item(self.lora_select)
        
        # Add navigation buttons
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        
        if self.page > 0:
            previous_button = Button(
                custom_id=f"previous_page_{self.page}",
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                row=1
            )
            previous_button.callback = self.previous_page_callback
            self.add_item(previous_button)
        
        if self.page < total_pages - 1:
            next_button = Button(
                custom_id=f"next_page_{self.page}",
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                row=1
            )
            next_button.callback = self.next_page_callback
            self.add_item(next_button)
        
        # Always show selection count
        confirm_button = Button(
            custom_id=f"confirm_{self.page}",
            label=f"Confirm Selection ({len(self.all_selections)} LoRAs)",
            style=discord.ButtonStyle.primary,
            row=2
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

        cancel_button = Button(
            custom_id=f"cancel_{self.page}",
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            row=2
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def previous_page_callback(self, interaction: discord.Interaction):
        """Handle previous page navigation"""
        if hasattr(self.lora_select, 'values'):
            # Get current page files
            start_idx = self.page * 25
            end_idx = min(start_idx + 25, len(self.bot.lora_options))
            current_page_files = {option.value for option in self.lora_select.options}
            
            # Update selections for current page
            self.all_selections = {
                selection for selection in self.all_selections 
                if selection not in current_page_files
            }
            if self.lora_select.values:
                self.all_selections.update(self.lora_select.values)
            
            self._page_selections[self.page] = set(self.lora_select.values)
        
        self.page = max(0, self.page - 1)
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        """Handle next page navigation"""
        if hasattr(self.lora_select, 'values'):
            # Get current page files
            start_idx = self.page * 25
            end_idx = min(start_idx + 25, len(self.bot.lora_options))
            current_page_files = {option.value for option in self.lora_select.options}
            
            # Update selections for current page
            self.all_selections = {
                selection for selection in self.all_selections 
                if selection not in current_page_files
            }
            if self.lora_select.values:
                self.all_selections.update(self.lora_select.values)
            
            self._page_selections[self.page] = set(self.lora_select.values)
        
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        self.page = min(self.page + 1, total_pages - 1)
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def confirm_callback(self, interaction: discord.Interaction):
        """Handle confirm button press"""
        if hasattr(self.lora_select, 'values'):
            # Get current page files
            start_idx = self.page * 25
            end_idx = min(start_idx + 25, len(self.bot.lora_options))
            current_page_files = {option.value for option in self.lora_select.options}
            
            # Update selections for current page
            self.all_selections = {
                selection for selection in self.all_selections 
                if selection not in current_page_files
            }
            if self.lora_select.values:
                self.all_selections.update(self.lora_select.values)
            
            self._page_selections[self.page] = set(self.lora_select.values)
            
        self.selected_loras = list(self.all_selections)
        logger.debug(f"Final LoRA selection: {self.selected_loras}")
        logger.debug(f"Page selections at confirm: {self._page_selections}")
        self.has_confirmed = True
        self.stop()
        await interaction.response.defer()

    async def cancel_callback(self, interaction: discord.Interaction):
        """Handle cancel button press"""
        self._page_selections.clear()
        self.all_selections.clear()
        self.selected_loras = []
        self.has_confirmed = False
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        """Handle view timeout"""
        self._page_selections.clear()
        self.all_selections.clear()
        self.selected_loras = []
        self.has_confirmed = False
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction is valid"""
        if not await super().interaction_check(interaction):
            return False
            
        if not hasattr(self, 'user_id'):
            self.user_id = interaction.user.id
            
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot use these controls.", 
                ephemeral=True
            )
            return False
            
        return True

class ResolutionSelect(Select):
    def __init__(self, bot, original_resolution):
        # Create options from bot's resolution options
        options = [
            SelectOption(
                label=res,
                value=res,
                default=(res == original_resolution)
            )
            for res in bot.resolution_options
        ]
        
        super().__init__(
            placeholder="Choose resolution",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            # Ensure we have a valid selection
            if not self.values:
                await interaction.response.send_message(
                    "Please select a resolution",
                    ephemeral=True
                )
                return

            # Update the resolution in the parent view
            if hasattr(self.view, 'selected_resolution'):
                self.view.selected_resolution = self.values[0]
            
            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in resolution select callback: {str(e)}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your selection",
                    ephemeral=True
                )

    async def refresh_options(self, bot, current_resolution):
        """Refresh the resolution options"""
        self.options = [
            SelectOption(
                label=res,
                value=res,
                default=(res == current_resolution)
            )
            for res in bot.resolution_options
        ]

class OptionsView(View):
    def __init__(self, bot, original_prompt, image_filename, original_resolution, original_loras, original_upscale_factor, original_seed, original_interaction):
        super().__init__(timeout=300)
        self.bot = bot
        self.original_prompt = original_prompt
        self.image_filename = image_filename
        self.selected_resolution = original_resolution
        self.all_selected_loras = set(original_loras if original_loras else [])
        self.current_page_selections = set()  # Track current page selections
        self.original_interaction = original_interaction
        self.selected_seed = original_seed
        self.original_upscale_factor = original_upscale_factor
        self.page = 0
        
        logger.debug(f"Initializing OptionsView with original LoRAs: {self.all_selected_loras}")
        self.setup_view()

    def setup_view(self):
        """Setup or refresh the view components"""
        # Clear existing items
        self.clear_items()

        # Resolution select (Row 0)
        self.resolution_select = ResolutionSelect(self.bot, self.selected_resolution)
        self.add_item(self.resolution_select)

        # Get current page selections
        start_idx = self.page * 25
        end_idx = min(start_idx + 25, len(self.bot.lora_options))
        current_page_loras = [lora['file'] for lora in self.bot.lora_options[start_idx:end_idx]]
        
        # Update current page selections
        self.current_page_selections = {lora for lora in self.all_selected_loras if lora in current_page_loras}

        # LoRA select (Row 1)
        self.lora_select = PaginatedLoRASelect(
            self.bot.lora_options,
            self.page,
            list(self.current_page_selections)  # Only pass current page selections
        )
        self.add_item(self.lora_select)

        # Navigation buttons (Row 2)
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        
        if total_pages > 1:
            if self.page > 0:
                prev_button = Button(
                    label=f"◀ Previous (Page {self.page + 1}/{total_pages})",
                    custom_id="previous_page",
                    style=discord.ButtonStyle.secondary,
                    row=2
                )
                prev_button.callback = self.previous_page_callback
                self.add_item(prev_button)

            if self.page < total_pages - 1:
                next_button = Button(
                    label=f"Next (Page {self.page + 2}/{total_pages}) ▶",
                    custom_id="next_page",
                    style=discord.ButtonStyle.secondary,
                    row=2
                )
                next_button.callback = self.next_page_callback
                self.add_item(next_button)

        # Action buttons (Row 3)
        confirm_button = Button(
            label=f"Confirm Selection ({len(self.all_selected_loras)} LoRAs)",
            style=discord.ButtonStyle.primary,
            custom_id="confirm_button",
            row=3
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

    async def update_current_page_selections(self):
        """Update selections for the current page"""
        if not hasattr(self.lora_select, 'values'):
            return

        # Get current page LoRA files
        start_idx = self.page * 25
        end_idx = min(start_idx + 25, len(self.bot.lora_options))
        current_page_loras = {lora['file'] for lora in self.bot.lora_options[start_idx:end_idx]}
        
        # Remove current page LoRAs from all selections
        self.all_selected_loras = {lora for lora in self.all_selected_loras if lora not in current_page_loras}
        
        # Add new selections from current page
        if self.lora_select.values:
            self.all_selected_loras.update(self.lora_select.values)
        
        logger.debug(f"Updated selections: {self.all_selected_loras}")

    async def resolution_select_callback(self, interaction: discord.Interaction):
        """Handle resolution selection"""
        if self.resolution_select.values:
            self.selected_resolution = self.resolution_select.values[0]
            logger.debug(f"Resolution selected: {self.selected_resolution}")
        await interaction.response.defer(ephemeral=True)

    async def lora_select_callback(self, interaction: discord.Interaction):
        """Handle LoRA selection"""
        if hasattr(self.lora_select, 'values'):
            # Update the master set of selected LoRAs
            self.all_selected_loras.update(self.lora_select.values)
            logger.debug(f"Updated LoRA selections after callback: {self.all_selected_loras}")
        await interaction.response.defer(ephemeral=True)

    async def previous_page_callback(self, interaction: discord.Interaction):
        """Handle previous page navigation"""
        await self.update_current_page_selections()
        self.page = max(0, self.page - 1)
        self.setup_view()
        await interaction.response.edit_message(view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        """Handle next page navigation"""
        await self.update_current_page_selections()
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        self.page = min(self.page + 1, total_pages - 1)
        self.setup_view()
        await interaction.response.edit_message(view=self)

    async def confirm_callback(self, interaction: discord.Interaction):
        """Handle confirmation and prompt processing"""
        try:
            # Update selections one final time
            await self.update_current_page_selections()
            
            logger.debug(f"Final LoRA selections at confirmation: {self.all_selected_loras}")
            
            # Process the prompt with LoRA trigger words
            lora_config = load_json('lora.json')
            base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.original_prompt)
            
            # First remove ALL existing trigger words from the base prompt
            for lora in lora_config['available_loras']:
                if lora.get('add_prompt'):
                    trigger_word = lora['add_prompt'].strip()
                    base_prompt = re.sub(fr',?\s*{re.escape(trigger_word)},?\s*', '', base_prompt, flags=re.IGNORECASE)
            
            # Clean up any duplicate commas and whitespace
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Add trigger words from currently selected LoRAs
            additional_prompts = []
            for lora_file in self.all_selected_loras:
                lora_info = next(
                    (l for l in lora_config['available_loras'] if l['file'] == lora_file),
                    None
                )
                if lora_info and lora_info.get('add_prompt'):
                    trigger_word = lora_info['add_prompt'].strip()
                    if trigger_word:
                        additional_prompts.append(trigger_word)
            
            # Combine base prompt with new trigger words
            updated_prompt = base_prompt
            if additional_prompts:
                if not updated_prompt.endswith(','):
                    updated_prompt += ','
                updated_prompt += ' ' + ', '.join(additional_prompts)
            
            updated_prompt = updated_prompt.strip(' ,')
            
            try:
                if self.original_interaction:
                    await self.original_interaction.delete_original_response()
            except Exception as e:
                logger.error(f"Error deleting options message: {e}")

            # Show the user the prompt changes
            changes_message = (
                f"Prompt changes:\n\n"
                f"Original: {self.original_prompt}\n"
                f"Updated: {updated_prompt}\n\n"
                f"LoRAs: {', '.join(self.all_selected_loras) if self.all_selected_loras else 'None'}"
            )
            
            await interaction.response.send_modal(PromptModal(
                self.bot,
                updated_prompt,
                self.image_filename,
                self.selected_resolution,
                list(self.all_selected_loras),
                self.original_upscale_factor,
                self.original_interaction,
                self.selected_seed
            ))
            
            # Send changes as a follow-up message
            await interaction.followup.send(changes_message, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in confirm callback: {e}", exc_info=True)
            await interaction.response.send_message(
                f"An error occurred while processing your selection: {str(e)}", 
                ephemeral=True
            )
            
def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.resolution_select.callback = cls.resolution_select_callback
        cls.lora_select.callback = cls.lora_select_callback

class PromptModal(Modal, title="Edit Prompt"):
    def __init__(self, bot, original_prompt, image_filename, resolution, loras, upscale_factor, original_interaction, original_seed=None):
        super().__init__()
        self.bot = bot
        self.image_filename = image_filename
        self.resolution = resolution
        self.loras = loras  # This will now be a list converted from the set
        self.upscale_factor = upscale_factor
        self.original_interaction = original_interaction

        self.prompt = TextInput(
            label="Prompt",
            style=discord.TextStyle.paragraph,
            placeholder="Enter your prompt here...",
            default=original_prompt,
            required=True
        )
        self.add_item(self.prompt)

        self.seed = TextInput(
            label="Seed (leave blank for random)",
            style=discord.TextStyle.short,
            placeholder="Enter a seed number or leave blank",
            default=str(original_seed) if original_seed is not None else "",
            required=False
        )
        self.add_item(self.seed)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lora_config = load_json('lora.json')
            base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.prompt.value)
            
            # Clean base prompt of any existing LoRA trigger words
            for lora in lora_config['available_loras']:
                if lora.get('prompt'):
                    base_prompt = base_prompt.replace(lora['prompt'], '').strip()
            
            # Clean up multiple commas and whitespace
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Get LoRA trigger words
            additional_prompts = []
            for lora in self.loras:
                lora_info = next((l for l in lora_config['available_loras'] if l['file'] == lora), None)
                if lora_info and lora_info.get('prompt') and lora_info['prompt'].strip():
                    additional_prompts.append(lora_info['prompt'].strip())
            
            # Join trigger words with commas and append to prompt
            trigger_words = ", ".join(additional_prompts) if additional_prompts else ""
            full_prompt = f"{base_prompt}, {trigger_words}" if trigger_words else base_prompt
            
            try:
                seed = int(self.seed.value) if self.seed.value else None
            except ValueError:
                seed = None

            workflow = load_json(fluxversion)
            request_uuid = str(uuid.uuid4())
            
            workflow = update_workflow(workflow, 
                                  full_prompt,
                                  self.resolution, 
                                  self.loras, 
                                  self.upscale_factor,
                                  seed)

            workflow_filename = f'flux3_{request_uuid}.json'
            save_json(workflow_filename, workflow)

            new_message = await interaction.response.send_message("Generating new image with updated options...")
            message = await interaction.original_response()

            request_item = RequestItem(
                id=str(interaction.id),
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel.id),
                interaction_id=str(interaction.id),
                original_message_id=str(message.id),
                prompt=full_prompt,
                resolution=self.resolution,
                loras=self.loras,
                upscale_factor=self.upscale_factor,
                workflow_filename=workflow_filename,
                seed=seed
            )
            await interaction.client.subprocess_queue.put(request_item)
            
        except Exception as e:
            logger.error(f"Error in modal submit: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)

class ReduxModal(Modal, title='Redux Image Generator'):
    def __init__(self, bot, resolution: str):
        super().__init__()
        self.bot = bot
        self.resolution = resolution
        
        self.strength1 = TextInput(
            label="Strength for Image 1 (0.1-1.0)",
            placeholder="Enter a number between 0.1 and 1.0",
            default="1.0",
            required=True,
            max_length=4
        )
        
        self.strength2 = TextInput(
            label="Strength for Image 2 (0.1-1.0)",
            placeholder="Enter a number between 0.1 and 1.0",
            default="0.5",
            required=True,
            max_length=4
        )
        
        self.add_item(self.strength1)
        self.add_item(self.strength2)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate strength inputs
            try:
                strength1 = float(self.strength1.value)
                strength2 = float(self.strength2.value)
                
                if not (0.1 <= strength1 <= 1.0 and 0.1 <= strength2 <= 1.0):
                    raise ValueError("Strength values must be between 0.1 and 1.0")
                    
            except ValueError as e:
                await interaction.response.send_message(
                    f"Invalid strength values: {str(e)}", 
                    ephemeral=True
                )
                return

            def check_message(m):
                return (m.author == interaction.user and
                    m.channel == interaction.channel and
                    len(m.attachments) > 0)

            # Defer the response first
            await interaction.response.defer(ephemeral=True)

            try:
                # Get first image
                first_prompt = await interaction.followup.send(
                    "Please send your first image", 
                    ephemeral=True,
                    wait=True
                )
                msg1 = await self.bot.wait_for('message', timeout=60.0, check=check_message)
                image1_data = await msg1.attachments[0].read()
                image1_filename = msg1.attachments[0].filename
                await msg1.delete()
                # Delete first prompt after image is received
                await first_prompt.delete()
                
                # Get second image
                second_prompt = await interaction.followup.send(
                    "Now send your second image", 
                    ephemeral=True,
                    wait=True
                )
                msg2 = await self.bot.wait_for('message', timeout=60.0, check=check_message)
                image2_data = await msg2.attachments[0].read()
                image2_filename = msg2.attachments[0].filename
                await msg2.delete()
                # Delete second prompt after image is received
                await second_prompt.delete()

                # Create processing message
                processing_msg = await interaction.followup.send(
                    "🔄 Processing Redux generation...",
                    ephemeral=False,
                    wait=True
                )

                # Create request item
                workflow_filename = f'redux_{str(uuid.uuid4())}.json'
                workflow = load_json('Redux.json')
                save_json(workflow_filename, workflow)

                request_item = ReduxRequestItem(
                    id=str(interaction.id),
                    user_id=str(interaction.user.id),
                    channel_id=str(interaction.channel.id),
                    interaction_id=str(interaction.id),
                    original_message_id=str(processing_msg.id),
                    resolution=self.resolution,
                    strength1=strength1,
                    strength2=strength2,
                    workflow_filename=workflow_filename,
                    image1=image1_data,
                    image2=image2_data,
                    image1_filename=image1_filename,
                    image2_filename=image2_filename
                )

                await self.bot.subprocess_queue.put(request_item)

            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "Timed out waiting for image upload", 
                    ephemeral=True,
                    wait=True
                )
                
        except Exception as e:
            logger.error(f"Error in redux modal: {str(e)}", exc_info=True)
            try:
                await interaction.followup.send(
                    f"An error occurred: {str(e)}",
                    ephemeral=True,
                    wait=True
                )
            except:
                # If followup fails, try response
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"An error occurred: {str(e)}",
                        ephemeral=True
                    )

class ReduxPromptModal(Modal, title='Redux Prompt'):
    def __init__(self, bot, resolution: str, strength: str):
        super().__init__()
        self.bot = bot
        self.resolution = resolution
        self.strength = strength

        self.prompt = TextInput(
            label='Enter your prompt',
            style=discord.TextStyle.paragraph,
            placeholder='Type your prompt here...',
            required=True,
            max_length=1000
        )

        self.seed = TextInput(
            label='Seed (optional)',
            style=discord.TextStyle.short,
            placeholder='Leave empty for random seed',
            required=False,
            max_length=20
        )

        self.add_item(self.prompt)
        self.add_item(self.seed)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Process seed value
            seed = None
            if self.seed.value.strip():
                try:
                    seed = int(self.seed.value)
                except ValueError:
                    await interaction.response.send_message(
                        "Invalid seed value. Please use a valid integer or leave empty for random seed.",
                        ephemeral=True
                    )
                    return

            # Check for banned words in the prompt
            is_banned, message = check_banned(str(interaction.user.id), self.prompt.value)
            if message:  # If there's a warning or ban message
                await interaction.response.send_message(message, ephemeral=True)
                if is_banned:  # If the user is banned, stop processing
                    return

            # Create a unique request ID
            request_id = str(uuid.uuid4())

            # Send message asking for image upload
            upload_msg = await interaction.response.send_message(
                "Please upload the reference image you'd like to use.",
                ephemeral=True
            )

            def check_message(m):
                return (m.author.id == interaction.user.id and 
                        m.channel.id == interaction.channel.id and 
                        len(m.attachments) > 0)

            try:
                # Wait for image upload
                message = await self.bot.wait_for('message', timeout=300.0, check=check_message)
                
                # Get the first attachment
                attachment = message.attachments[0]
                
                # Check if it's an image
                if not attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    await interaction.followup.send(
                        "Please upload a valid image file (PNG, JPG, JPEG, or WEBP).",
                        ephemeral=True
                    )
                    return

                # Save the image
                temp_dir = os.path.join('Main', 'Datasets', 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                image_path = os.path.join(temp_dir, f"{request_id}_{attachment.filename}")
                await attachment.save(image_path)

                # Delete both the upload message and the original request message
                try:
                    await message.delete()
                    original_message = await interaction.original_response()
                    await original_message.delete()
                except Exception as e:
                    logger.error(f"Error deleting messages: {str(e)}")

                # Load and update the workflow
                try:
                    base_workflow = load_json('Reduxprompt.json')
                    workflow = update_reduxprompt_workflow(
                        workflow=base_workflow,
                        image_path=image_path,
                        prompt=self.prompt.value,
                        strength=self.strength,
                        seed=seed,
                        resolution=self.resolution
                    )

                    # Save the modified workflow
                    workflow_filename = f'reduxprompt_{request_id}.json'
                    save_json(workflow_filename, workflow)

                    # Create processing message
                    processing_msg = await interaction.followup.send(
                        "🔄 Processing Redux generation...",
                        ephemeral=False
                    )

                    # Create request item
                    request_item = ReduxPromptRequestItem(
                        id=str(interaction.id),
                        user_id=str(interaction.user.id),
                        channel_id=str(interaction.channel.id),
                        interaction_id=str(interaction.id),
                        original_message_id=str(processing_msg.id),
                        resolution=self.resolution,
                        strength=self.strength,
                        prompt=self.prompt.value,
                        image_path=image_path,
                        image_filename=attachment.filename,
                        workflow_filename=workflow_filename,
                        seed=seed if seed is not None else None
                    )

                    # Add to bot's subprocess queue for processing
                    await self.bot.subprocess_queue.put(request_item)
                    logger.debug(f"Added request {request_id} to queue for processing")

                    # Send confirmation message
                    await interaction.followup.send(
                        f"Request queued for processing with the following settings:\n"
                        f"Resolution: {self.resolution}\n"
                        f"Strength: {self.strength}\n"
                        f"Prompt: {self.prompt.value}",
                        ephemeral=True
                    )

                except Exception as e:
                    logger.error(f"Error processing request: {str(e)}")
                    await interaction.followup.send(
                        f"Error processing request: {str(e)}",
                        ephemeral=True
                    )
                    # Clean up temp files if they exist
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            logger.error(f"Error cleaning up temp file: {str(e)}")

            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "You didn't upload an image in time. Please try again.",
                    ephemeral=True
                )
                return

        except Exception as e:
            logger.error(f"Error in ReduxPromptModal submission: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"An error occurred while processing your request: {str(e)}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while processing your request: {str(e)}",
                    ephemeral=True
                )

class ReduxProcessingView(View):
    def __init__(self, bot, resolution: str, strength1: float, strength2: float):
        super().__init__()
        self.bot = bot
        self.resolution = resolution
        self.strength1 = strength1
        self.strength2 = strength2
        self.image1 = None
        self.image2 = None

    @discord.ui.button(label="Upload Image 1", style=discord.ButtonStyle.primary)
    async def upload_image1(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Please upload the first image (send it as a message attachment)",
            ephemeral=True
        )
        
        def check(m):
            return (m.author == interaction.user and
                   m.channel == interaction.channel and
                   len(m.attachments) > 0)
        
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            self.image1 = await msg.attachments[0].read()
            button.disabled = True
            button.label = "✓ Image 1 Uploaded"
            await interaction.edit_original_response(view=self)
            await msg.delete()
            
            if self.image1 and self.image2:
                await self.process_images(interaction)
                
        except TimeoutError:
            await interaction.followup.send("Timed out waiting for image upload", ephemeral=True)

    @discord.ui.button(label="Upload Image 2", style=discord.ButtonStyle.primary)
    async def upload_image2(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "Please upload the second image (send it as a message attachment)",
            ephemeral=True
        )
        
        def check(m):
            return (m.author == interaction.user and
                   m.channel == interaction.channel and
                   len(m.attachments) > 0)
        
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            self.image2 = await msg.attachments[0].read()
            button.disabled = True
            button.label = "✓ Image 2 Uploaded"
            await interaction.edit_original_response(view=self)
            await msg.delete()
            
            if self.image1 and self.image2:
                await self.process_images(interaction)
                
        except TimeoutError:
            await interaction.followup.send("Timed out waiting for image upload", ephemeral=True)

    async def process_images(self, interaction: discord.Interaction):
        try:
            # Load and modify the Redux workflow
            workflow = load_json('Redux.json')
            
            # Update resolution
            if '49' in workflow:
                workflow['49']['inputs']['ratio_selected'] = self.resolution
            
            # Update strength values
            if '53' in workflow:
                workflow['53']['inputs']['conditioning_to_strength'] = self.strength1
            if '44' in workflow:
                workflow['44']['inputs']['conditioning_to_strength'] = self.strength2
            
            # Generate a unique workflow file
            request_uuid = str(uuid.uuid4())
            workflow_filename = f'redux_{request_uuid}.json'
            save_json(workflow_filename, workflow)

            # Create processing message
            processing_msg = await interaction.channel.send("🔄 Processing Redux generation...")

            # Create request item
            request_item = ReduxRequestItem(
                id=str(interaction.id),
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel.id),
                interaction_id=str(interaction.id),
                original_message_id=str(processing_msg.id),
                resolution=self.resolution,
                strength1=self.strength1,
                strength2=self.strength2,
                workflow_filename=workflow_filename,
                image1=self.image1,
                image2=self.image2
            )

            await interaction.client.subprocess_queue.put(request_item)

            # Disable all buttons after processing starts
            for child in self.children:
                child.disabled = True
            await interaction.edit_original_response(view=self)
            
        except Exception as e:
            logger.error(f"Error processing redux images: {str(e)}")
            await interaction.followup.send(
                f"An error occurred while processing: {str(e)}",
                ephemeral=True
            )

class ImageControlView(View):
    def __init__(self, bot, original_prompt=None, image_filename=None, original_resolution=None, original_loras=None, original_upscale_factor=None, original_seed=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.original_prompt = original_prompt
        self.image_filename = image_filename
        self.original_resolution = original_resolution
        self.original_loras = original_loras
        self.original_upscale_factor = original_upscale_factor
        self.original_seed = original_seed

    @discord.ui.button(label="Options", style=discord.ButtonStyle.primary, custom_id="options_button", emoji="📚")
    async def options(self, interaction: discord.Interaction, button: Button):
        options_view = OptionsView(
            self.bot, 
            self.original_prompt, 
            self.image_filename, 
            self.original_resolution, 
            self.original_loras, 
            self.original_upscale_factor,
            self.original_seed,
            interaction
        )
        await interaction.response.send_message("Choose your options:", view=options_view, ephemeral=True)

    @discord.ui.button(label="Regenerate", style=discord.ButtonStyle.primary, custom_id="regenerate_button", emoji="♻️")
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer(ephemeral=False)
            
            workflow = load_json(fluxversion)
            request_uuid = str(uuid.uuid4())
            new_seed = generate_random_seed()
            
            workflow = update_workflow(workflow, 
                                    self.original_prompt, 
                                    self.original_resolution, 
                                    self.original_loras, 
                                    self.original_upscale_factor,
                                    new_seed)

            workflow_filename = f'flux3_{request_uuid}.json'
            save_json(workflow_filename, workflow)

            new_message = await interaction.followup.send("Regenerating image...")

            request_item = RequestItem(
                id=str(interaction.id),
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel.id),
                interaction_id=str(interaction.id),
                original_message_id=str(new_message.id),
                prompt=self.original_prompt,
                resolution=self.original_resolution,
                loras=self.original_loras,
                upscale_factor=self.original_upscale_factor,
                workflow_filename=workflow_filename,
                seed=new_seed
            )
            await interaction.client.subprocess_queue.put(request_item)

        except Exception as e:
            logger.error(f"Error in regenerate button: {str(e)}", exc_info=True)
            await interaction.followup.send("An error occurred while regenerating the image.", ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_button", emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.message.delete()
        except discord.errors.NotFound:
            logger.warning("Message already deleted")
        except discord.errors.Forbidden:
            logger.warning("Missing permissions to delete message")
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")

class PromptModal(Modal, title="Edit Prompt"):
    def __init__(self, bot, original_prompt, image_filename, resolution, loras, upscale_factor, original_interaction, original_seed=None):
        super().__init__()
        self.bot = bot
        self.image_filename = image_filename
        self.resolution = resolution
        self.loras = loras
        self.upscale_factor = upscale_factor
        self.original_interaction = original_interaction

        self.prompt = TextInput(
            label="Prompt",
            style=discord.TextStyle.paragraph,
            placeholder="Enter your prompt here...",
            default=original_prompt,
            required=True
        )
        self.add_item(self.prompt)

        self.seed = TextInput(
            label="Seed (leave blank for random)",
            style=discord.TextStyle.short,
            placeholder="Enter a seed number or leave blank",
            default=str(original_seed) if original_seed is not None else "",
            required=False
        )
        self.add_item(self.seed)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lora_config = load_json('lora.json')
            base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.prompt.value)
            
            # Clean base prompt of any existing LoRA trigger words
            for lora in lora_config['available_loras']:
                if lora.get('prompt'):
                    base_prompt = base_prompt.replace(lora['prompt'], '').strip()
            
            # Clean up multiple commas and whitespace
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Get LoRA trigger words
            additional_prompts = []
            for lora in self.loras:
                lora_info = next((l for l in lora_config['available_loras'] if l['file'] == lora), None)
                if lora_info and lora_info.get('prompt') and lora_info['prompt'].strip():
                    additional_prompts.append(lora_info['prompt'].strip())
            
            # Join trigger words with commas and append to prompt
            trigger_words = ", ".join(additional_prompts) if additional_prompts else ""
            full_prompt = f"{base_prompt}, {trigger_words}" if trigger_words else base_prompt
            
            try:
                seed = int(self.seed.value) if self.seed.value else None
            except ValueError:
                seed = None

            workflow = load_json(fluxversion)
            request_uuid = str(uuid.uuid4())
            
            workflow = update_workflow(workflow, 
                                  full_prompt,
                                  self.resolution, 
                                  self.loras, 
                                  self.upscale_factor,
                                  seed)

            workflow_filename = f'flux3_{request_uuid}.json'
            save_json(workflow_filename, workflow)

            new_message = await interaction.response.send_message("Generating new image with updated options...")
            message = await interaction.original_response()

            request_item = RequestItem(
                id=str(interaction.id),
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel.id),
                interaction_id=str(interaction.id),
                original_message_id=str(message.id),
                prompt=full_prompt,
                resolution=self.resolution,
                loras=self.loras,
                upscale_factor=self.upscale_factor,
                workflow_filename=workflow_filename,
                seed=seed
            )
            await interaction.client.subprocess_queue.put(request_item)
            
        except Exception as e:
            logger.error(f"Error in modal submit: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)

class LoraInfoView(View):
    """A paginated view for displaying LoRA information"""
    def __init__(self, loras: List[dict]):
        super().__init__(timeout=300)  # 5 minute timeout
        self.loras = loras
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = (len(self.loras) + self.items_per_page - 1) // self.items_per_page
        self.message = None
        self.update_buttons()

    def get_page_content(self) -> str:
        """Get the content for the current page"""
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.loras))
        page_loras = self.loras[start_idx:end_idx]
        
        content = [f"Page {self.current_page + 1} of {self.total_pages}\n"]
        for lora in page_loras:
            name = lora.get('name', 'Unnamed')
            url = lora.get('url', '')
            
            entry = [f"**{name}**"]
            if url:
                entry.append(f"[LoraInfo]({url})")
            else:
                entry.append("*No info available*")
            
            # Add an empty line between entries
            entry.append("")
            content.append("\n".join(entry))
        
        return "\n".join(content)

    def update_buttons(self):
        """Update button states based on current page"""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1
        self.last_page.disabled = self.current_page >= self.total_pages - 1

    async def update_message(self, interaction: discord.Interaction):
        """Update the message with the current page content"""
        await interaction.response.edit_message(
            content=self.get_page_content(),
            view=self
        )

    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.gray)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = 0
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        await self.update_message(interaction)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.gray)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = self.total_pages - 1
        self.update_buttons()
        await self.update_message(interaction)

class ReduxImageView(View):
    """A simple view for Redux images that only contains a delete button."""
    def __init__(self):
        # Set timeout to None for persistent view
        super().__init__(timeout=None)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_button", emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: Button):
        """Handle the delete button press."""
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.message.delete()
        except discord.errors.NotFound:
            logger.warning("Message already deleted")
        except discord.errors.Forbidden:
            logger.warning("Missing permissions to delete message")
            await interaction.followup.send("I don't have permission to delete this message.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            await interaction.followup.send("An error occurred while trying to delete the message.", ephemeral=True)

class CreativityModal(Modal, title='Creativity Settings'):
    def __init__(self, bot, resolution: str = None, initial_prompt: str = None, upscale_factor: int = 1, initial_seed: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.resolution = resolution
        self.upscale_factor = upscale_factor

        self.prompt = TextInput(
            label='Enter your prompt',
            style=discord.TextStyle.paragraph,
            placeholder='Type your prompt here...',
            default=initial_prompt if initial_prompt else '',
            required=True,
            max_length=1000
        )

        self.seed = TextInput(
            label='Seed (optional)',
            style=discord.TextStyle.short,
            placeholder='Leave empty for random seed',
            default=str(initial_seed) if initial_seed is not None else '',
            required=False,
            max_length=20
        )

        self.creativity = TextInput(
            label='Creativity Level (1-10)',
            style=discord.TextStyle.short,
            placeholder='1: No changes, 5: Moderate, 10: Extreme',
            default='5',
            required=True,
            max_length=2
        )

        self.add_item(self.prompt)
        self.add_item(self.seed)
        self.add_item(self.creativity)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=False)
            
            # Validate creativity value
            try:
                creativity = int(self.creativity.value)
                if not 1 <= creativity <= 10:
                    raise ValueError("Creativity must be between 1 and 10")
            except ValueError as e:
                await interaction.followup.send(f"Invalid creativity value: {e}", ephemeral=True)
                return

            # Get the prompt and seed
            prompt = self.prompt.value
            seed = int(self.seed.value) if self.seed.value else None

            # Convert creativity level from 1-10 to temperature (0.1-1.0)
            temperature = creativity / 10.0

            try:
                # Initialize AI provider if needed
                if not hasattr(self.bot, 'ai_provider') or not self.bot.ai_provider:
                    try:
                        logger.info(f"Initializing AI provider: {AI_PROVIDER}")
                        self.bot.ai_provider = AIProviderFactory.get_provider(AI_PROVIDER)
                        logger.info(f"Successfully initialized {AI_PROVIDER} provider")
                    except Exception as e:
                        logger.error(f"Failed to initialize AI provider: {e}")
                        await interaction.followup.send(
                            "Could not initialize AI provider. Using original prompt.",
                            ephemeral=True
                        )
                        await process_image_request(
                            interaction,
                            prompt,
                            self.resolution,
                            upscale_factor=self.upscale_factor,
                            seed=seed
                        )
                        return

                enhanced_prompt = await self.bot.ai_provider.generate_response(
                    prompt,
                    temperature=temperature
                )

                # Get the enhancement level description
                if creativity == 1:
                    level_desc = "No enhancement"
                elif creativity == 2:
                    level_desc = "Minimal enhancement"
                elif creativity == 3:
                    level_desc = "Light enhancement"
                elif creativity == 4:
                    level_desc = "Moderate enhancement"
                elif creativity == 5:
                    level_desc = "Balanced enhancement"
                elif creativity == 6:
                    level_desc = "Notable enhancement"
                elif creativity == 7:
                    level_desc = "Significant enhancement"
                elif creativity == 8:
                    level_desc = "Extensive enhancement"
                elif creativity == 9:
                    level_desc = "Substantial enhancement"
                else:  # 10
                    level_desc = "Maximum enhancement"

                logger.info(f"Enhanced prompt (creativity {creativity} - {level_desc}): {enhanced_prompt}")
                
                if creativity > 1:
                    await interaction.followup.send(
                        f"Creativity Level {creativity} ({level_desc}):\n"
                        f"Original prompt: {prompt}\n"
                        f"Enhanced prompt: {enhanced_prompt}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Creativity Level 1 (No enhancement): Using original prompt",
                        ephemeral=True
                    )
                
                await process_image_request(
                    interaction,
                    enhanced_prompt,
                    self.resolution,
                    upscale_factor=self.upscale_factor,
                    seed=seed
                )

            except Exception as e:
                logger.error(f"Error in prompt enhancement: {e}")
                await interaction.followup.send(
                    f"Error enhancing prompt: {str(e)}. Using original prompt.",
                    ephemeral=True
                )
                await process_image_request(
                    interaction,
                    prompt,
                    self.resolution,
                    upscale_factor=self.upscale_factor,
                    seed=seed
                )

        except Exception as e:
            logger.error(f"Error in creativity modal: {e}")
            await interaction.followup.send(
                "An error occurred while processing your request.",
                ephemeral=True
            )

# Optional interface class for better type hints and documentation
class ViewInterface:
    """Interface class defining the expected view structure"""
    ImageControlView = ImageControlView
    LoRAView = LoRAView
    OptionsView = OptionsView
    PromptModal = PromptModal
    PaginatedLoRASelect = PaginatedLoRASelect
    ResolutionSelect = ResolutionSelect
    LoraInfoView = LoraInfoView
    ReduxImageView = ReduxImageView
    CreativityModal = CreativityModal

__all__ = [
    'ImageControlView',
    'LoRAView',
    'OptionsView',
    'PromptModal',
    'PaginatedLoRASelect',
    'ResolutionSelect',
    'LoraInfoView',
    'ReduxImageView',
    'ViewInterface',
    'CreativityModal'
]