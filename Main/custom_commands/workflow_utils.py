import logging
from Main.utils import load_json

logger = logging.getLogger(__name__)

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    # Update prompt
    if '69' in workflow:
        workflow['69']['inputs']['prompt'] = prompt

    # Update resolution
    if '258' in workflow:
        workflow['258']['inputs']['ratio_selected'] = resolution

    # Update LoRAs
    if '271' in workflow:
        lora_loader = workflow['271']['inputs']
        lora_config = load_json('lora.json')
        lora_info = {lora['file']: lora for lora in lora_config['available_loras']}

        # Clear existing LoRAs
        for key in list(lora_loader.keys()):
            if key.startswith('lora_'):
                del lora_loader[key]

        # Add selected LoRAs
        for i, lora in enumerate(loras, start=1):
            lora_key = f'lora_{i}'
            if lora in lora_info:
                lora_loader[lora_key] = {
                    'on': True,
                    'lora': lora,
                    'strength': lora_info[lora]['weight']
                }
            else:
                logger.warning(f"LoRA {lora} not found in lora.json")

    # Update upscale factor
    if '264' in workflow:
        workflow['264']['inputs']['scale_by'] = upscale_factor

    # Update seed
    if '198:2' in workflow:
        workflow['198:2']['inputs']['noise_seed'] = seed
        logger.debug(f"Updated seed in workflow. New seed: {seed}")
    else:
        logger.warning("Node 198:2 not found in workflow")

    return workflow