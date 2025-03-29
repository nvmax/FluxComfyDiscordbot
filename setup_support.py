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
import zipfile

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

# Custom Nodes Repositories
CUSTOM_NODES = {
    'comfyui-manager': {
        'repo_url': 'https://github.com/ltdrdata/ComfyUI-Manager',
        'destination': 'comfyui-manager',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'comfyui-gguf': {
        'repo_url': 'https://github.com/city96/ComfyUI-GGUF.git',
        'destination': 'ComfyUI-GGUF',
        'has_requirements': True,
        'skip_requirements': False,  # Skip requirements that need complex build tools
    },
    'rgthree-comfy': {
        'repo_url': 'https://github.com/rgthree/rgthree-comfy.git',
        'destination': 'rgthree-comfy',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'was-node-suite': {
        'repo_url': 'https://github.com/WASasquatch/was-node-suite-comfyui.git',
        'destination': 'was-node-suite-comfyui',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'video-helper-suite': {
        'repo_url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git',
        'destination': 'ComfyUI-VideoHelperSuite',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'tea-cache': {
        'repo_url': 'https://github.com/welltop-cn/ComfyUI-TeaCache.git',
        'destination': 'ComfyUI-TeaCache',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'pulid-flux': {
        'repo_url': 'https://github.com/lldacing/ComfyUI_PuLID_Flux_ll.git',
        'destination': 'ComfyUI_PuLID_Flux_ll',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'patches-ll': {
        'repo_url': 'https://github.com/lldacing/ComfyUI_Patches_ll.git',
        'destination': 'ComfyUI_Patches_ll',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'neural-media': {
        'repo_url': 'https://github.com/YarvixPA/ComfyUI-NeuralMedia.git',
        'destination': 'ComfyUI-NeuralMedia',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'crystools': {
        'repo_url': 'https://github.com/crystian/ComfyUI-Crystools.git',
        'destination': 'ComfyUI-Crystools',
        'has_requirements': True,
        'skip_requirements': False,
    },
    'ppm': {
        'repo_url': 'https://github.com/pamparamm/ComfyUI-ppm.git',
        'destination': 'ComfyUI-ppm',
        'has_requirements': False,
        'skip_requirements': False,
    },
    'mikey-nodes': {
        'repo_url': 'https://github.com/bash-j/mikey_nodes.git',
        'destination': 'mikey_nodes',
        'has_requirements': False,
        'skip_requirements': False,
    },
    'advanced-reflux-control': {
        'repo_url': 'https://github.com/kaibioinfo/ComfyUI_AdvancedRefluxControl.git',
        'destination': 'ComfyUI_AdvancedRefluxControl',
        'has_requirements': False,
        'skip_requirements': False,
    },
    'comfyroll-custom-nodes': {
        'repo_url': 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git',
        'destination': 'ComfyUI_Comfyroll_CustomNodes',
        'has_requirements': False,
        'skip_requirements': False,
    },
    'alekpet-custom-nodes': {
        'repo_url': 'https://github.com/AlekPet/ComfyUI_Custom_Nodes_AlekPet.git',
        'destination': 'ComfyUI_Custom_Nodes_AlekPet',
        'has_requirements': False,
        'skip_requirements': False,
    },
    'mx-toolkit': {
        'repo_url': 'https://github.com/Smirnov75/ComfyUI-mxToolkit',
        'destination': 'ComfyUI-mxToolkit',
        'has_requirements': False,
        'skip_requirements': True,
    },
    'ultimate-sd-upscale': {
        'repo_url': 'https://github.com/ssitu/ComfyUI_UltimateSDUpscale',
        'destination': 'ComfyUI_UltimateSDUpscale',
        'has_requirements': False,
        'skip_requirements': True,
    },
    'various-utils': {
        'repo_url': 'https://github.com/jamesWalker55/comfyui-various',
        'destination': 'comfyui-various',
        'has_requirements': False,
        'skip_requirements': True,
    },
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
                    
                    # Flush to disk periodically
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

class PreSetupManager:
    def __init__(self):
        self.status_callback = None
        self.progress_callback = None
        self.comfyui_dir = None
        self.python_exe = None  # Will be determined when needed
        
        # Set default paths - these will be updated when comfyui_dir is set
        self.embedded_python_exe_paths = []
        self.embedded_python_exe = None
        self.custom_nodes_path = None
        
    def set_comfyui_dir(self, comfyui_dir):
        """Set the ComfyUI base directory"""
        if not comfyui_dir:
            raise ValueError("ComfyUI directory must be specified")
            
        # This is the base directory selected by the user
        base_dir = Path(comfyui_dir)
        
        # Set the correct path structure: base_dir/ComfyUI/custom_nodes
        self.comfyui_dir = base_dir / "ComfyUI"
        self.custom_nodes_path = self.comfyui_dir / "custom_nodes"
        
        # Create directories if they don't exist
        os.makedirs(self.comfyui_dir, exist_ok=True)
        os.makedirs(self.custom_nodes_path, exist_ok=True)
        
        # Set embedded Python paths based on user directory
        self.embedded_python_exe_paths = [
            os.path.join(str(base_dir), "python_embeded", "python.exe"),  # User directory/python_embeded
            os.path.join(os.getcwd(), "python_embeded", "python.exe"),    # Current dir/python_embeded
            "./python_embeded/python.exe",                                # Relative path
            os.path.join(os.getcwd(), "required_files", "Comfyui files", "python_embeded", "python.exe")  # Original path
        ]
        
        # Find the embedded Python
        for path in self.embedded_python_exe_paths:
            if os.path.exists(path):
                self.embedded_python_exe = path
                self.update_status(f"Found embedded Python at: {path}")
                break
                
        if not self.embedded_python_exe:
            self.update_status("WARNING: Could not find embedded Python, trying fallback approach")
        
        self.update_status(f"Using base directory: {base_dir}")
        self.update_status(f"ComfyUI directory set to: {self.comfyui_dir}")
        self.update_status(f"Custom nodes will be installed to: {self.custom_nodes_path}")
        return True
        
    def update_status(self, message):
        """Update status message"""
        if self.status_callback:
            self.status_callback(message)
        logger.info(message)
            
    def update_progress(self, value):
        """Update progress bar"""
        if self.progress_callback:
            self.progress_callback(value)
            
    def clone_repository(self, repo_url, destination):
        """Clone a git repository to the specified destination"""
        try:
            import git
            self.update_status(f"Cloning {repo_url} to {destination}...")
            
            # Check if the directory already exists
            if os.path.exists(destination):
                self.update_status(f"Repository already exists at {destination}, updating...")
                repo = git.Repo(destination)
                origin = repo.remotes.origin
                origin.pull()
                return True
                
            # Clone the repository
            git.Repo.clone_from(repo_url, destination)
            self.update_status(f"Successfully cloned {repo_url}")
            return True
        except Exception as e:
            self.update_status(f"Error cloning repository {repo_url}: {str(e)}")
            return False
            
    def install_requirements(self, requirements_path, node_name=None):
        """Install requirements from a requirements.txt file"""
        try:
            import subprocess
            import sys
            
            if not os.path.exists(requirements_path):
                self.update_status(f"Requirements file not found at {requirements_path}")
                return False
            
            # Special handling for ComfyUI-GGUF - directly use the command that works
            if node_name == 'comfyui-gguf' or 'ComfyUI-GGUF' in requirements_path:
                self.update_status(f"Attempting direct installation for ComfyUI-GGUF...")
                
                base_dir = os.path.dirname(os.path.dirname(self.custom_nodes_path))
                direct_python_path = os.path.join(str(base_dir), "python_embeded", "python.exe")
                
                self.update_status(f"Checking for user path Python at: {direct_python_path}")
                if os.path.exists(direct_python_path):
                    cmd = [direct_python_path, "-s", "-m", "pip", "install", "-r", requirements_path]
                    self.update_status(f"Running: {' '.join(cmd)}")
                    
                    try:
                        process = subprocess.Popen(
                            cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        stdout, stderr = process.communicate()
                        
                        if process.returncode == 0:
                            self.update_status("Successfully installed ComfyUI-GGUF requirements")
                            return True
                        else:
                            self.update_status(f"Warning: Error installing GGUF requirements: {stderr}")
                    except Exception as e:
                        self.update_status(f"Error with user path Python: {str(e)}")
                else:
                    self.update_status(f"User path Python not found at: {direct_python_path}")
                
                # Try all other python paths
                for python_path in self.embedded_python_exe_paths:
                    if os.path.exists(python_path):
                        cmd = [python_path, "-s", "-m", "pip", "install", "-r", requirements_path]
                        self.update_status(f"Trying with alternate path: {' '.join(cmd)}")
                        
                        try:
                            process = subprocess.Popen(
                                cmd, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = process.communicate()
                            
                            if process.returncode == 0:
                                self.update_status("Successfully installed ComfyUI-GGUF requirements")
                                return True
                        except Exception as e:
                            self.update_status(f"Error with alternate path: {str(e)}")
                
                # For ComfyUI-GGUF, continue even if installation fails
                self.update_status("GGUF dependencies installation had issues - ComfyUI Manager will handle them later")
                return True
                
            # For other packages, try to use embedded Python if available
            if self.embedded_python_exe:
                # First check and install Cython if needed
                self.update_status("Checking for Cython in embedded Python...")
                try:
                    check_cmd = [self.embedded_python_exe, "-c", "import Cython; print('Cython already installed')"]
                    process = subprocess.Popen(
                        check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        self.update_status("Cython not found, installing it first...")
                        install_cython_cmd = [self.embedded_python_exe, "-s", "-m", "pip", "install", "Cython"]
                        self.update_status(f"Running: {' '.join(install_cython_cmd)}")
                        
                        process = subprocess.Popen(
                            install_cython_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        
                        if process.returncode == 0:
                            self.update_status("Successfully installed Cython")
                        else:
                            self.update_status(f"Warning: Failed to install Cython: {stderr}")
                    else:
                        self.update_status("Cython is already installed")
                except Exception as e:
                    self.update_status(f"Error checking/installing Cython: {str(e)}")
                
                # Check and install wheel if needed
                self.update_status("Checking for wheel in embedded Python...")
                try:
                    check_cmd = [self.embedded_python_exe, "-c", "import wheel; print('wheel already installed')"]
                    process = subprocess.Popen(
                        check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        self.update_status("wheel not found, installing it first...")
                        install_wheel_cmd = [self.embedded_python_exe, "-s", "-m", "pip", "install", "wheel"]
                        self.update_status(f"Running: {' '.join(install_wheel_cmd)}")
                        
                        process = subprocess.Popen(
                            install_wheel_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        
                        if process.returncode == 0:
                            self.update_status("Successfully installed wheel")
                        else:
                            self.update_status(f"Warning: Failed to install wheel: {stderr}")
                    else:
                        self.update_status("wheel is already installed")
                except Exception as e:
                    self.update_status(f"Error checking/installing wheel: {str(e)}")
                
                # Check and install filterpy if needed - it has a circular dependency issue
                self.update_status("Checking for filterpy...")
                try:
                    check_cmd = [self.embedded_python_exe, "-c", "import filterpy; print('filterpy already installed')"]
                    process = subprocess.Popen(
                        check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        self.update_status("Installing filterpy...")
                        
                        # Use the command that works - install directly from GitHub
                        install_cmd = [self.embedded_python_exe, "-m", "pip", "install", "git+https://github.com/rodjjo/filterpy.git"]
                        
                        result = subprocess.run(
                            install_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        if result.returncode == 0:
                            self.update_status("Successfully installed filterpy")
                        else:
                            self.update_status("Warning: Could not install filterpy")
                            self.update_status("Continuing with setup, but some nodes may not work correctly")
                    else:
                        self.update_status("filterpy is already installed")
                except Exception as e:
                    self.update_status(f"Error checking/installing filterpy: {str(e)}")
                
                # Now install requirements
                node_folder = os.path.basename(os.path.dirname(requirements_path))
                self.update_status(f"Installing requirements for {node_folder}...")
                
                process = subprocess.Popen(
                    [self.embedded_python_exe, "-s", "-m", "pip", "install", "-r", requirements_path], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    self.update_status("Warning: Error installing requirements")
                    self.update_status("Falling back to system Python...")
                else:
                    self.update_status("Requirements installed successfully with embedded Python")
                    return True
            else:
                self.update_status("Embedded Python not found, using system Python instead")
            
            # Fall back to system Python if embedded Python failed or doesn't exist
            # Get Python executable if not set yet
            if not self.python_exe:
                # Use system Python executable
                self.python_exe = sys.executable
                
                if not self.python_exe:
                    # As a fallback, try common commands
                    python_commands = ["python", "py"]
                    for cmd in python_commands:
                        try:
                            # Check if the command exists
                            result = subprocess.run([cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            if result.returncode == 0:
                                self.python_exe = cmd
                                break
                        except:
                            continue
            
            if not self.python_exe:
                self.update_status("Error: Could not find Python executable")
                return False
                
            self.update_status(f"Installing requirements from {requirements_path} using {self.python_exe}...")
            
            # Try first with prefer-binary flag to use wheels when possible
            process = subprocess.Popen(
                [self.python_exe, "-m", "pip", "install", "-r", requirements_path, "--prefer-binary"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                self.update_status(f"Warning: Error during standard installation: {stderr}")
                self.update_status("Attempting to install packages individually...")
                
                # Read requirements file and install packages one by one
                with open(requirements_path, 'r') as f:
                    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
                install_success = True
                for req in requirements:
                    try:
                        # Skip problematic packages we already tried to install
                        if 'sentencepiece' in req.lower():
                            continue
                            
                        self.update_status(f"Installing {req}...")
                        process = subprocess.Popen(
                            [self.python_exe, "-m", "pip", "install", req, "--prefer-binary"], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        
                        if process.returncode != 0:
                            self.update_status(f"Warning: Could not install {req}: {stderr}")
                            install_success = False
                    except Exception as e:
                        self.update_status(f"Warning: Error installing {req}: {str(e)}")
                        install_success = False
                
                if not install_success:
                    self.update_status("Some packages could not be installed, but continuing with setup")
                return True  # Continue even with some failures
                
            self.update_status("Requirements installed successfully")
            return True
        except Exception as e:
            self.update_status(f"Error installing requirements: {str(e)}")
            return False
            
    def run_presetup(self):
        """Run the pre-setup process to install all custom nodes"""
        if not self.comfyui_dir:
            self.update_status("ComfyUI directory not set. Please specify a valid directory.")
            return False
            
        if not os.path.exists(self.comfyui_dir):
            self.update_status(f"ComfyUI directory not found at {self.comfyui_dir}")
            return False
            
        # Extract libs-include.zip first
        self.update_status("Extracting required libraries...")
        if not extract_libs_include(os.path.dirname(self.comfyui_dir)):
            self.update_status("Failed to extract required libraries. Setup cannot continue.")
            return False
        self.update_status("Successfully extracted required libraries")
        
        # Ensure GitPython is installed
        self.update_status("Checking if GitPython is installed...")
        try:
            import git
            self.update_status("GitPython is installed, continuing with setup")
        except ImportError:
            self.update_status("GitPython is not installed. Please install it first.")
            return False
            
        # Check for embedded Python
        for path in self.embedded_python_exe_paths:
            self.update_status(f"Checking for embedded Python at: {path}")
            if os.path.exists(path):
                self.embedded_python_exe = path
                self.update_status(f"Found embedded Python at: {path}")
                break
                
        if not self.embedded_python_exe:
            self.update_status(" WARNING: Embedded Python not found at any of these locations:")
            for path in self.embedded_python_exe_paths:
                self.update_status(f"  - {path}")
            self.update_status("Some extensions like GGUF may not install correctly without embedded Python")
            
        total_nodes = len(CUSTOM_NODES)
        completed = 0
        
        # Clone ComfyUI Manager first
        manager_info = CUSTOM_NODES['comfyui-manager']
        manager_dest = os.path.join(self.custom_nodes_path, manager_info['destination'])
        
        self.update_status("Installing ComfyUI Manager (required for other extensions)...")
        success = self.clone_repository(manager_info['repo_url'], manager_dest)
        
        if success and manager_info['has_requirements'] and not manager_info['skip_requirements']:
            requirements_path = os.path.join(manager_dest, "requirements.txt")
            self.install_requirements(requirements_path, 'comfyui-manager')
            
        completed += 1
        self.update_progress(completed / total_nodes * 100)
            
        # Install other custom nodes
        for name, node_info in CUSTOM_NODES.items():
            if name == 'comfyui-manager':  # Skip the manager as it's already installed
                continue
                
            repo_url = node_info['repo_url']
            destination = os.path.join(self.custom_nodes_path, node_info['destination'])
            
            self.update_status(f"Installing {name}...")
            success = self.clone_repository(repo_url, destination)
            
            if success and node_info['has_requirements']:
                if name == 'comfyui-gguf':
                    # For ComfyUI-GGUF, always try to install requirements using the embedded Python
                    requirements_path = os.path.join(destination, "requirements.txt")
                    self.install_requirements(requirements_path, name)
                elif node_info['skip_requirements']:
                    self.update_status(f"Skipping requirements for {name} due to build dependencies")
                    self.update_status(f"Note: You may need to manually install requirements for {name} later")
                else:
                    requirements_path = os.path.join(destination, "requirements.txt")
                    self.install_requirements(requirements_path, name)
                
            completed += 1
            self.update_progress(completed / total_nodes * 100)
            
        self.update_status("Pre-setup completed. Please start ComfyUI to complete the installation.")
        self.update_status("Note: ComfyUI Manager will handle additional dependencies on first startup.")
        
        # Added note about GGUF
        if 'comfyui-gguf' in CUSTOM_NODES:
            self.update_status("")
            self.update_status(" NOTE: If there were issues with GGUF extension installation, you may need to:")
            self.update_status("1. Install CMake manually if prompted by ComfyUI Manager")
            self.update_status("2. Or try: pip install cmake sentencepiece protobuf")
            
        return True

class SetupManager:
    def __init__(self):
        self.models_path = None
        self.base_dir = None
        self.hf_token = None
        self.civitai_token = None
        self.progress_callback = None
        self.env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        self.env_vars = {}  # Initialize empty dictionary for env vars
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
        
        # Load environment variables on initialization
        self.load_env()

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

    def load_env(self):
        """Load environment variables from .env file"""
        env_vars = {}
        try:
            if os.path.exists(self.env_file):
                logger.info(f"Loading environment variables from {self.env_file}")
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                # Remove quotes if present
                                if value.startswith('"') and value.endswith('"'):
                                    value = value[1:-1]
                                elif value.startswith("'") and value.endswith("'"):
                                    value = value[1:-1]
                                
                                # Store variables with original names
                                env_vars[key] = value
                                logger.debug(f"Loaded env var: {key}={value}")
                            
                # Store environment variables
                self.env_vars = env_vars
                logger.info(f"Loaded {len(env_vars)} environment variables")
                            
                # Load key variables into instance attributes
                self.hf_token = env_vars.get('HUGGINGFACE_TOKEN')
                self.civitai_token = env_vars.get('CIVITAI_API_TOKEN')
                self.base_dir = env_vars.get('COMFYUI_MODELS_PATH')
                
                return self.env_vars
            else:
                logger.warning(f"Environment file {self.env_file} not found")
        except Exception as e:
            logger.error(f"Error loading .env file: {str(e)}", exc_info=True)
        
        # Return empty dict if file doesn't exist or error occurred
        self.env_vars = env_vars
        return self.env_vars

    def save_env(self, env_vars: Dict[str, str]) -> bool:
        """Save environment variables to .env file"""
        try:
            # Variables that should be quoted
            always_quote = {'fluxversion', 'BOT_SERVER', 'server_address', 'workflow', 'PULIDWORKFLOW'}

            # Write the .env file
            with open(self.env_file, 'w', encoding='utf-8') as f:
                # Write variables in a specific order
                order = [
                    'COMMAND_PREFIX',
                    'HUGGINGFACE_TOKEN',
                    'CIVITAI_API_TOKEN',
                    'DISCORD_TOKEN',
                    'COMFYUI_MODELS_PATH',
                    'BOT_SERVER',
                    'server_address',
                    'ALLOWED_SERVERS',
                    'CHANNEL_IDS',
                    'BOT_MANAGER_ROLE_ID',
                    'fluxversion',
                    'LORA_FOLDER_PATH',
                    'ENABLE_PROMPT_ENHANCEMENT',
                    'AI_PROVIDER',
                    'LMSTUDIO_HOST',
                    'LMSTUDIO_PORT',
                    'XAI_MODEL',
                    'OPENAI_MODEL',
                    'EMBEDDING_MODEL',
                    'GEMINI_API_KEY',
                    'PULIDWORKFLOW'
                ]
                
                # Write ordered variables first
                for key in order:
                    if key in env_vars and env_vars[key]:
                        value = env_vars[key]
                        if key in always_quote and not (value.startswith('"') and value.endswith('"')):
                            value = f'"{value}"'
                        f.write(f"{key}={value}\n")
                        
                # Write any remaining variables that weren't in the order list
                for key, value in env_vars.items():
                    if key not in order and value:
                        if key in always_quote and not (value.startswith('"') and value.endswith('"')):
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

    def validate_civitai_token(self, token: str) -> bool:
        """Validate CivitAI token by making a test API call"""
        try:
            response = requests.get(
                'https://civitai.com/api/v1/models?limit=1',
                headers={'Authorization': f'Bearer {token}'},
                verify=False
            )
            if response.status_code == 200:
                return True
            logger.error(f"Failed to validate CivitAI token: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Error validating CivitAI token: {str(e)}")
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

def extract_libs_include(base_dir):
    """
    Extracts libs-include.zip into the python_embeded directory.

    Args:
        base_dir (str): The base directory of the project.
    """
    zip_filename = "libs-include.zip"
    # Source zip is in the project's required_files directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    source_zip_path = os.path.join(project_dir, "required_files", zip_filename)
    target_extract_path = os.path.join(base_dir, "python_embeded")

    logging.info(f"Attempting to extract '{zip_filename}'...")
    logging.info(f"Source: {source_zip_path}")
    logging.info(f"Target: {target_extract_path}")

    if not os.path.exists(source_zip_path):
        logging.error(f"Error: Source zip file not found at {source_zip_path}")
        return False

    os.makedirs(target_extract_path, exist_ok=True)

    try:
        with zipfile.ZipFile(source_zip_path, 'r') as zip_ref:
            # Log the contents of the zip file
            contents = zip_ref.namelist()
            logging.info(f"Zip file contains {len(contents)} files")
            for item in contents:
                logging.info(f"Extracting: {item}")
            
            # Extract all files
            zip_ref.extractall(target_extract_path)

            # Verify extraction
            extracted_files = []
            for root, dirs, files in os.walk(target_extract_path):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), target_extract_path)
                    extracted_files.append(rel_path)
            
            logging.info(f"Found {len(extracted_files)} files in target directory")
            for file in extracted_files:
                logging.info(f"Extracted file: {file}")

            if len(extracted_files) == 0:
                logging.error("No files were extracted!")
                return False

        logging.info(f"Successfully extracted '{zip_filename}' to {target_extract_path}")
        return True
    except zipfile.BadZipFile:
        logging.error(f"Error: Failed to extract '{zip_filename}'. The file might be corrupted.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during extraction: {e}")
        return False