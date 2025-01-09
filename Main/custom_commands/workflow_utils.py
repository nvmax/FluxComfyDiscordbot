import logging
import json
from Main.utils import load_json, generate_random_seed
import os
import random

logger = logging.getLogger(__name__)

def validate_workflow(workflow):
    """Validates the workflow structure with enhanced checks"""
    if not isinstance(workflow, dict):
        raise ValueError("Workflow must be a dictionary")
    
    # Check for required nodes
    required_nodes = ['69', '258', '271']
    missing_nodes = [node for node in required_nodes if node not in workflow]
    if missing_nodes:
        raise ValueError(f"Missing required nodes in workflow: {missing_nodes}")
    
    # Validate node structure
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            raise ValueError(f"Node {node_id} must be a dictionary")
        
        if 'inputs' not in node:
            raise ValueError(f"Node {node_id} is missing 'inputs' field")
            
        if not isinstance(node.get('inputs'), dict):
            raise ValueError(f"Node {node_id} 'inputs' must be a dictionary")
            
        if 'class_type' not in node:
            raise ValueError(f"Node {node_id} is missing 'class_type' field")
    
    logger.debug(f"Workflow validation passed: {len(workflow)} nodes checked")
    return True

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    """Updates the workflow with the provided parameters with enhanced validation"""
    try:
        # Validate workflow first
        validate_workflow(workflow)
        logger.debug("Initial workflow validation passed")

        # Create a copy to avoid modifying the original
        workflow = workflow.copy()

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
                    logger.debug(f"Added LoRA {lora} with strength {lora_strength}")
                else:
                    logger.warning(f"LoRA {lora} not found in configuration")

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

        # Validate the updated workflow
        validate_workflow(workflow)
        logger.debug("Final workflow validation passed")
        
        # Update guidance value if present
        if '198:4' in workflow and 'inputs' in workflow['198:4']:
            workflow['198:4']['inputs']['guidance'] = 3.5
            logger.debug("Set default guidance value to 3.5")
        
        # Keep original steps value from workflow template
        if '198:1' in workflow and 'inputs' in workflow['198:1']:
            original_steps = workflow['198:1']['inputs'].get('steps', 20)  # fallback to 20 if not found
            logger.debug(f"Using steps value from workflow: {original_steps}")

        return workflow

    except Exception as e:
        logger.error(f"Error updating workflow: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to update workflow: {str(e)}")

def update_reduxprompt_workflow(workflow, image_path, prompt, strength, seed=None, resolution=None):
    """
    Updates the ReduxPrompt workflow with the provided parameters.
    The strength parameter must be one of: 'highest', 'high', 'medium', 'low', 'lowest'
    
    Args:
        workflow: The workflow dictionary to update
        image_path: Full absolute path to the image file
        prompt: The prompt text
        strength: Strength value ('highest', 'high', 'medium', 'low', 'lowest')
        seed: Optional seed value for generation. If None, a random seed will be used
        resolution: Optional resolution value for the image generation
    """
    try:
        # Create a copy to avoid modifying the original
        workflow = workflow.copy()

        # Generate random seed if none provided
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
            logger.debug(f"Generated random seed: {seed}")

        # Validate strength is one of the allowed values
        valid_strengths = ['highest', 'high', 'medium', 'low', 'lowest']
        if strength not in valid_strengths:
            raise ValueError(f"Invalid strength value: {strength}. Must be one of: {', '.join(valid_strengths)}")

        # Convert Windows path to forward slashes and ensure absolute path
        image_path = os.path.abspath(image_path).replace('\\', '/')
        logger.debug(f"Using image path: {image_path}")

        # Update image path in node 40
        if '40' in workflow:
            workflow['40']['inputs']['image'] = image_path
            logger.debug(f"Updated image path in node 40: {image_path}")
        else:
            raise ValueError("Node 40 (LoadImage node) not found in workflow")

        # Update prompt in node 6 if it exists
        if '6' in workflow:
            workflow['6']['inputs']['text'] = prompt
            logger.debug(f"Updated prompt in node 6: {prompt}")

        # Update strength in node 54 if it exists (using string value directly)
        if '54' in workflow:
            workflow['54']['inputs']['image_strength'] = strength
            logger.debug(f"Updated strength in node 54: {strength}")

        # Update seed in RandomNoise node
        if '25' in workflow:
            workflow['25']['inputs']['noise_seed'] = seed
            logger.debug(f"Updated seed in RandomNoise node: {seed}")

        # Update resolution in node 62 if resolution is provided
        if resolution and '62' in workflow:
            workflow['62']['inputs']['ratio_selected'] = resolution
            logger.debug(f"Updated resolution in node 62: {resolution}")
        elif '62' in workflow:
            logger.warning("Resolution not provided, using default in node 62")
        else:
            logger.warning("Node 62 (resolution node) not found in workflow")

        return workflow

    except Exception as e:
        logger.error(f"Error updating ReduxPrompt workflow: {str(e)}")
        raise