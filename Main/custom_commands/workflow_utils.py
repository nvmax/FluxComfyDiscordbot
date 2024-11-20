import logging
from Main.utils import load_json

logger = logging.getLogger(__name__)

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    """
    Updates the workflow with the provided parameters.
    """
    try:
        # Update prompt
        if '69' in workflow:
            workflow['69']['inputs']['prompt'] = prompt
            logger.debug(f"Updated prompt: {prompt}")
        else:
            logger.warning("Node 69 (prompt node) not found in workflow")

        # Update resolution
        if '258' in workflow:
            workflow['258']['inputs']['ratio_selected'] = resolution
            logger.debug(f"Updated resolution: {resolution}")
        else:
            logger.warning("Node 258 (resolution node) not found in workflow")

        # Update LoRAs
        if '271' in workflow:
            lora_loader = workflow['271']['inputs']
            
            # Load lora config
            lora_config = load_json('lora.json')
            lora_info = {lora['file']: lora for lora in lora_config['available_loras']}

            # Clean existing LoRA entries
            for key in list(lora_loader.keys()):
                if key.startswith('lora_'):
                    del lora_loader[key]

            # Add new LoRA entries
            for i, lora in enumerate(loras, start=1):
                if lora in lora_info:
                    lora_key = f'lora_{i}'
                    # Get base strength from config
                    base_strength = float(lora_info[lora].get('weight', 1.0))
                    
                    # If multiple LoRAs are selected, scale down to 0.5 unless already lower
                    if len(loras) > 1:
                        lora_strength = min(base_strength, 0.5)
                    else:
                        lora_strength = base_strength
                        
                    lora_loader[lora_key] = {
                        'on': True,
                        'lora': lora,
                        'strength': lora_strength
                    }
                    logger.debug(f"Added LoRA {lora} with strength {lora_strength} (base strength: {base_strength})")
                else:
                    logger.warning(f"LoRA {lora} not found in lora.json")
        else:
            logger.warning("Node 271 (LoRA loader) not found in workflow")

        # Update upscale factor
        if '279' in workflow:
            workflow['279']['inputs']['rescale_factor'] = upscale_factor
            logger.debug(f"Updated upscale factor: {upscale_factor}")
        else:
            logger.warning("Node 279 (upscale node) not found in workflow")

        # Update seed
        if '198:2' in workflow:
            workflow['198:2']['inputs']['noise_seed'] = seed
            logger.debug(f"Updated seed: {seed}")
        else:
            logger.warning("Node 198:2 (seed node) not found in workflow")
            
        # Update guidance value if present
        if '198:4' in workflow and 'inputs' in workflow['198:4']:
            workflow['198:4']['inputs']['guidance'] = 3.5
            logger.debug("Set default guidance value to 3.5")
        
        # Update steps value if present
        if '198:1' in workflow and 'inputs' in workflow['198:1']:
            workflow['198:1']['inputs']['steps'] = 20
            logger.debug("Set default steps value to 20")

        return workflow

    except Exception as e:
        logger.error(f"Error updating workflow: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to update workflow: {str(e)}")