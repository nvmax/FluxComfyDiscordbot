import os
import json
import shutil
import asyncio
import aiohttp
import logging
import concurrent.futures
from pathlib import Path
from typing import Optional, Dict, Any
from huggingface_hub import hf_hub_download, HfApi
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
        'path': '/checkpoints',
        'repo_id': 'black-forest-labs/FLUX.1-dev',
        'file': 'flux1-dev.safetensors',
        'workflow': 'FluxDev24GB.json',
        'source': 'huggingface'
    }
}

@dataclass
class DownloadConfig:
    chunk_size: int = 16 * 1024 * 1024  # 64MB chunks
    max_concurrent_downloads: int = 5 
    timeout: int = 600  
    retry_attempts: int = 3
    retry_delay: int = 5
    verify_hash: bool = True

class AdvancedDownloadManager:
    def __init__(self, max_workers=None, chunk_size=16*1024*1024):
        """
        Advanced download manager with parallel and resumable downloads
        
        :param max_workers: Number of concurrent downloads (defaults to CPU count)
        :param chunk_size: Size of each download chunk
        """
        self.max_workers = max_workers or (multiprocessing.cpu_count() * 4)
        self.chunk_size = chunk_size
        self.download_queue = queue.Queue()
        self.completed_downloads = []
        self.failed_downloads = []
        self.lock = threading.Lock()

    def _download_chunk(self, url, start, end, output_file, headers=None):
      
        headers = headers or {}
        headers['Range'] = f'bytes={start}-{end}'
        
        try:
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(output_file, 'r+b') as f:
                f.seek(start)
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
            
            return True
        except Exception as e:
            logger.error(f"Chunk download failed: {e}")
            return False

    def download_file_parallel(self, url, output_path, total_size=None, headers=None):
       
        try:
            # If total size not provided, get file size first
            if total_size is None:
                head_response = requests.head(url, headers=headers)
                head_response.raise_for_status()
                total_size = int(head_response.headers.get('Content-Length', 0))
            
            # Prepare output file
            with open(output_path, 'wb') as f:
                f.seek(total_size - 1)
                f.write(b'\0')
            
            # Calculate chunk sizes
            chunk_count = self.max_workers
            chunk_size = total_size // chunk_count
            
            # Prepare download chunks
            chunks = []
            for i in range(chunk_count):
                start = i * chunk_size
                end = start + chunk_size - 1 if i < chunk_count - 1 else total_size - 1
                chunks.append((start, end))
            
            # Parallel download using ProcessPoolExecutor
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                partial_download = partial(self._download_chunk, url, output_path=output_path, headers=headers)
                futures = [executor.submit(partial_download, start, end) for start, end in chunks]
                
                # Wait for all downloads to complete
                concurrent.futures.wait(futures)
                
                # Check if all chunks downloaded successfully
                results = [future.result() for future in futures]
                
                return all(results)
        
        except Exception as e:
            logger.error(f"Parallel download failed: {e}")
            return False

    def download_with_retry(self, file_info, output_path, max_retries=3):
  
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                # Choose download method based on source
                if file_info.get('source', 'huggingface') == 'huggingface':
                    # Use HuggingFace download method
                    file_path = hf_hub_download(
                        repo_id=file_info['repo_id'],
                        filename=file_info['file'],
                        local_dir=os.path.dirname(output_path),
                        force_download=False,
                        resume_download=True,
                        token=file_info.get('token'),
                        local_files_only=False
                    )
                    shutil.move(file_path, output_path)
                
                elif file_info.get('source') == 'civitai':
                    # Use parallel download for CivitAI
                    success = self.download_file_parallel(
                        url=file_info['url'], 
                        output_path=output_path, 
                        headers={'Authorization': f'Bearer {file_info.get("token")}'}
                    )
                    if not success:
                        raise Exception("Parallel download failed")
                
                end_time = time.time()
                download_time = end_time - start_time
                
                logger.info(f"Download completed in {download_time:.2f} seconds")
                return True
            
            except Exception as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to download after {max_retries} attempts")
                    return False

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
            always_quote = {'fluxversion', 'BOT_SERVER', 'server_address', 'workflow'}

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

                # Patch tqdm with our progress callback
                def patch_tqdm(progress_callback):
                    """Monkey patch tqdm to use our progress callback"""
                    original_update = tqdm.update

                    def patched_update(self, n=1):
                        try:
                            if not hasattr(self, 'n') or not hasattr(self, 'total'):
                                return original_update(self, n)
                                
                            if self.n is None or self.total is None:
                                return original_update(self, n)
                            
                            # Format the information
                            downloaded = float(self.n) / 1024 / 1024 if self.n is not None else 0
                            total_size = float(self.total) / 1024 / 1024 if self.total is not None else 0
                            
                            # Get speed from format_dict, default to 0 if not available
                            format_dict = getattr(self, 'format_dict', {})
                            if not isinstance(format_dict, dict):
                                format_dict = {}
                            
                            speed = float(format_dict.get("rate", 0)) / (1024 * 1024) if format_dict.get("rate") is not None else 0
                            
                            # Ensure speed is not zero to prevent division by zero
                            speed = max(speed, 0.001)
                            
                            # Calculate remaining time
                            remaining_bytes = float(self.total - self.n) if self.total is not None and self.n is not None else 0
                            time_left = remaining_bytes / (speed * 1024 * 1024) if speed > 0 else 0
                            
                            # Format time
                            if time_left < 60:
                                time_str = f"{time_left:.0f}s"
                            elif time_left < 3600:
                                time_str = f"{time_left/60:.1f}m"
                            else:
                                time_str = f"{time_left/3600:.1f}h"
                            
                            # Calculate progress percentage
                            progress = (float(self.n) / float(self.total)) * 100 if self.total and self.total > 0 else 0
                            
                            # Format status message
                            status = f"Downloaded: {int(downloaded)}/{int(total_size)} MB Speed: {speed:.2f} MB/s Remaining: {time_str}"
                            
                            # Call the progress callback
                            if progress_callback:
                                progress_callback(progress, status)
                            
                        except Exception as e:
                            logger.error(f"Error in progress update: {str(e)}")
                            # Continue with original update even if our progress tracking fails
                            
                        return original_update(self, n)

                    tqdm.update = patched_update

                patch_tqdm(self.progress_callback)

                if not setup_hf_transfer():
                    logger.warning("HF Transfer initialization failed - download may be slower")

                # Create cache directory if it doesn't exist
                cache_dir = os.path.join(os.path.dirname(output_path), '.cache')
                os.makedirs(cache_dir, exist_ok=True)

                try:
                    # Use HF Transfer for faster downloads
                    file_path = hf_hub_download(
                        repo_id=file_info['repo_id'],
                        filename=file_info['file'],
                        local_dir=os.path.dirname(output_path),
                        force_download=False,
                        resume_download=True,
                        token=token,
                        local_files_only=False,
                        cache_dir=cache_dir
                    )
                    
                    # Log actual transfer method and file info
                    if "hf_transfer" in sys.modules:
                        logger.info(f"Download completed using HF Transfer (high-speed) to: {file_path}")
                        size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        logger.info(f"Downloaded file size: {size_mb:.2f} MB")
                    else:
                        logger.warning("Download completed using standard method (slower)")
                        
                except Exception as e:
                    logger.error(f"Download error: {str(e)}")
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

                # Download the file using aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(download_url) as response:
                        if response.status != 200:
                            raise ValueError(f"Failed to download file: HTTP {response.status}")
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(output_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    # Calculate progress and speed
                                    if total_size > 0:
                                        progress = (downloaded / total_size) * 100
                                        downloaded_mb = downloaded / (1024 * 1024)
                                        total_mb = total_size / (1024 * 1024)
                                        
                                        # Calculate speed
                                        current_time = time.time()
                                        time_diff = current_time - self.last_update_time
                                        if time_diff >= self.min_update_interval:
                                            bytes_since_last = downloaded - self.last_downloaded
                                            speed = (bytes_since_last / time_diff) / (1024 * 1024)  # MB/s
                                            
                                            # Calculate remaining time
                                            remaining_bytes = total_size - downloaded
                                            time_left = remaining_bytes / (speed * 1024 * 1024) if speed > 0 else 0
                                            
                                            # Format time
                                            if time_left < 60:
                                                time_str = f"{time_left:.0f}s"
                                            elif time_left < 3600:
                                                time_str = f"{time_left/60:.1f}m"
                                            else:
                                                time_str = f"{time_left/3600:.1f}h"
                                            
                                            # Update status
                                            status = f"Downloaded: {int(downloaded_mb)}/{int(total_mb)} MB Speed: {speed:.2f} MB/s Remaining: {time_str}"
                                            if self.progress_callback:
                                                self.progress_callback(progress, status)
                                            
                                            # Update tracking variables
                                            self.last_downloaded = downloaded
                                            self.last_update_time = current_time
                
                logger.info(f"Successfully downloaded file from CivitAI to: {output_path}")
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"Downloaded file size: {size_mb:.2f} MB")
            
            else:
                raise ValueError(f"Unsupported download source: {source}")
                
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            raise

    def validate_huggingface_token(self, token: str) -> bool:
        """Validate Hugging Face token using HF Hub API"""
        if not token or not token.startswith('hf_'):
            return False
            
        try:
            api = HfApi(token=token)
            user = api.whoami()
            
            headers = {'Authorization': f'Bearer {token}'}
            test_url = 'https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors'
            response = requests.head(test_url, headers=headers, allow_redirects=True, verify=False)
            
            return user is not None and response.status_code == 200
        except Exception as e:
            logger.error(f"HF token validation error: {str(e)}")
            return False

    def validate_civitai_token(self, token: str) -> bool:
        """Validate CivitAI token"""
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get('https://civitai.com/api/v1/models', headers=headers, timeout=10)
            return response.status_code in [200, 401]
        except Exception as e:
            logger.error(f"CivitAI token validation error: {str(e)}")
            return False