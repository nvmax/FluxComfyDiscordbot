import websocket
import uuid
import json
import urllib.request
import urllib.parse
import requests
import sys
import logging
import os
import time
from Main.database import add_to_history
from Main.utils import generate_random_seed, load_json, save_json
import re
from dotenv import load_dotenv
from config import server_address, BOT_SERVER
from Main.custom_commands.workflow_utils import (
    update_workflow,
    update_reduxprompt_workflow,
    validate_workflow
)

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client_id = str(uuid.uuid4())

def open_workflow(workflow_filename):
    """Opens and loads workflow file from DataSets directory with validation"""
    try:
        workflow_path = f"Main/DataSets/{workflow_filename}"
        logger.debug(f"Opening workflow file: {workflow_path}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            # Read the file content
            content = f.read().strip()

            # Remove any BOM characters that might be present
            if content.startswith('\ufeff'):
                content = content[1:]

            # Parse the JSON carefully
            try:
                workflow = json.loads(content)
                if not isinstance(workflow, dict):
                    raise ValueError("Workflow must be a dictionary")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in workflow: {e}")
                raise

            logger.debug(f"Successfully loaded workflow with {len(workflow)} nodes")
            return workflow

    except FileNotFoundError:
        logger.error(f"Workflow file not found: {workflow_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading workflow: {str(e)}")
        raise

def update_workflow(workflow, prompt, resolution, loras, upscale_factor, seed):
    """Updates the workflow with the provided parameters with validation"""
    try:
        # Create a deep copy to avoid modifying original
        workflow = json.loads(json.dumps(workflow))

        # Update prompt
        if '69' in workflow:
            workflow['69']['inputs']['prompt'] = prompt
            logger.debug(f"Updated prompt in workflow")

        # Update resolution
        if '258' in workflow:
            workflow['258']['inputs']['ratio_selected'] = resolution
            logger.debug(f"Updated resolution in workflow")

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
                    lora_loader[lora_key] = {
                        'on': True,
                        'lora': lora,
                        'strength': float(lora_info[lora].get('weight', 1.0))
                    }
            logger.debug(f"Updated LoRAs in workflow: {len(loras)} LoRAs configured")

        # Update upscale factor
        if '279' in workflow:
            workflow['279']['inputs']['rescale_factor'] = upscale_factor
            logger.debug(f"Updated upscale factor in workflow")

        # Update seed
        if '198:2' in workflow:
            workflow['198:2']['inputs']['noise_seed'] = seed
            logger.debug(f"Updated seed in workflow: {seed}")

        # Validate the final workflow
        if not isinstance(workflow, dict):
            raise ValueError("Workflow must remain a dictionary after updates")

        logger.debug("Successfully updated workflow with all parameters")
        return workflow

    except Exception as e:
        logger.error(f"Error updating workflow: {str(e)}")
        raise ValueError(f"Failed to update workflow: {str(e)}")

def queue_prompt(workflow):
    """Queue a prompt for processing with enhanced validation and debugging"""
    try:
        # Validate workflow is a dictionary
        if not isinstance(workflow, dict):
            raise ValueError("Workflow must be a dictionary")

        # Create the request data
        request_data = {
            "prompt": workflow,
            "client_id": client_id
        }

        # Convert to JSON with minimal whitespace
        json_str = json.dumps(request_data, ensure_ascii=False, separators=(',', ':'))

        # Log the request data for debugging
        logger.debug(f"Sending request to ComfyUI prompt endpoint")
        logger.debug(f"Client ID: {client_id}")
        logger.debug(f"Request size: {len(json_str)} bytes")

        # Encode as UTF-8
        data = json_str.encode('utf-8')

        # Create and configure the request
        url = f"http://{server_address}:8188/prompt"
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': str(len(data))
        }

        logger.debug(f"Sending request to URL: {url}")
        logger.debug(f"Headers: {headers}")

        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers=headers
        )

        # Send the request with error handling
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                response_data = response.read().decode('utf-8')
                result = json.loads(response_data)
                if not isinstance(result, dict):
                    raise ValueError("Expected dictionary response from ComfyUI")
                logger.debug("Successfully queued prompt with ComfyUI")
                return result
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error: {e.code} - {e.reason}")
            logger.error(f"Response body: {e.read().decode('utf-8')}")
            raise
        except urllib.error.URLError as e:
            logger.error(f"URL Error: {str(e)}")
            raise

    except json.JSONDecodeError as e:
        logger.error(f"JSON encoding/decoding error: {str(e)}")
        logger.error(f"Problem data: {str(request_data)[:200]}...")
        raise ValueError(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        logger.error(f"Error in queue_prompt: {str(e)}")
        raise

def get_video(filename, subfolder, folder_type):
    """Gets a video file from ComfyUI's output directory"""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    url = f"http://{server_address}:8188/view?{url_values}"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read(), filename
    except Exception as e:
        logger.error(f"Error in get_video: {str(e)}")
        raise

def get_image(filename, subfolder, folder_type):
    """Gets an image file from ComfyUI's output directory"""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    url = f"http://{server_address}:8188/view?{url_values}"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read(), filename
    except Exception as e:
        logger.error(f"Error in get_image: {str(e)}")
        raise

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return json.loads(response.read())
    except Exception as e:
        logger.error(f"Error in get_history: {str(e)}")
        raise

def clear_cache(ws):
    clear_message = json.dumps({"type": "clear_cache"})
    ws.send(clear_message)
    logger.debug("Sent clear_cache message to ComfyUI")

def send_progress_update(request_id, progress_data):
    try:
        bot_server = os.getenv('BOT_SERVER', BOT_SERVER)
        retries = 3
        retry_delay = 1

        data = {
            'request_id': request_id,
            'progress_data': progress_data
        }

        for attempt in range(retries):
            try:
                response = requests.post(
                    f"http://{bot_server}:8080/update_progress",
                    json=data,
                    timeout=120
                )
                if response.status_code == 200:
                    logger.debug(f"Progress update sent: {progress_data}")
                    return
                else:
                    logger.warning(f"Progress update failed with status {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"All retry attempts failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error sending progress update: {str(e)}")

def get_images(ws, workflow, progress_callback):
    try:
        # Record the start time when we send the request to ComfyUI
        generation_start_time = time.time()
        logger.debug(f"Starting image generation at {generation_start_time}")

        prompt_response = queue_prompt(workflow)
        if 'prompt_id' not in prompt_response:
            raise ValueError("No prompt_id in response from queue_prompt")

        prompt_id = prompt_response['prompt_id']
        output_images = {}
        last_milestone = 0

        while True:
            out = ws.recv()
            if isinstance(out, str):
                try:
                    message = json.loads(out)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing WebSocket message: {e}")
                    continue

                if message['type'] == 'execution_start':
                    progress_callback({
                        "status": "execution",
                        "message": "Starting execution..."
                    })

                elif message['type'] == 'executing':
                    data = message['data']

                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        # Record the end time when generation is complete
                        generation_end_time = time.time()
                        generation_time = generation_end_time - generation_start_time
                        logger.debug(f"Image generation completed in {generation_time:.2f} seconds")

                        progress_callback({
                            "status": "complete",
                            "message": "Generation complete!",
                            "generation_time": generation_time
                        })
                        break

                    if "UNETLoader" in str(data) or "CLIPLoader" in str(data) or "VAELoader" in str(data):
                        progress_callback({
                            "status": "loading_models",
                            "message": "Loading models and preparing generation..."
                        })

                elif message['type'] == 'progress':
                    data = message['data']
                    current_step = data['value']
                    max_steps = data['max']
                    progress = int((current_step / max_steps) * 100)

                    current_milestone = (progress // 10) * 10
                    if current_milestone > last_milestone:
                        progress_callback({
                            "status": "generating",
                            "progress": progress
                        })
                        last_milestone = current_milestone

        history = get_history(prompt_id)[prompt_id]
        logger.debug(f"Got history for prompt {prompt_id}")

        # Debug log the available outputs
        logger.debug(f"Available outputs in history: {list(history['outputs'].keys())}")

        for node_id, node_output in history['outputs'].items():
            logger.debug(f"Processing output from node {node_id}")
            logger.debug(f"Node output keys: {list(node_output.keys())}")

            # Special handling for node 42 (VHS_VideoCombine)
            if node_id == '42':
                # Check all possible video output keys
                video_data = None
                if 'gifs' in node_output:
                    for gif in node_output['gifs']:
                        if gif['filename'].endswith('.mp4'):
                            video_data = gif
                            break

                if video_data:
                    logger.debug(f"Found video data in node 42: {video_data}")
                    video_bytes, filename = get_video(
                        video_data['filename'],
                        video_data.get('subfolder', ''),
                        video_data.get('type', 'output')
                    )
                    output_images[node_id] = [(video_bytes, filename)]
                    logger.debug(f"Successfully processed video: {filename}")

            # Handle regular image outputs
            elif 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data, filename = get_image(
                        image['filename'],
                        image.get('subfolder', ''),
                        image.get('type', 'output')
                    )
                    images_output.append((image_data, filename))
                output_images[node_id] = images_output

        if not output_images:
            logger.error("No outputs found in workflow execution")
            logger.error(f"History outputs: {history['outputs']}")
            raise ValueError("No outputs generated from workflow")

        # Calculate final generation time
        generation_end_time = time.time()
        generation_time = generation_end_time - generation_start_time
        logger.debug(f"Total image processing completed in {generation_time:.2f} seconds")

        # Return both the images and the generation time
        return output_images, generation_time

    except Exception as e:
        logger.error(f"Error in get_images: {str(e)}")
        progress_callback({
            "status": "error",
            "message": str(e)
        })
        raise

def calculate_upscaled_resolution(resolution, upscale_factor):
    try:
        ratios_config = load_json('ratios.json')

        if resolution not in ratios_config['ratios']:
            raise ValueError(f"Resolution {resolution} not found in ratios configuration")

        base_res = ratios_config['ratios'][resolution]
        width = base_res['width']
        height = base_res['height']

        final_width = width * upscale_factor
        final_height = height * upscale_factor

        return f"{final_width}x{final_height}"
    except Exception as e:
        logger.error(f"Error calculating upscaled resolution: {str(e)}")
        raise ValueError(f"Unable to calculate upscaled resolution: {str(e)}")

def cleanup_workflow_file(workflow_filename):
    """Delete a temporary workflow file and its associated temporary files after they've been used"""
    try:
        # Delete workflow file
        file_path = os.path.join('Main', 'DataSets', workflow_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Successfully deleted workflow file: {workflow_filename}")

        # Get the request ID from the workflow filename if it exists
        request_id = None
        if workflow_filename and ('_' in workflow_filename):
            request_id = workflow_filename.split('_', 1)[1].rsplit('.', 1)[0]
            logger.debug(f"Extracted request ID: {request_id}")

        # Check both temp directory and main directory
        dirs_to_check = [
            os.path.join('Main', 'DataSets', 'temp'),
            os.path.join('Main', 'DataSets')
        ]

        for dir_path in dirs_to_check:
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    try:
                        file_path = os.path.join(dir_path, file)
                        if os.path.isfile(file_path):
                            # If we have a request ID, check if file contains it
                            if request_id and request_id in file:
                                os.remove(file_path)
                                logger.debug(f"Deleted request-related file: {file} from {dir_path}")
                            # For temp directory, also clean up any temporary files
                            elif dir_path.endswith('temp'):
                                # Check for common image extensions
                                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                                    os.remove(file_path)
                                    logger.debug(f"Deleted temp image file: {file} from {dir_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file}: {str(e)}")
                        continue

    except Exception as e:
        logger.error(f"Error in cleanup_workflow_file: {str(e)}")
        # Don't raise the exception - we don't want cleanup failures to affect the main process

def send_final_image(request_id, user_id, channel_id, interaction_id, original_message_id,
                    prompt, resolution, upscaled_resolution, loras, upscale_factor,
                    seed, image_data, filename, workflow_filename=None, generation_time=None,
                    request_type="standard"):
    try:
        bot_server = os.getenv('BOT_SERVER', BOT_SERVER)
        retries = 3
        retry_delay = 1  # seconds

        # Determine if this is a video file
        is_video = filename.lower().endswith('.mp4')

        # For video files, we need to send the binary data directly
        if is_video:
            files = {
                'video_data': (
                    filename,
                    image_data,
                    'video/mp4' if is_video else 'image/png'
                )
            }
        else:
            files = {'image_data': (filename, image_data)}

        # Convert all data fields to strings to prevent encoding issues
        data = {
            'request_id': str(request_id),
            'user_id': str(user_id),
            'channel_id': str(channel_id),
            'interaction_id': str(interaction_id),
            'original_message_id': str(original_message_id),
            'prompt': str(prompt),
            'resolution': str(resolution),
            'upscaled_resolution': str(upscaled_resolution),
            'loras': json.dumps(loras),
            'upscale_factor': str(upscale_factor),
            'seed': str(seed),
            'is_video': str(is_video),
            'generation_time': str(generation_time) if generation_time is not None else '',
            'request_type': str(request_type)
        }

        for attempt in range(retries):
            try:
                response = requests.post(
                    f"http://{bot_server}:8080/send_image",
                    files=files,
                    data=data,
                    timeout=120
                )
                if response.status_code == 200:
                    logger.info(f"Successfully sent {'video' if is_video else 'image'}")
                    # Clean up workflow file after successful send
                    if workflow_filename:
                        cleanup_workflow_file(workflow_filename)
                    return response
                else:
                    logger.warning(f"Failed to send {'video' if is_video else 'image'}, status code: {response.status_code}")
                    logger.warning(f"Response content: {response.text}")
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All retry attempts failed: {str(e)}")
                    raise
    except Exception as e:
        logger.error(f"Error sending final {'video' if is_video else 'image'}: {str(e)}")
        raise

if __name__ == "__main__":
    ws = None  # Define ws at the module level
    workflow_filename = None
    temp_workflow = None  # Track temporary workflow file

    # Define retry-related constants at the module level
    max_retries = 3
    retry_delay = 2  # seconds

    try:
        if len(sys.argv) < 7:
            raise ValueError(f"Expected at least 7 arguments, but got {len(sys.argv) - 1}")

        request_id = sys.argv[1]
        user_id = sys.argv[2]
        channel_id = sys.argv[3]
        interaction_id = sys.argv[4]
        original_message_id = sys.argv[5]
        request_type = sys.argv[6]

        # Create temp directory if needed
        temp_dir = os.path.join('Main', 'DataSets', 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # Process based on request type
        if request_type == 'standard':  # Standard /comfy command
            full_prompt = sys.argv[7]
            resolution = sys.argv[8]
            loras = json.loads(sys.argv[9])
            upscale_factor = int(sys.argv[10])
            workflow_filename = sys.argv[11]
            seed = sys.argv[12] if len(sys.argv) > 12 else None

            # Send initial status
            send_progress_update(request_id, {
                'status': 'starting',
                'message': 'Starting Generation process...'
            })

            workflow = open_workflow(workflow_filename)

            # Process seed
            try:
                seed = int(seed) if seed != "None" else generate_random_seed()
                logger.debug(f"Using seed: {seed}")
            except ValueError:
                seed = generate_random_seed()

            # Update workflow with parameters
            workflow = update_workflow(
                workflow,
                full_prompt,
                resolution,
                loras,
                upscale_factor,
                seed
            )

            # Save updated workflow back to the same file
            save_json(workflow_filename, workflow)
            logger.debug(f"Updated workflow file: {workflow_filename}")

            upscaled_resolution = resolution

        elif request_type == 'redux':  # Redux command
            if len(sys.argv) < 13:
                raise ValueError("Not enough arguments for redux request")

            resolution = sys.argv[7]
            strength1 = float(sys.argv[8])
            strength2 = float(sys.argv[9])
            workflow_filename = sys.argv[10]
            image1_path = sys.argv[11]
            image2_path = sys.argv[12]

            workflow = open_workflow(workflow_filename)
            comfy_image1_path = os.path.abspath(image1_path)
            comfy_image2_path = os.path.abspath(image2_path)

            comfy_image1_path = comfy_image1_path.replace('\\', '/')
            comfy_image2_path = comfy_image2_path.replace('\\', '/')

            if '40' in workflow:
                workflow['40']['inputs']['image'] = comfy_image1_path
            if '46' in workflow:
                workflow['46']['inputs']['image'] = comfy_image2_path
            if '53' in workflow:
                workflow['53']['inputs']['conditioning_to_strength'] = strength1
            if '44' in workflow:
                workflow['44']['inputs']['conditioning_to_strength'] = strength2
            if '49' in workflow:
                workflow['49']['inputs']['ratio_selected'] = resolution
            # Add random seed generation for redux using node '25'
            if '25' in workflow:
                seed = generate_random_seed()
                workflow['25']['inputs']['noise_seed'] = seed
                logger.debug(f"Set random seed for redux in node 25: {seed}")

            upscale_factor = 1
            full_prompt = "Redux image generation"
            loras = []
            upscaled_resolution = resolution

        elif request_type == 'reduxprompt':  # ReduxPrompt command
            if len(sys.argv) < 12:
                raise ValueError("Not enough arguments for reduxprompt request")

            prompt = sys.argv[7]
            resolution = sys.argv[8]
            strength = sys.argv[9]
            workflow_filename = sys.argv[10]
            temp_image_path = sys.argv[11]

            # Send initial status
            send_progress_update(request_id, {
                'status': 'starting',
                'message': 'Loading workflow and preparing generation...'
            })

            workflow = open_workflow(workflow_filename)
            temp_image_path = os.path.abspath(temp_image_path)
            temp_image_path = temp_image_path.replace('\\', '/')

            # Update the workflow with our parameters
            try:
                if '40' in workflow:
                    workflow['40']['inputs']['image'] = temp_image_path
                if '6' in workflow:
                    workflow['6']['inputs']['text'] = prompt
                if '54' in workflow:
                    workflow['54']['inputs']['image_strength'] = strength
                if '62' in workflow:
                    workflow['62']['inputs']['ratio_selected'] = resolution
                # Add random seed generation for reduxprompt using node '25'
                if '25' in workflow:
                    seed = generate_random_seed()
                    workflow['25']['inputs']['noise_seed'] = seed
                    logger.debug(f"Set random seed for reduxprompt in node 25: {seed}")

                # Save the modified workflow
                save_json(workflow_filename, workflow)
                logger.debug(f"Saved modified workflow to: {workflow_filename}")
            except Exception as e:
                logger.error(f"Error updating workflow: {str(e)}")
                send_progress_update(request_id, {
                    'status': 'error',
                    'message': f"Error updating workflow: {str(e)}"
                })
                sys.exit(1)

            upscale_factor = 1
            full_prompt = prompt
            loras = []
            upscaled_resolution = resolution
            seed = None

        elif request_type == 'video':  # Video generation command
            if len(sys.argv) < 9:
                raise ValueError("Not enough arguments for video request")

            prompt = sys.argv[7]
            workflow_filename = sys.argv[8]

            # Send initial status
            send_progress_update(request_id, {
                'status': 'starting',
                'message': 'Starting video generation process...'
            })

            workflow = open_workflow(workflow_filename)

            # Generate random seed if not provided
            seed = generate_random_seed()

            # Update workflow nodes
            if '3' in workflow:
                workflow['3']['inputs']['seed'] = seed
            if '44' in workflow:
                workflow['44']['inputs']['text'] = prompt

            # Save the modified workflow
            save_json(workflow_filename, workflow)
            logger.debug(f"Updated video workflow file: {workflow_filename}")

            # Set these for compatibility with existing code
            full_prompt = prompt
            resolution = "video"  # Special case for video
            loras = []
            upscale_factor = 1
            upscaled_resolution = "video"

        else:
            raise ValueError(f"Invalid request type: {request_type}")

        # Get server address and client ID
        server_address = os.getenv('server_address', server_address)
        client_id = str(uuid.uuid4())

        # Connect to WebSocket with retries
        for attempt in range(max_retries):
            try:
                send_progress_update(request_id, {
                    'status': 'connecting',
                    'message': f'Connecting to ComfyUI (attempt {attempt + 1})...'
                })
                ws = websocket.create_connection(
                    f"ws://{server_address}:8188/ws?clientId={client_id}",
                    timeout=120
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"WebSocket connection attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All WebSocket connection attempts failed: {str(e)}")
                    raise

        try:
            # Clear cache and prepare for generation
            clear_cache(ws)

            send_progress_update(request_id, {
                'status': 'loading_models',
                'message': 'Loading models and preparing generation...'
            })

            # Generate images
            images, generation_time = get_images(ws, workflow, lambda data: send_progress_update(request_id, data))
            logger.info(f"Image generation completed in {generation_time:.2f} seconds")

            # Process output images
            final_image = None
            for node_id, image_data_list in reversed(images.items()):
                for image_data, filename in reversed(image_data_list):
                    if not filename.startswith('ComfyUI_temp'):
                        final_image = (image_data, filename)
                        break
                if final_image:
                    break

            if final_image:
                image_data, filename = final_image
                response = send_final_image(
                    request_id=request_id,
                    user_id=user_id,
                    channel_id=channel_id,
                    interaction_id=interaction_id,
                    original_message_id=original_message_id,
                    prompt=full_prompt,
                    resolution=resolution,
                    upscaled_resolution=upscaled_resolution,
                    loras=loras,
                    upscale_factor=upscale_factor,
                    seed=seed,
                    image_data=image_data,
                    filename=filename,
                    workflow_filename=workflow_filename,
                    generation_time=generation_time,  # Pass the generation time
                    request_type=request_type  # Pass the request type
                )

                add_to_history(user_id, full_prompt, workflow, filename, resolution, loras, upscale_factor)
            else:
                logger.error("No final image found to send.")
                send_progress_update(request_id, {
                    'status': 'error',
                    'message': 'No final image generated'
                })

        except Exception as e:
            logger.error(f"Error during image generation: {str(e)}", exc_info=True)
            send_progress_update(request_id, {
                'status': 'error',
                'message': f'Error during generation: {str(e)}'
            })
            raise

    except ValueError as ve:
        logger.error(f"Argument error: {str(ve)}")
        send_progress_update(request_id, {
            'status': 'error',
            'message': f'Configuration error: {str(ve)}'
        })
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        send_progress_update(request_id, {
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        })
    finally:
        # Clean up WebSocket connection
        if ws:
            try:
                ws.close()
                logger.debug("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")

        # Clean up temporary files
        try:
            # Clean up redux images if present
            if request_type == 'reduxprompt':
                if 'temp_image_path' in locals() and os.path.exists(temp_image_path):
                    try:
                        os.remove(temp_image_path)
                        logger.debug(f"Deleted temp file: {temp_image_path}")
                    except Exception as e:
                        logger.error(f"Error removing temp file {temp_image_path}: {str(e)}")

            # Clean up workflow file
            if 'workflow_filename' in locals() and workflow_filename:
                workflow_path = os.path.join("Main", "DataSets", workflow_filename)
                if os.path.exists(workflow_path):
                    try:
                        os.remove(workflow_path)
                        logger.debug(f"Deleted temporary workflow file: {workflow_filename}")
                    except Exception as e:
                        logger.error(f"Error removing temporary workflow file: {str(e)}")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")