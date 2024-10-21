# custom_commands/views.py
import discord
from discord import ui
from .models import RequestItem
import logging
import uuid
import time
import json
import re
from Main.utils import load_json, save_json, generate_random_seed
from .workflow_utils import update_workflow

logger = logging.getLogger(__name__)

class LoRASelectMenu(discord.ui.Select):
    def __init__(self, bot):
        options = [
            discord.SelectOption(label=lora['name'], value=lora['file'])
            for lora in bot.lora_options
        ]
        super().__init__(
            placeholder="Select LoRAs...",
            min_values=0,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_loras = self.values

class LoRAView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.selected_loras = []
        self.lora_select = LoRASelectMenu(bot)
        self.add_item(self.lora_select)

        self.confirm = discord.ui.Button(label="Confirm Selection", style=discord.ButtonStyle.primary)
        self.confirm.callback = self.confirm_callback
        self.add_item(self.confirm)

    async def confirm_callback(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.defer()

class OptionsView(ui.View):
   def __init__(self, bot, original_prompt, image_filename, original_resolution, original_loras, original_upscale_factor, original_seed, original_interaction):
       super().__init__(timeout=300)
       self.bot = bot
       self.original_prompt = original_prompt
       self.image_filename = image_filename
       self.original_upscale_factor = original_upscale_factor
       self.selected_resolution = original_resolution
       self.selected_loras = original_loras if original_loras else []
       self.original_interaction = original_interaction
       self.selected_seed = original_seed

       self.resolution_select = ResolutionSelect(bot, original_resolution)
       self.resolution_select.callback = self.resolution_callback
       self.add_item(self.resolution_select)

       self.lora_select = LoRASelectMenu(bot)
       self.lora_select.callback = self.lora_callback
       self.add_item(self.lora_select)

       self.confirm_button = ui.Button(label="Confirm and Edit Prompt", style=discord.ButtonStyle.primary)
       self.confirm_button.callback = self.confirm_callback
       self.add_item(self.confirm_button)

   async def resolution_callback(self, interaction: discord.Interaction):
       self.selected_resolution = self.resolution_select.values[0]
       await interaction.response.defer(ephemeral=True)

   async def lora_callback(self, interaction: discord.Interaction):
       self.selected_loras = self.lora_select.values
       await interaction.response.defer(ephemeral=True)

   async def confirm_callback(self, interaction: discord.Interaction):
    try:
        lora_config = load_json('lora.json')
        
        base_prompt = re.sub(r'\s*\(Timestamp:.*?\)', '', self.original_prompt)
        for lora in lora_config['available_loras']:
            if lora.get('add_prompt'):
                base_prompt = base_prompt.replace(lora['add_prompt'], '').strip()
        
        base_prompt = re.sub(r'\s*,\s*,\s*', ', ', base_prompt).strip(' ,')
        
        additional_prompts = [
            lora_info['add_prompt']
            for lora in self.selected_loras
            if (lora_info := next((l for l in lora_config['available_loras'] if l['file'] == lora), None))
            and lora_info.get('add_prompt')
        ]
        
        updated_prompt = f"{base_prompt} {', '.join(additional_prompts)}".strip()

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
            self.selected_loras,
            self.original_upscale_factor,
            self.original_interaction,
            self.selected_seed
        )
        await interaction.response.send_modal(modal)
        
    except Exception as e:
        logger.error(f"Error in confirm callback: {e}", exc_info=True)
        await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
       

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
            
            workflow = load_json('flux3.json')
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

            new_message = await interaction.followup.send("Regenerating image... 0% complete")

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

           workflow = load_json('flux3.json')
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

           new_message = await interaction.response.send_message("Generating new image with updated options... 0% complete")
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

class ResolutionSelect(ui.Select):
    def __init__(self, bot, original_resolution):
        options = [
            discord.SelectOption(label=res, value=res, default=(res == original_resolution))
            for res in bot.resolution_options
        ]
        super().__init__(placeholder="Choose resolution", options=options)

__all__ = ['ImageControlView', 'LoRAView', 'OptionsView']
