import discord
import logging
import uuid
from typing import Optional, List, Any, Dict

# Third-party imports
from discord import Interaction

# Local application imports
from Main.utils import load_json, save_json, generate_random_seed
from .workflow_utils import update_workflow
from config import fluxversion

logger = logging.getLogger(__name__)

async def process_image_request(interaction: discord.Interaction, prompt: str, resolution: str, upscale_factor: int = 1, seed: Optional[int] = None):
    """Process a standard image generation request without prompt enhancement."""
    try:
        # Only defer if we haven't responded yet (i.e., no warning message was sent)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False)
        
        # Show LoRA selection view
        from .views import LoRAView  # Import here to avoid circular import
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
        lora_config = load_json('lora.json')
        additional_prompts = []
        for lora_file in selected_loras:
            lora_info = next(
                (l for l in lora_config['available_loras'] if l['file'] == lora_file),
                None
            )
            if lora_info and lora_info.get('add_prompt') and lora_info['add_prompt'].strip():
                additional_prompts.append(lora_info['add_prompt'].strip())
        
        # Construct final prompt with new trigger words
        full_prompt = prompt
        if additional_prompts:
            if not full_prompt.endswith(','):
                full_prompt += ','
            full_prompt += ' ' + ', '.join(additional_prompts)
        
        full_prompt = full_prompt.strip(' ,')
        logger.debug(f"Final prompt with LoRA triggers: {full_prompt}")
        
        # Use provided seed or generate new one
        current_seed = seed if seed is not None else generate_random_seed()
        
        workflow = load_json(fluxversion)
        request_uuid = str(uuid.uuid4())
        
        workflow = update_workflow(
            workflow,
            full_prompt,
            resolution,
            selected_loras,
            upscale_factor,
            current_seed
        )

        workflow_filename = f'flux3_{request_uuid}.json'
        save_json(workflow_filename, workflow)

        original_message = await interaction.followup.send(
            "🔄 Starting generation process...",
            ephemeral=False
        )

        from .models import RequestItem  # Import here to avoid circular import
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
            seed=current_seed
        )
        await interaction.client.subprocess_queue.put(request_item)
        
    except Exception as e:
        logger.error(f"Error in process_image_request: {str(e)}", exc_info=True)
        await interaction.followup.send(
            f"An error occurred while processing your request: {str(e)}",
            ephemeral=True
        )
