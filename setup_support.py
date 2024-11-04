import os
import logging
import requests
import tkinter as tk
from tkinter import filedialog
from tqdm import tqdm
from typing import Dict, List, Optional
import urllib3
import re
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import LocalTokenNotFoundError, RepositoryNotFoundError
import shutil


# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Required base models
BASE_MODELS = {
    'VAE Model': {
        'filename': 'ae.safetensors',
        'path': '/vae',
        'repo_id': 'black-forest-labs/FLUX.1-dev',
        'file': 'ae.safetensors',
        'source': 'huggingface'
    },
    'CLIP_L': {
        'filename': 'clip_l.safetensors',
        'path': '/clip',
        'repo_id': 'comfyanonymous/flux_text_encoders',
        'file': 'clip_l.safetensors',
        'source': 'huggingface'
    },
    'T5XXL_FP16': {
        'filename': 't5xxl_fp16.safetensors',
        'path': '/clip',
        'repo_id': 'comfyanonymous/flux_text_encoders',
        'file': 't5xxl_fp16.safetensors',
        'source': 'huggingface'
    },
    'T5XXL_FP8': {
        'filename': 't5xxl_fp8_e4m3fn.safetensors',
        'path': '/clip',
        'repo_id': 'comfyanonymous/flux_text_encoders',
        'file': 't5xxl_fp8_e4m3fn.safetensors',
        'source': 'huggingface'
    }
}

# Available checkpoints
CHECKPOINTS = {
    'FLUX 6GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ3KM.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944957',
        'workflow': 'fluxfusion6GB4step.json',
        'source': 'civitai'
    },
    'FLUX 8GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ50.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944799',
        'workflow': 'fluxfusion8GB4step.json',
        'source': 'civitai'
    },
    'FLUX 10GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ6K.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944704',
        'workflow': 'fluxfusion10GB4step.json',
        'source': 'civitai'
    },
    'FLUX 12GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ80.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '936976',
        'workflow': 'fluxfusion12GB4step.json',
        'source': 'civitai'
    },
    'FLUX 24GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2Fp16.safetensors',
        'path': '/checkpoints',
        'model_id': '630820',
        'version_id': '936309',
        'workflow': 'fluxfusion24GB4step.json',
        'source': 'civitai'
    },
    'FLUX Dev': {
        'filename': 'flux1-dev.safetensors',
        'path': '/checkpoints',
        'repo_id': 'black-forest-labs/FLUX.1-dev',
        'file': 'flux1-dev.safetensors',
        'workflow': 'FluxDev24GB.json',
        'source': 'huggingface'
    }
}

class SetupManager:
    def __init__(self):
        self.models_path = None
        self.selected_checkpoint = None
        self.hf_token = None
        self.civitai_token = None
        self.progress_callback = None
        self.env_file = '.env'
    
    def select_models_directory(self) -> Optional[str]:
        """Prompt user to select ComfyUI models directory"""
        root = tk.Tk()
        root.withdraw()
        models_dir = filedialog.askdirectory(title="Select ComfyUI Models Directory")
        return models_dir if models_dir else None

    def validate_huggingface_token(self, token: str) -> bool:
        """Validate Hugging Face token using HF Hub API"""
        try:
            api = HfApi(token=token)
            user = api.whoami()
            return user is not None
        except Exception as e:
            logger.error(f"HF token validation error: {str(e)}")
            return False

    def validate_civitai_token(self, token: str) -> bool:
        """Validate CivitAI token"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            response = requests.get(
                'https://civitai.com/api/v1/models',
                headers=headers,
                timeout=10
            )
            return response.status_code in [200, 401]  # 401 is ok as it means token format is valid
        except Exception as e:
            logger.error(f"CivitAI token validation error: {str(e)}")
            return False

    def get_civitai_download_url(self, model_id: str, version_id: str, token: str) -> str:
        """Get the direct download URL from CivitAI API"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        try:
            logger.info(f"Getting download URL for model_id: {model_id}, version_id: {version_id}")
            # First get the model version information
            response = requests.get(
                f'https://civitai.com/api/v1/model-versions/{version_id}',
                headers=headers
            )
            response.raise_for_status()
            
            version_data = response.json()
            logger.debug(f"Version data received: {version_data}")
            
            # Find the primary file
            for file in version_data.get('files', []):
                if file.get('primary', False):
                    download_url = file.get('downloadUrl')
                    logger.info(f"Found download URL: {download_url}")
                    return download_url
                    
            raise Exception("No primary file found in model version")
        
        except Exception as e:
            logger.error(f"Error getting CivitAI download URL: {str(e)}")
            raise

    def download_huggingface_file(self, repo_id: str, filename: str, local_dir: str, token: str) -> str:
        """Download file from Hugging Face using their API"""
        try:
            logger.info(f"Starting HuggingFace download: {repo_id}/{filename}")
            
            # Ensure the directory exists
            os.makedirs(local_dir, exist_ok=True)

            # Build the direct download URL
            url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            local_path = os.path.join(local_dir, filename)
            total_size = int(response.headers.get('content-length', 0))
            
            logger.info(f"Downloading {total_size} bytes to {local_path}")
            
            with open(local_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if self.progress_callback and total_size:
                                progress = (downloaded / total_size) * 100
                                self.progress_callback(progress)
            
            logger.info(f"Download complete: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Error downloading from Hugging Face: {str(e)}")
            if os.path.exists(os.path.join(local_dir, filename)):
                os.remove(os.path.join(local_dir, filename))
            raise

    def download_file(self, file_info: dict, output_path: str, token: str = None, source: str = 'huggingface'):
        """Download file with progress bar"""
        try:
            logger.info(f"Starting download process for source: {source}")
            logger.info(f"Target output path: {output_path}")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            if source == 'huggingface':
                url = f"https://huggingface.co/{file_info['repo_id']}/resolve/main/{file_info['file']}"
                logger.info(f"Downloading from URL: {url}")
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                
                response = requests.get(url, headers=headers, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                logger.info(f"Total file size: {total_size} bytes")
                
                with open(output_path, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                        if self.progress_callback:
                            self.progress_callback(100)
                    else:
                        downloaded = 0
                        chunk_size = 1024 * 1024  # 1MB chunks
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if self.progress_callback:
                                    progress = int((downloaded / total_size) * 100)
                                    logger.debug(f"Download progress: {progress}%")
                                    self.progress_callback(progress)
                    
            else:  # civitai
                logger.info("Processing CivitAI download...")
                download_url = self.get_civitai_download_url(
                    model_id=file_info['model_id'],
                    version_id=file_info['version_id'],
                    token=token
                )
                
                headers = {'Authorization': f'Bearer {token}'} if token else {}
                response = requests.get(download_url, headers=headers, stream=True, verify=False)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                logger.info(f"Total file size: {total_size} bytes")
                
                with open(output_path, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                        if self.progress_callback:
                            self.progress_callback(100)
                    else:
                        downloaded = 0
                        chunk_size = 1024 * 1024  # 1MB chunks
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if self.progress_callback:
                                    progress = int((downloaded / total_size) * 100)
                                    logger.debug(f"Download progress: {progress}%")
                                    self.progress_callback(progress)
                                        
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def check_and_download_dependencies(self, models_dir: str):
        """Check and download required base models"""
        logger.info("Starting dependency check...")
        for model_name, model_info in BASE_MODELS.items():
            model_path = os.path.join(
                models_dir.strip('/'), 
                model_info['path'].strip('/'), 
                model_info['filename']
            )
            
            if not os.path.exists(model_path):
                print(f"\nDownloading required model: {model_name}")
                try:
                    logger.info(f"Downloading {model_name} to {model_path}")
                    self.download_file(
                        file_info=model_info,
                        output_path=model_path,
                        token=self.hf_token if model_info['source'] == 'huggingface' else self.civitai_token,
                        source=model_info['source']
                    )
                except Exception as e:
                    logger.error(f"Failed to download {model_name}: {str(e)}")
                    raise

    def move_additional_files(self, models_path: str):
        """Move additional required files to their correct locations"""
        try:
            # Handle upscale model file
            source_upscale = os.path.join("ComfyUI", "models", "upscale_models", "4x-ClearRealityV1.pth")
            dest_upscale = os.path.join(models_path, "upscale_models", "4x-ClearRealityV1.pth")
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_upscale), exist_ok=True)
            
            if os.path.exists(source_upscale):
                logger.info(f"Moving upscale model from {source_upscale} to {dest_upscale}")
                if os.path.exists(dest_upscale):
                    logger.info("Upscale model already exists in destination, skipping...")
                else:
                    shutil.copy2(source_upscale, dest_upscale)
                    logger.info("Upscale model moved successfully")
            else:
                logger.warning(f"Source upscale model not found at {source_upscale}")
                
            # Handle ratios.json file
            # Get custom_nodes path by going up one level from models_path and adding custom_nodes
            custom_nodes_path = os.path.join(os.path.dirname(models_path.rstrip(os.sep)), "custom_nodes")
            source_ratios = os.path.join("required_files", "ratios.json")
            dest_ratios = os.path.join(custom_nodes_path, "mikey_nodes", "ratios.json")
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_ratios), exist_ok=True)
            
            if os.path.exists(source_ratios):
                logger.info(f"Moving ratios.json from {source_ratios} to {dest_ratios}")
                if os.path.exists(dest_ratios):
                    logger.info("ratios.json already exists in destination, skipping...")
                else:
                    shutil.copy2(source_ratios, dest_ratios)
                    logger.info("ratios.json moved successfully")
            else:
                logger.warning(f"Source ratios.json not found at {source_ratios}")
                
        except Exception as e:
            logger.error(f"Error moving additional files: {str(e)}")
            raise

    def load_env(self) -> Dict[str, str]:
        """Load existing environment variables from .env file"""
        logger.debug("Loading environment variables from .env file")
        env_vars = {}
        if os.path.exists(self.env_file):
            try:
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            try:
                                key, value = line.split('=', 1)
                                env_vars[key.strip()] = value.strip().strip('"\'')
                            except ValueError:
                                continue
                logger.debug(f"Loaded {len(env_vars)} variables from .env")
                return env_vars
            except Exception as e:
                logger.error(f"Error reading .env file: {str(e)}")
                return {}
        else:
            logger.debug("No .env file found")
            return {}

    def save_env(self, env_vars: Dict[str, str]):
        """Save environment variables while preserving comments and formatting"""
        logger.debug("Saving environment variables to .env file")
        try:
            existing_lines = []
            if os.path.exists(self.env_file):
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()

            # Process existing lines and update values
            new_lines = []
            updated_vars = set()

            for line in existing_lines:
                line_strip = line.strip()
                if line_strip and not line_strip.startswith('#'):
                    try:
                        # Split only on the first '=' to preserve any '=' in the value
                        if '=' in line_strip:
                            key = line_strip.split('=', 1)[0].strip()
                            if key in env_vars:
                                # Check if the original line had quotes
                                original_value = line_strip.split('=', 1)[1].strip()
                                has_quotes = original_value.startswith('"') and original_value.endswith('"')
                                
                                # Special handling for specific keys
                                if key in ['BOT_SERVER', 'server_address']:
                                    # Always preserve quotes and comments for these keys
                                    comment_part = line[line.find('#'):] if '#' in line else ''
                                    value = env_vars[key].replace('"', '')  # Remove any existing quotes
                                    new_lines.append(f'{key}="{value}"{comment_part}\n')
                                elif key == 'fluxversion':
                                    # Always use quotes for fluxversion
                                    value = env_vars[key].replace('"', '')  # Remove any existing quotes
                                    new_lines.append(f'{key}="{value}"\n')
                                else:
                                    # For other variables, preserve original formatting
                                    if has_quotes:
                                        value = env_vars[key].replace('"', '')  # Remove any existing quotes
                                        new_lines.append(f'{key}="{value}"\n')
                                    else:
                                        new_lines.append(f'{key}={env_vars[key]}\n')
                                updated_vars.add(key)
                            else:
                                new_lines.append(line)
                        else:
                            new_lines.append(line)
                    except Exception as e:
                        logger.error(f"Error processing line '{line}': {str(e)}")
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # Add any new variables that weren't in the file
            for key, value in env_vars.items():
                if key not in updated_vars:
                    if key in ['BOT_SERVER', 'server_address', 'fluxversion']:
                        value = value.replace('"', '')  # Remove any existing quotes
                        new_lines.append(f'{key}="{value}"\n')
                    else:
                        new_lines.append(f'{key}={value}\n')

            # Write back to file
            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            logger.debug(f"Successfully saved {len(env_vars)} variables to .env")
        except Exception as e:
            logger.error(f"Error saving to .env file: {str(e)}")
            raise

    def update_env_file(self, workflow_file: str):
        """Update .env file with selected workflow"""
        try:
            env_vars = self.load_env()
            env_vars['fluxversion'] = workflow_file
            self.save_env(env_vars)
            logger.debug(f"Updated fluxversion in .env to {workflow_file}")
        except Exception as e:
            logger.error(f"Error updating workflow in .env: {str(e)}")
            raise

    def get_tokens(self) -> Dict[str, str]:
        """Get both Hugging Face and CivitAI tokens, prompting if necessary"""
        env_vars = self.load_env()
        tokens = {}

        # Handle Hugging Face token
        hf_token = env_vars.get('HUGGINGFACE_TOKEN')
        if not hf_token or not self.validate_huggingface_token(hf_token):
            print("\nNo valid Hugging Face token found.")
            while True:
                print("Please enter your Hugging Face token (starts with 'hf_'):")
                hf_token = input().strip()
                if self.validate_huggingface_token(hf_token):
                    break
                print("Invalid token. Please try again.")
        tokens['HUGGINGFACE_TOKEN'] = hf_token

        # Handle CivitAI token
        civitai_token = env_vars.get('CIVITAI_API_TOKEN')
        if not civitai_token or not self.validate_civitai_token(civitai_token):
            print("\nNo valid CivitAI token found.")
            while True:
                print("Please enter your CivitAI token:")
                civitai_token = input().strip()
                if self.validate_civitai_token(civitai_token):
                    break
                print("Invalid token. Please try again.")
        tokens['CIVITAI_API_TOKEN'] = civitai_token

        # Save tokens to .env file
        env_vars.update(tokens)
        self.save_env(env_vars)

        return tokens

    def run_setup(self):
        """Run the complete setup process"""
        try:
            # Get tokens
            tokens = self.get_tokens()
            self.hf_token = tokens['HUGGINGFACE_TOKEN']
            self.civitai_token = tokens['CIVITAI_API_TOKEN']

            # Select models directory
            print("\nPlease select your ComfyUI models directory...")
            models_dir = self.select_models_directory()
            if not models_dir:
                logger.info("No directory selected. Setup cancelled.")
                print("No directory selected. Setup cancelled.")
                return False
            
            self.models_path = models_dir
            logger.info(f"Selected models directory: {models_dir}")

            # Select checkpoint
            print("\nAvailable checkpoints:")
            for i, (name, info) in enumerate(CHECKPOINTS.items(), 1):
                print(f"{i}. {name}")
            
            while True:
                try:
                    choice = int(input("\nSelect checkpoint number to download (or 0 to cancel): "))
                    if choice == 0:
                        logger.info("Setup cancelled by user")
                        print("Setup cancelled.")
                        return False
                    if 1 <= choice <= len(CHECKPOINTS):
                        checkpoint_name = list(CHECKPOINTS.keys())[choice - 1]
                        break
                    print("Invalid selection. Please try again.")
                except ValueError:
                    print("Please enter a number.")

            checkpoint_info = CHECKPOINTS[checkpoint_name]
            logger.info(f"Selected checkpoint: {checkpoint_name}")

            # Save the models path to .env
            env_vars = self.load_env()
            env_vars['COMFYUI_MODELS_PATH'] = models_dir
            self.save_env(env_vars)
            logger.info("Saved models path to .env")

            # Check and download dependencies
            print("\nChecking and downloading required models...")
            logger.info("Starting dependency downloads")
            self.check_and_download_dependencies(models_dir)

            # Download selected checkpoint
            checkpoint_path = os.path.join(
                models_dir.strip('/'),
                checkpoint_info['path'].strip('/'),
                checkpoint_info['filename']
            )
            
            print(f"\nDownloading checkpoint: {checkpoint_name}")
            logger.info(f"Starting checkpoint download: {checkpoint_name}")
            token = self.hf_token if checkpoint_info['source'] == 'huggingface' else self.civitai_token
            self.download_file(
                file_info=checkpoint_info,
                output_path=checkpoint_path,
                token=token,
                source=checkpoint_info['source']
            )

            # Update .env file with workflow
            logger.info(f"Updating .env with workflow: {checkpoint_info['workflow']}")
            self.update_env_file(checkpoint_info['workflow'])
            
            print("\nSetup completed successfully!")
            logger.info("Setup completed successfully")
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"\nError: {error_msg}")
            return False
