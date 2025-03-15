import os
import json
import shutil
import asyncio
import aiohttp
import logging
import concurrent.futures
from pathlib import Path
from typing import Optional, Dict, Any
from huggingface_hub import hf_hub_download, HfApi, hf_hub_url
import tkinter as tk
from tkinter import filedialog
from tqdm.auto import tqdm
import urllib3
import re
import requests
from dataclasses import dataclass
from comfyui_validator import ComfyUIValidator
import time
import sys
import multiprocessing
import queue
import threading
from functools import partial

# Configure root logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_hf_transfer():
    """Initialize and verify HF Transfer configuration"""
    try:
        # First unset any existing HF env vars to ensure clean state
        for key in list(os.environ.keys()):
            if key.startswith('HF_'):
                del os.environ[key]
        
        # Set required environment variables with verbose logging
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        os.environ["HF_TRANSFER_DISABLE_PROGRESS_BARS"] = "1"
        
        # Try importing hf_transfer
        import hf_transfer
        import importlib
        importlib.reload(hf_transfer)  # Reload to ensure new env vars are picked up
        
        logger.info(f"HF Transfer {hf_transfer.__version__} initialized successfully")
        logger.info(f"HF_HUB_ENABLE_HF_TRANSFER: {os.environ.get('HF_HUB_ENABLE_HF_TRANSFER', 'Not Set')}")
        logger.info(f"HF_TRANSFER_DISABLE_PROGRESS_BARS: {os.environ.get('HF_TRANSFER_DISABLE_PROGRESS_BARS', 'Not Set')}")
        
        return True
    except ImportError as e:
        logger.error(f"Failed to import hf_transfer: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in HF Transfer setup: {e}")
        return False

# Initialize HF Transfer
if not setup_hf_transfer():
    logger.warning("HF Transfer not available - falling back to standard downloads")


# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    },
    'CLIP_GmP': {
        'filename': 'ViT-L-14-TEXT-detail-improved-hiT-GmP-state_dict.pt',
        'path': '/clip',
        'repo_id': 'zer0int/CLIP-GmP-ViT-L-14',
        'file': 'ViT-L-14-TEXT-detail-improved-hiT-GmP-state_dict.pt',
        'source': 'huggingface'
    },
    'FLUX_Redux': {
        'filename': 'flux1-redux-dev.safetensors',
        'path': '/style_models',
        'repo_id': 'black-forest-labs/FLUX.1-Redux-dev',
        'file': 'flux1-redux-dev.safetensors',
        'source': 'huggingface'
    },
    'SigClip_Vision': {
        'filename': 'sigclip_vision_patch14_384.safetensors',
        'path': '/clip_vision',
        'repo_id': 'Comfy-Org/sigclip_vision_384',
        'file': 'sigclip_vision_patch14_384.safetensors',
        'source': 'huggingface'
    },
    'PuLID_Model': {
        'filename': 'pulid_flux_v0.9.1.safetensors',
        'path': '/pulid',
        'repo_id': 'guozinan/PuLID',
        'file': 'pulid_flux_v0.9.1.safetensors',
        'source': 'huggingface'
    },
    'EVA_CLIP': {
        'filename': 'EVA02_CLIP_L_336_psz14_s6B.pt',
        'path': '/clip',
        'repo_id': 'QuanSun/EVA-CLIP',
        'file': 'EVA02_CLIP_L_336_psz14_s6B.pt',
        'source': 'huggingface'
    },
    'InstantID_1k3d68': {
        'filename': '1k3d68.onnx',
        'path': '/insightface/models/antelopev2',
        'repo_id': '12kaz/antelopev2',
        'file': 'antelopev2/1k3d68.onnx',
        'source': 'huggingface'
    },
    'InstantID_2d106det': {
        'filename': '2d106det.onnx',
        'path': '/insightface/models/antelopev2',
        'repo_id': '12kaz/antelopev2',
        'file': 'antelopev2/2d106det.onnx',
        'source': 'huggingface'
    },
    'InstantID_genderage': {
        'filename': 'genderage.onnx',
        'path': '/insightface/models/antelopev2',
        'repo_id': '12kaz/antelopev2',
        'file': 'antelopev2/genderage.onnx',
        'source': 'huggingface'
    },
    'InstantID_glintr100': {
        'filename': 'glintr100.onnx',
        'path': '/insightface/models/antelopev2',
        'repo_id': '12kaz/antelopev2',
        'file': 'antelopev2/glintr100.onnx',
        'source': 'huggingface'
    },
    'InstantID_scrfd': {
        'filename': 'scrfd_10g_bnkps.onnx',
        'path': '/insightface/models/antelopev2',
        'repo_id': '12kaz/antelopev2',
        'file': 'antelopev2/scrfd_10g_bnkps.onnx',
        'source': 'huggingface'
    },
    'Wan_T2V_1.3B': {
        'filename': 'wan2.1_t2v_1.3B_bf16.safetensors',
        'path': '/diffusion_models',
        'repo_id': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
        'file': 'split_files/diffusion_models/wan2.1_t2v_1.3B_bf16.safetensors',
        'source': 'huggingface'
    },
    'Wan_UMT5_XXL': {
        'filename': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        'path': '/text_encoders',
        'repo_id': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
        'file': 'split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        'source': 'huggingface'
    },
    'Wan_Clip_Vision': {
        'filename': 'clip_vision_h.safetensors',
        'path': '/clip_vision',
        'repo_id': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
        'file': 'split_files/clip_vision/clip_vision_h.safetensors',
        'source': 'huggingface'
    },
    'Wan_VAE': {
        'filename': 'wan_2.1_vae.safetensors',
        'path': '/vae',
        'repo_id': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
        'file': 'split_files/vae/wan_2.1_vae.safetensors',
        'source': 'huggingface'
    }
}

# Available checkpoints
CHECKPOINTS = {
    'FLUXFusion 6GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ3KM.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944957',
        'workflow': 'fluxfusion6GB4step.json',
        'source': 'civitai'
    },
    'FLUXFusion 8GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ50.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944799',
        'workflow': 'fluxfusion8GB4step.json',
        'source': 'civitai'
    },
    'FLUXFusion 10GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ6K.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '944704',
        'workflow': 'fluxfusion10GB4step.json',
        'source': 'civitai'
    },
    'FLUXFusion 12GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2GGUFQ80.gguf',
        'path': '/unet',
        'model_id': '630820',
        'version_id': '936976',
        'workflow': 'fluxfusion12GB4step.json',
        'source': 'civitai'
    },
    'FLUXFusion 24GB': {
        'filename': 'fluxFusionV24StepsGGUFNF4_V2Fp16.safetensors',
        'path': '/diffusion_models',
        'model_id': '630820',
        'version_id': '936309',
        'workflow': 'fluxfusion24GB4step.json',
        'source': 'civitai'
    },
    'FLUX.1 Dev': {
        'filename': 'flux1-dev.safetensors',
        'path': '/unet',
        'repo_id': 'black-forest-labs/FLUX.1-dev',
        'file': 'flux1-dev.safetensors',
        'workflow': 'FluxDev24GB.json',
        'source': 'huggingface'
    }
}

@dataclass
class DownloadConfig:
    chunk_size: int = 1024 * 1024  # 1MB chunks for progress tracking
    timeout: int = 7200            # 2 hours timeout for large files
    retry_attempts: int = 5
    retry_delay: int = 10
    verify_hash: bool = True

class AdvancedDownloadManager:
    def __init__(self):
        self.download_queue = queue.Queue()
        self.completed_downloads = []
        self.failed_downloads = []
        self.lock = threading.Lock()

    def _get_civitai_download_url(self, model_id, version_id):
        """Get direct download URL from CivitAI API"""
        try:
            api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
            logger.info(f"Fetching download URL from CivitAI API: {api_url}")
            
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            files = data.get('files', [])
            
            if not files:
                raise Exception(f"No files found for model version {version_id}")
            
            logger.info(f"Found {len(files)} files in API response")
            
            # Find the specific file we want
            for file in files:
                name = file.get('name', '')
                size = file.get('sizeKB', 0)
                logger.info(f"Checking file: {name} (Size: {size/1024:.2f} MB)")
                
                if name.endswith(('.safetensors', '.gguf')):
                    download_url = file.get('downloadUrl')
                    if download_url:
                        logger.info(f"Found matching file: {name}")
                        logger.info(f"Download URL: {download_url}")
                        return download_url
            
            raise Exception(f"No suitable file found in model version {version_id}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting CivitAI download URL: {e}")
            raise

    def download_file_with_progress(self, url, destination_path, headers=None, timeout=7200, progress_callback=None):
        """Download file with progress tracking and resume support"""
        try:
            # First check if we have a partial download
            downloaded_size = 0
            file_mode = 'ab'  # Always use append binary mode for resume support
            temp_path = f"{destination_path}.downloading"
            
            # Check for both temp and partial downloads
            if os.path.exists(temp_path):
                downloaded_size = os.path.getsize(temp_path)
                logger.info(f"Found existing partial download in temp file: {downloaded_size / (1024*1024):.2f} MB")
            elif os.path.exists(destination_path):
                downloaded_size = os.path.getsize(destination_path)
                # Move existing file to temp path for resuming
                shutil.move(destination_path, temp_path)
                logger.info(f"Moving existing file to temp path for resume: {downloaded_size / (1024*1024):.2f} MB")

            # Ensure directory exists
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            # Set up headers for range request
            if headers is None:
                headers = {}
            if downloaded_size > 0:
                headers['Range'] = f'bytes={downloaded_size}-'
                logger.info(f"Resuming download from byte {downloaded_size}")

            # First make a HEAD request to get the total size
            head_response = requests.head(url, headers=headers, timeout=30, verify=False)
            head_response.raise_for_status()
            expected_size = int(head_response.headers.get('content-length', 0))
            
            # If we already have a file, verify its size
            if os.path.exists(destination_path):
                current_size = os.path.getsize(destination_path)
                if current_size > 0 and current_size == expected_size:
                    logger.info(f"Destination file exists and matches expected size ({current_size} bytes)")
                    return True
                else:
                    logger.info(f"Destination file exists but size mismatch. Expected: {expected_size}, Got: {current_size}")
                    if os.path.exists(destination_path):
                        os.remove(destination_path)

            # Now start the actual download
            response = requests.get(url, headers=headers, stream=True, timeout=timeout, verify=False)
            response.raise_for_status()

            # Get actual total size from response
            if 'content-length' in response.headers:
                content_length = int(response.headers['content-length'])
                if response.status_code == 206:
                    total_size = downloaded_size + content_length
                else:
                    total_size = content_length
            else:
                total_size = expected_size
            
            if total_size == 0:
                raise Exception("Could not determine file size")
            
            logger.info(f"Total download size: {total_size / (1024*1024):.2f} MB")
            logger.info(f"Remaining to download: {(total_size - downloaded_size) / (1024*1024):.2f} MB")
            
            chunk_size = 8 * 1024 * 1024  # 8MB chunks
            with open(temp_path, file_mode, buffering=16*1024*1024) as f:
                start_time = time.time()
                last_log_time = start_time
                last_progress_time = start_time
                last_flush_size = downloaded_size
                initial_size = downloaded_size
                last_progress_update = start_time
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    
                    chunk_size = len(chunk)
                    f.write(chunk)
                    downloaded_size += chunk_size
                    
                    # Flush every 256MB
                    if downloaded_size - last_flush_size >= 256 * 1024 * 1024:
                        logger.debug(f"Forcing file flush at {downloaded_size / (1024*1024):.2f} MB")
                        f.flush()
                        os.fsync(f.fileno())
                        last_flush_size = downloaded_size
                    
                    current_time = time.time()
                    # Update console log every 30 seconds
                    if current_time - last_log_time >= 30:
                        progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                        current_speed = (downloaded_size - initial_size) / (current_time - start_time) / 1024 / 1024  # MB/s
                        logger.info(f"Download progress: {progress:.2f}% ({downloaded_size / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB) at {current_speed:.2f} MB/s")
                        last_log_time = current_time

                    # Update progress bar more frequently (every 0.5 seconds)
                    if progress_callback and (current_time - last_progress_update >= 0.5):
                        progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                        current_speed = (downloaded_size - initial_size) / (current_time - start_time) / 1024 / 1024  # MB/s
                        status = f"Downloaded: {int(downloaded_size / (1024*1024))} MB / {int(total_size / (1024*1024))} MB Speed: {current_speed:.2f} MB/s"
                        progress_callback(progress, status)
                        last_progress_update = current_time
                    
                    # Check for stalls
                    if current_time - last_progress_time > 600:  # 10 minutes
                        raise Exception("Download stalled - no progress for 10 minutes")
                    last_progress_time = current_time
            
            logger.info(f"Download completed successfully. Total size: {downloaded_size / (1024*1024):.2f} MB")
            
            # Final size validation
            if not os.path.exists(temp_path):
                raise Exception("File not found after download")
            
            final_size = os.path.getsize(temp_path)
            if total_size > 0 and final_size != total_size:
                raise Exception(f"File size mismatch. Expected: {total_size} bytes, Got: {final_size} bytes")
            
            # Rename temp file to final destination
            shutil.move(temp_path, destination_path)
            logger.info("File validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {str(e)}", exc_info=True)
            # Don't delete partial file on failure - it can be used for resume
            raise

    def download_large_file(self, url, output_path, headers=None):
        """Download large file with progress tracking"""
        try:
            # First get the file size
            logger.info(f"Getting file size from URL: {url}")
            logger.info(f"Using headers: {headers}")
            
            response = requests.head(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"Total file size: {total_size / (1024*1024*1024):.2f} GB")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            # Now start the download
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                downloaded = 0
                start_time = time.time()
                last_log_time = start_time
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_log_time >= 5:
                            progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                            speed = downloaded / (current_time - start_time) / 1024 / 1024  # MB/s
                            logger.info(f"Progress: {progress:.1f}% Speed: {speed:.1f} MB/s")
                            last_log_time = current_time
            
            return True
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

class SetupManager:
    def __init__(self):
        self.models_path = None
        self.base_dir = None
        self.hf_token = None
        self.civitai_token = None
        self.progress_callback = None
        self.env_file = '.env'
        self.validator = ComfyUIValidator()
        
        # Configure download settings
        self.download_config = DownloadConfig()
        self.hf_download_config = {
            'local_files_only': False,
            'resume_download': True,
            'force_download': False,
            'proxies': None,
            'local_dir_use_symlinks': False
        }
        
        # Speed smoothing settings
        self.speed_window_size = 20  # Increased window size for more smoothing
        self.speed_samples = []
        self.last_downloaded = 0
        self.last_update_time = time.time()
        self.min_update_interval = 0.5  # Minimum time between updates in seconds
        
        self.download_manager = AdvancedDownloadManager()

    def format_time(self, seconds):
        """Format time in seconds to a human-readable string"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.0f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def calculate_smooth_speed(self, current_downloaded):
        """Calculate smoothed download speed"""
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff >= self.min_update_interval:
            bytes_diff = current_downloaded - self.last_downloaded
            speed = bytes_diff / time_diff if time_diff > 0 else 0
            
            self.speed_samples.append(speed)
            if len(self.speed_samples) > self.speed_window_size:
                self.speed_samples.pop(0)
            
            self.last_downloaded = current_downloaded
            self.last_update_time = current_time
            
            return sum(self.speed_samples) / len(self.speed_samples)
        
        return sum(self.speed_samples) / len(self.speed_samples) if self.speed_samples else 0

    def verify_file_placement(self) -> Dict[str, bool]:
        """Verify that all required files are in their correct locations"""
        pass

    def load_env(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}
        try:
            if os.path.exists(self.env_file):
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip().strip('"').strip("'")
            else:
                # If .env doesn't exist, try to copy from .env_example
                if os.path.exists('.env_example'):
                    shutil.copy('.env_example', self.env_file)
                    logger.info("Created .env file from .env_example")
                    return self.load_env()  # Recursively load the newly created .env
                else:
                    logger.warning("No .env or .env_example file found")
        except Exception as e:
            logger.error(f"Error loading .env file: {str(e)}")
        return env_vars

    def save_env(self, env_vars: Dict[str, str]) -> bool:
        """Save environment variables to .env file"""
        try:
            # Add default values if not present
            defaults = {
                'COMMAND_PREFIX': '/'
            }
            
            for key, default_value in defaults.items():
                if key not in env_vars or not env_vars[key]:
                    env_vars[key] = default_value

            # Variables that should be quoted
            always_quote = {'fluxversion', 'BOT_SERVER', 'server_address', 'workflow', 'PULIDWORKFLOW'}

            # Write the .env file
            with open(self.env_file, 'w', encoding='utf-8') as f:
                # Write COMMAND_PREFIX first
                f.write(f"COMMAND_PREFIX={env_vars.pop('COMMAND_PREFIX', '/')}\n")
                
                # Write remaining variables
                for key, value in env_vars.items():
                    # Skip empty values
                    if value:
                        # Quote if in always_quote list
                        if key in always_quote:
                            if not value.startswith('"'):
                                value = f'"{value}"'
                        f.write(f"{key}={value}\n")
            logger.info("Successfully saved .env file")
            return True
        except Exception as e:
            logger.error(f"Error saving .env file: {str(e)}")
            return False

    def update_env_file(self, key: str, value: str) -> bool:
        """Update a single environment variable in the .env file"""
        try:
            env_vars = self.load_env()
            env_vars[key] = value
            self.save_env(env_vars)
            logger.info(f"Successfully updated {key} in .env file")
            return True
        except Exception as e:
            logger.error(f"Error updating {key} in .env file: {str(e)}")
            return False

    async def get_civitai_download_url(self, model_id: str, version_id: str, token: str) -> str:
        """Get the direct download URL from CivitAI API"""
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {token}'}
            async with session.get(
                f'https://civitai.com/api/v1/model-versions/{version_id}',
                headers=headers
            ) as response:
                data = await response.json()
                
                for file in data.get('files', []):
                    if file.get('primary', False):
                        return file.get('downloadUrl')
                raise Exception("No primary file found in model version")

    async def download_file(self, file_info: dict, output_path: str, token: str = None, source: str = 'huggingface'):
        """Download a file from HuggingFace or CivitAI"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Reset speed tracking for new download
            self.speed_samples = []
            self.last_downloaded = 0
            self.last_update_time = time.time()
            
            if source == 'huggingface':
                if not token:
                    raise ValueError("HuggingFace token is required")

                try:
                    # Get the direct download URL
                    url = hf_hub_url(
                        repo_id=file_info['repo_id'],
                        filename=file_info['file'],
                        repo_type="model"
                    )
                    
                    # Set up headers for HF download
                    headers = {
                        'Authorization': f'Bearer {token}',
                        'User-Agent': 'FluxComfyUI-Downloader/1.0'
                    }
                    
                    # First make a HEAD request to get file size
                    response = requests.head(url, headers=headers, allow_redirects=True)
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # Download with progress tracking
                    response = requests.get(url, headers=headers, stream=True)
                    response.raise_for_status()
                    
                    downloaded_size = 0
                    chunk_size = 8 * 1024 * 1024  # 8MB chunks
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if self.progress_callback and total_size > 0:
                                    progress = (downloaded_size / total_size) * 100
                                    speed = self.calculate_smooth_speed(downloaded_size)
                                    status = f"Downloading {file_info['filename']}: {downloaded_size/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB ({speed/(1024*1024):.1f} MB/s)"
                                    self.progress_callback(progress, status)
                                    
                                # Flush to disk periodically
                                if downloaded_size % (64 * 1024 * 1024) == 0:  # Every 64MB
                                    f.flush()
                                    os.fsync(f.fileno())
                    
                    logger.info(f"Successfully downloaded file to: {output_path}")
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    logger.info(f"Downloaded file size: {size_mb:.2f} MB")
                        
                except Exception as e:
                    logger.error(f"Download error: {str(e)}")
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    raise
                    
            elif source == 'civitai':
                if not token:
                    raise ValueError("CivitAI token is required")

                # Get the download URL from CivitAI API
                if 'model_id' not in file_info or 'version_id' not in file_info:
                    raise ValueError("Missing model_id or version_id for CivitAI download")
                    
                download_url = await self.get_civitai_download_url(
                    file_info['model_id'],
                    file_info['version_id'],
                    token
                )
                
                if not download_url:
                    raise ValueError("Failed to get download URL from CivitAI")

                # Set up headers for CivitAI
                headers = {
                    'Authorization': f'Bearer {token}',
                    'User-Agent': 'FluxComfyUI-Downloader/1.0'
                }

                # Define progress callback wrapper
                def progress_wrapper(progress, status):
                    if self.progress_callback:
                        status = f"Downloading {file_info['filename']}: {status}"
                        self.progress_callback(progress, status)

                # Use our improved download_file_with_progress for CivitAI downloads
                success = self.download_manager.download_file_with_progress(
                    url=download_url,
                    destination_path=output_path,
                    headers=headers,
                    timeout=7200,
                    progress_callback=progress_wrapper
                )

                if not success:
                    raise Exception("Download failed")
                    
                logger.info(f"Successfully downloaded file from CivitAI to: {output_path}")
                
            else:
                raise ValueError(f"Unsupported source: {source}")
                
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise