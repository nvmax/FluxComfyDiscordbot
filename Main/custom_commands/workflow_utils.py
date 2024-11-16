import logging
from Main.utils import load_json

logger = logging.getLogger(__name__)

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    """
    Updates the workflow with the provided parameters.
    """
    try:
        # Load lora config and get trigger words
        lora_config = load_json('lora.json')
        lora_info = {lora['file']: lora for lora in lora_config['available_loras']}

        # Add trigger words from selected loras to prompt
        trigger_words = []
        for lora in loras:
            if lora in lora_info and 'prompt' in lora_info[lora]:
                trigger_word = lora_info[lora]['prompt'].strip()
                if trigger_word:
                    trigger_words.append(trigger_word)

        # Combine original prompt with trigger words
        if trigger_words:
            if not prompt.endswith(','):
                prompt += ','
            prompt += ' ' + ', '.join(trigger_words)
        prompt = prompt.strip(' ,')

        # Update prompt (Node 69)
        if '69' in workflow:
            workflow['69']['inputs']['prompt'] = prompt
            logger.debug(f"Updated prompt with trigger words: {prompt}")
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

            # Clear existing LoRAs
            for key in list(lora_loader.keys()):
                if key.startswith('lora_') and key != 'PowerLoraLoaderHeaderWidget':
                    del lora_loader[key]

            # Add selected LoRAs
            for i, lora in enumerate(loras, start=1):
                lora_key = f'lora_{i}'
                if lora in lora_info:
                    lora_strength = lora_info[lora]['weight'] if lora_info[lora]['weight'] < 0.5 else (1.0 if len(loras) == 1 else 0.5)
                    lora_loader[lora_key] = {
                        'on': True,
                        'lora': lora,
                        'strength': lora_strength
                    }
                else:
                    logger.warning(f"LoRA {lora} not found in lora.json")

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

        # Update guidance value if it exists (Node 198:4)
        if '198:4' in workflow:
            if 'inputs' in workflow['198:4'] and 'guidance' in workflow['198:4']['inputs']:
                workflow['198:4']['inputs']['guidance'] = 3.5  # Default guidance value
        else:
            logger.warning("Node 198:4 (guidance node) not found in workflow")

        return workflow

    except Exception as e:
        logger.error(f"Error updating workflow: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to update workflow: {str(e)}")