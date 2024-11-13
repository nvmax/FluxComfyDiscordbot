import logging
from Main.utils import load_json

logger = logging.getLogger(__name__)

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    """
    Updates the workflow with the provided parameters.
    Handles dynamic LoRA weight adjustment based on number of selected LoRAs.
    """
    try:
        # Update prompt (Node 69)
        if '69' in workflow:
            workflow['69']['inputs']['prompt'] = prompt
        else:
            logger.warning("Node 69 (prompt node) not found in workflow")

        # Update resolution (Node 258)
        if '258' in workflow:
            workflow['258']['inputs']['ratio_selected'] = resolution
        else:
            logger.warning("Node 258 (resolution node) not found in workflow")

        # Update LoRAs (Node 271)
        if '271' in workflow:
            lora_loader = workflow['271']['inputs']
            lora_config = load_json('lora.json')
            lora_info = {lora['file']: lora for lora in lora_config['available_loras']}

            # Clear existing LoRAs
            for key in list(lora_loader.keys()):
                if key.startswith('lora_') and key != 'PowerLoraLoaderHeaderWidget':
                    del lora_loader[key]

            # Add selected LoRAs with dynamic weight adjustment
            num_loras = len(loras)
            for i, lora in enumerate(loras, start=1):
                lora_key = f'lora_{i}'
                if lora in lora_info:
                    lora_data = lora_info[lora]
                    weight_config = lora_data.get('weight', 0.5)
                    
                    # Determine weight based on number of selected LoRAs
                    if isinstance(weight_config, dict):
                        # Use max weight for single LoRA, min weight for multiple LoRAs
                        weight = weight_config.get('max', 1.0) if num_loras == 1 else weight_config.get('min', 0.5)
                    else:
                        # Fallback for old format - use direct weight value
                        weight = float(weight_config)

                    lora_loader[lora_key] = {
                        'on': True,
                        'lora': lora,
                        'strength': weight
                    }
                    logger.debug(f"Set LoRA {lora} weight to {weight} (of {num_loras} total LoRAs)")
                else:
                    logger.warning(f"LoRA {lora} not found in lora.json")
        else:
            logger.warning("Node 271 (LoRA loader) not found in workflow")

        # Update CR Upscale Image node (Node 279)
        if '279' in workflow:
            workflow['279']['inputs']['rescale_factor'] = upscale_factor
            logger.debug(f"Updated rescale factor to: {upscale_factor}")
        else:
            logger.warning("Node 279 (CR Upscale Image) not found in workflow")

        # Update seed (Node 198:2)
        if '198:2' in workflow:
            workflow['198:2']['inputs']['noise_seed'] = seed
            logger.debug(f"Updated seed in workflow. New seed: {seed}")
        else:
            logger.warning("Node 198:2 (seed node) not found in workflow")

        return workflow

    except Exception as e:
        logger.error(f"Error updating workflow: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to update workflow: {str(e)}")