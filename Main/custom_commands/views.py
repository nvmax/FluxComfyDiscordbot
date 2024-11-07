import discord
from discord import ui
from .models import RequestItem
import logging
import uuid
import time
import json
import asyncio
import re
from typing import List, Optional
from Main.utils import load_json, save_json, generate_random_seed
from .workflow_utils import update_workflow
from config import fluxversion

logger = logging.getLogger(__name__)

class PaginatedLoRASelect(discord.ui.Select):
    def __init__(self, lora_options: List[dict], page: int = 0, selected_loras: List[str] = None):
        self.all_options = []
        selected_loras = selected_loras or []
        
        # Create select options with proper default values
        for lora in lora_options:
            self.all_options.append(
                discord.SelectOption(
                    label=lora['name'],
                    value=lora['file'],
                    default=bool(lora['file'] in selected_loras)  # Explicitly convert to boolean
                )
            )
        
        # Calculate page slicing
        start_idx = page * 25
        end_idx = min(start_idx + 25, len(self.all_options))
        current_options = self.all_options[start_idx:end_idx]
        
        total_pages = (len(self.all_options) - 1) // 25 + 1
        super().__init__(
            placeholder=f"Select LoRAs (Page {page + 1}/{total_pages})",
            min_values=0,
            max_values=len(current_options),
            options=current_options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class PaginatedLoRASelect(discord.ui.Select):
    def __init__(self, lora_options: List[dict], page: int = 0, selected_loras: List[str] = None):
        self.all_options = []
        selected_loras = selected_loras or []
        
        # Create select options with proper default values
        for lora in lora_options:
            self.all_options.append(
                discord.SelectOption(
                    label=lora['name'],
                    value=lora['file'],
                    default=bool(lora['file'] in selected_loras)  # Explicitly convert to boolean
                )
            )
        
        # Calculate page slicing
        start_idx = page * 25
        end_idx = min(start_idx + 25, len(self.all_options))
        current_options = self.all_options[start_idx:end_idx]
        
        total_pages = (len(self.all_options) - 1) // 25 + 1
        super().__init__(
            placeholder=f"Select LoRAs (Page {page + 1}/{total_pages})",
            min_values=0,
            max_values=len(current_options),
            options=current_options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class LoRAView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.page = 0
        self.all_selections = set()
        self.selected_loras = []
        self.has_confirmed = False
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        # Create new select menu with current selections
        self.lora_select = PaginatedLoRASelect(
            self.bot.lora_options,
            self.page,
            list(self.all_selections)
        )
        self.add_item(self.lora_select)
        
        # Add navigation buttons if needed
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        
        if self.page > 0:
            previous_button = discord.ui.Button(
                custom_id="previous_page",
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                row=1
            )
            previous_button.callback = self.previous_page_callback
            self.add_item(previous_button)
        
        if self.page < total_pages - 1:
            next_button = discord.ui.Button(
                custom_id="next_page",
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                row=1
            )
            next_button.callback = self.next_page_callback
            self.add_item(next_button)
        
        # Always show selection count
        selection_count = len(self.all_selections)
        confirm_button = discord.ui.Button(
            custom_id="confirm",
            label=f"Confirm Selection ({selection_count})",
            style=discord.ButtonStyle.primary,
            row=2
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

        cancel_button = discord.ui.Button(
            custom_id="cancel",
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            row=2
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def previous_page_callback(self, interaction: discord.Interaction):
        # Update selections from current page
        if self.lora_select.values:
            self.all_selections.update(self.lora_select.values)
        
        self.page = max(0, self.page - 1)
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        # Update selections from current page
        if self.lora_select.values:
            self.all_selections.update(self.lora_select.values)
        
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        self.page = min(self.page + 1, total_pages - 1)
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def confirm_callback(self, interaction: discord.Interaction):
        # Update selections one last time
        if self.lora_select.values:
            self.all_selections.update(self.lora_select.values)
        
        self.selected_loras = list(self.all_selections)
        logger.debug(f"Confirming LoRA selection: {self.selected_loras}")
        self.has_confirmed = True
        self.stop()
        await interaction.response.defer()

    async def cancel_callback(self, interaction: discord.Interaction):
        self.all_selections.clear()
        self.selected_loras = []
        self.has_confirmed = False
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.all_selections.clear()
        self.selected_loras = []
        self.has_confirmed = False
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
            
        # Store the user_id from the first interaction
        if not hasattr(self, 'user_id'):
            self.user_id = interaction.user.id
            
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot use these controls.", 
                ephemeral=True
            )
            return False
            
        return True

class ResolutionSelect(ui.Select):
    def __init__(self, bot, original_resolution):
        # Create options from bot's resolution options
        options = [
            discord.SelectOption(
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
            discord.SelectOption(
                label=res,
                value=res,
                default=(res == current_resolution)
            )
            for res in bot.resolution_options
        ]

class OptionsView(ui.View):
    def __init__(self, bot, original_prompt, image_filename, original_resolution, original_loras, original_upscale_factor, original_seed, original_interaction):
        super().__init__(timeout=300)
        self.bot = bot
        self.original_prompt = original_prompt
        self.image_filename = image_filename
        self.original_upscale_factor = original_upscale_factor
        self.selected_resolution = original_resolution
        self.all_selected_loras = set(original_loras if original_loras else [])  # Changed to set
        self.original_interaction = original_interaction
        self.selected_seed = original_seed
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

        # LoRA select (Row 1)
        self.lora_select = PaginatedLoRASelect(
            self.bot.lora_options,
            self.page,
            list(self.all_selected_loras)  # Convert set to list for the select
        )
        self.add_item(self.lora_select)

        # Navigation buttons (Row 2)
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        
        if total_pages > 1:
            if self.page > 0:
                prev_button = ui.Button(
                    label=f"◀ Previous (Page {self.page}/{total_pages})",
                    custom_id="previous_page",
                    style=discord.ButtonStyle.secondary,
                    row=2
                )
                prev_button.callback = self.previous_page_callback
                self.add_item(prev_button)

            if self.page < total_pages - 1:
                next_button = ui.Button(
                    label=f"Next (Page {self.page + 2}/{total_pages}) ▶",
                    custom_id="next_page",
                    style=discord.ButtonStyle.secondary,
                    row=2
                )
                next_button.callback = self.next_page_callback
                self.add_item(next_button)

        # Action buttons (Row 3)
        confirm_button = ui.Button(
            label=f"Confirm Selection ({len(self.all_selected_loras)} LoRAs)",
            style=discord.ButtonStyle.primary,
            custom_id="confirm_button",
            row=3
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

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
        if hasattr(self.lora_select, 'values'):
            # Update selections from current page before changing
            self.all_selected_loras.update(self.lora_select.values)
            logger.debug(f"Stored selections before page change: {self.all_selected_loras}")
        
        self.page = max(0, self.page - 1)
        self.setup_view()
        await interaction.response.edit_message(view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        """Handle next page navigation"""
        if hasattr(self.lora_select, 'values'):
            # Update selections from current page before changing
            self.all_selected_loras.update(self.lora_select.values)
            logger.debug(f"Stored selections before page change: {self.all_selected_loras}")
        
        total_pages = (len(self.bot.lora_options) - 1) // 25 + 1
        self.page = min(self.page + 1, total_pages - 1)
        self.setup_view()
        await interaction.response.edit_message(view=self)

    async def confirm_callback(self, interaction: discord.Interaction):
        """Handle confirmation and prompt processing"""
        try:
            # Get final selections from current page
            if hasattr(self.lora_select, 'values'):
                self.all_selected_loras.update(self.lora_select.values)
            
            logger.debug(f"Final LoRA selections at confirmation: {self.all_selected_loras}")
            
            # Process the prompt with LoRA trigger words
            lora_config = load_json('lora.json')
            base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.original_prompt)
            
            # Clean base prompt of existing trigger words
            for lora in lora_config['available_loras']:
                if lora.get('add_prompt'):
                    base_prompt = base_prompt.replace(lora['add_prompt'], '').strip()
            
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Add trigger words from all selected LoRAs
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
                        logger.debug(f"Adding trigger word '{trigger_word}' for LoRA: {lora_file}")
            
            # Combine base prompt with trigger words
            updated_prompt = base_prompt
            if additional_prompts:
                if not updated_prompt.endswith(','):
                    updated_prompt += ','
                updated_prompt += ' ' + ', '.join(additional_prompts)
            updated_prompt = updated_prompt.strip(' ,')
            
            logger.debug(f"Final processed prompt: {updated_prompt}")

            try:
                if self.original_interaction:
                    await self.original_interaction.delete_original_response()
            except Exception as e:
                logger.error(f"Error deleting options message: {e}")

            modal = PromptModal(
                self.bot,
                updated_prompt,
                self.image_filename,
                self.selected_resolution,
                list(self.all_selected_loras),  # Convert set back to list for modal
                self.original_upscale_factor,
                self.original_interaction,
                self.selected_seed
            )
            await interaction.response.send_modal(modal)
            
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

class PromptModal(ui.Modal, title="Edit Prompt"):
    def __init__(self, bot, original_prompt, image_filename, resolution, loras, upscale_factor, original_interaction, original_seed=None):
        super().__init__()
        self.bot = bot
        self.image_filename = image_filename
        self.resolution = resolution
        self.loras = loras  # This will now be a list converted from the set
        self.upscale_factor = upscale_factor
        self.original_interaction = original_interaction

        self.prompt = ui.TextInput(
            label="Prompt",
            style=discord.TextStyle.paragraph,
            placeholder="Enter your prompt here...",
            default=original_prompt,
            required=True
        )
        self.add_item(self.prompt)

        self.seed = ui.TextInput(
            label="Seed (leave blank for random)",
            style=discord.TextStyle.short,
            placeholder="Enter a seed number or leave blank",
            default=str(original_seed) if original_seed is not None else "",
            required=False
        )
        self.add_item(self.seed)

        logger.debug(f"PromptModal initialized with LoRAs: {self.loras}")

class ImageControlView(ui.View):
    def __init__(self, bot, original_prompt=None, image_filename=None, original_resolution=None, original_loras=None, original_upscale_factor=None, original_seed=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.original_prompt = original_prompt
        self.image_filename = image_filename
        self.original_resolution = original_resolution
        self.original_loras = original_loras
        self.original_upscale_factor = original_upscale_factor
        self.original_seed = original_seed

    @ui.button(label="Options", style=discord.ButtonStyle.primary, custom_id="options_button", emoji="📚")
    async def options(self, interaction: discord.Interaction, button: ui.Button):
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

    @ui.button(label="Regenerate", style=discord.ButtonStyle.primary, custom_id="regenerate_button", emoji="♻️")
    async def regenerate(self, interaction: discord.Interaction, button: ui.Button):
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

    @ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_button", emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.message.delete()
        except discord.errors.NotFound:
            logger.warning("Message already deleted")
        except discord.errors.Forbidden:
            logger.warning("Missing permissions to delete message")
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")

class PromptModal(ui.Modal, title="Edit Prompt"):
    def __init__(self, bot, original_prompt, image_filename, resolution, loras, upscale_factor, original_interaction, original_seed=None):
        super().__init__()
        self.bot = bot
        self.image_filename = image_filename
        self.resolution = resolution
        self.loras = loras
        self.upscale_factor = upscale_factor
        self.original_interaction = original_interaction

        self.prompt = ui.TextInput(
            label="Prompt",
            style=discord.TextStyle.paragraph,
            placeholder="Enter your prompt here...",
            default=original_prompt,
            required=True
        )
        self.add_item(self.prompt)

        self.seed = ui.TextInput(
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
            
            # Clean base prompt
            for lora in lora_config['available_loras']:
                if lora.get('add_prompt'):
                    base_prompt = base_prompt.replace(lora['add_prompt'], '').strip()
            
            base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
            
            # Add new LoRA prompts
            additional_prompts = [
                lora_info['add_prompt']
                for lora in self.loras
                if (lora_info := next((l for l in lora_config['available_loras'] if l['file'] == lora), None))
                and lora_info.get('add_prompt')
            ]
            
            full_prompt = f"{base_prompt} {', '.join(additional_prompts)}".strip()
            
            try:
                seed = int(self.seed.value) if self.seed.value else None
            except ValueError:
                seed = None

            workflow = load_json(fluxversion)
            request_uuid = str(uuid.uuid4())
            current_timestamp = int(time.time())
            
            workflow = update_workflow(workflow, 
                                  f"{full_prompt} (Timestamp: {current_timestamp})", 
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

# Optional interface class for better type hints and documentation
class ViewInterface:
    """Interface class defining the expected view structure"""
    ImageControlView = ImageControlView
    LoRAView = LoRAView
    OptionsView = OptionsView
    PromptModal = PromptModal
    PaginatedLoRASelect = PaginatedLoRASelect
    ResolutionSelect = ResolutionSelect

__all__ = [
    'ImageControlView',
    'LoRAView',
    'OptionsView',
    'PromptModal',
    'PaginatedLoRASelect',
    'ResolutionSelect',
    'ViewInterface'
]