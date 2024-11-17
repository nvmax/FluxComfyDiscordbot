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
from huggingface_hub import HfApi
import shutil
from comfyui_validator import ComfyUIValidator

# Configure root logger
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        'path': '/checkpoints',
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

class SetupManager:
    def __init__(self):
        self.models_path = None
        self.base_dir = None
        self.hf_token = None
        self.civitai_token = None
        self.progress_callback = None
        self.env_file = '.env'
        self.validator = ComfyUIValidator()

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
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get('https://civitai.com/api/v1/models', headers=headers, timeout=10)
            return response.status_code in [200, 401]
        except Exception as e:
            logger.error(f"CivitAI token validation error: {str(e)}")
            return False

    def get_civitai_download_url(self, model_id: str, version_id: str, token: str) -> str:
        """Get the direct download URL from CivitAI API"""
        headers = {'Authorization': f'Bearer {token}'}
        
        try:
            response = requests.get(
                f'https://civitai.com/api/v1/model-versions/{version_id}',
                headers=headers
            )
            response.raise_for_status()
            version_data = response.json()
            
            for file in version_data.get('files', []):
                if file.get('primary', False):
                    return file.get('downloadUrl')
            raise Exception("No primary file found in model version")
            
        except Exception as e:
            logger.error(f"Error getting CivitAI download URL: {str(e)}")
            raise

    def download_file(self, file_info: dict, output_path: str, token: str = None, source: str = 'huggingface'):
        """Download file with progress tracking and size verification"""
        try:
            # Skip local files - they should be handled by copy operation
            if source == 'local':
                return
                
            logger.info(f"Starting download for source: {source}")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            if source == 'huggingface':
                url = f"https://huggingface.co/{file_info['repo_id']}/resolve/main/{file_info['file']}"
                headers = {"Authorization": f"Bearer {token}"} if token else {}
            else:  # civitai
                url = self.get_civitai_download_url(
                    model_id=file_info['model_id'],
                    version_id=file_info['version_id'],
                    token=token
                )
                headers = {'Authorization': f'Bearer {token}'} if token else {}
            
            # First make a HEAD request to get the expected file size
            head_response = requests.head(url, headers=headers, verify=False)
            head_response.raise_for_status()
            expected_size = int(head_response.headers.get('content-length', 0))
            logger.info(f"Expected file size: {expected_size} bytes")
            
            # Check if file already exists and verify its size
            if os.path.exists(output_path):
                current_size = os.path.getsize(output_path)
                if current_size == expected_size:
                    logger.info(f"File already exists with correct size ({current_size} bytes), skipping download")
                    if self.progress_callback:
                        self.progress_callback(100)
                    return
                else:
                    logger.warning(f"File exists but size mismatch (expected: {expected_size}, got: {current_size}), redownloading")
                    os.remove(output_path)
            
            response = requests.get(url, headers=headers, stream=True, verify=False)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            if total_size != expected_size:
                raise ValueError(f"Download size mismatch (HEAD: {expected_size}, GET: {total_size})")
            
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
                                self.progress_callback(progress)
            
            # Verify final file size
            final_size = os.path.getsize(output_path)
            if final_size != expected_size:
                raise ValueError(f"Final file size mismatch (expected: {expected_size}, got: {final_size})")
            logger.info(f"Download completed and verified. File size: {final_size} bytes")
                                
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def verify_file_placement(self) -> Dict[str, bool]:
        """Verify that all required files are in their correct locations"""
        verification_results = {}
        total_files = len(BASE_MODELS) + 2  # +2 for gguf_reader and checkpoint
        current_file = 0
        
        # Progress callback for verification
        def update_progress(file_name: str, exists: bool):
            nonlocal current_file
            current_file += 1
            status = "exists, skipping..." if exists else "not found!"
            if self.progress_callback:
                progress = int((current_file / total_files) * 100)
                self.progress_callback(progress, f"Verifying {file_name} ({current_file}/{total_files})... {status}")
        
        # Verify gguf_reader.py
        python_folder = self.validator.find_python_folder(Path(self.base_dir))
        gguf_path = Path(self.base_dir) / python_folder / "Lib" / "site-packages" / "gguf" / "gguf_reader.py"
        exists = gguf_path.exists()
        verification_results['gguf_reader.py'] = exists
        update_progress('gguf_reader.py', exists)

        # Verify all base models
        for model_name, model_info in BASE_MODELS.items():
            model_path = Path(self.models_path) / model_info['path'].strip('/') / model_info['filename']
            exists = model_path.exists()
            verification_results[model_info['filename']] = exists
            update_progress(model_info['filename'], exists)

        # Verify selected checkpoint
        if hasattr(self, 'selected_checkpoint_info'):
            checkpoint_path = Path(self.models_path) / self.selected_checkpoint_info['path'].strip('/') / self.selected_checkpoint_info['filename']
            exists = checkpoint_path.exists()
            verification_results[self.selected_checkpoint_info['filename']] = exists
            update_progress(self.selected_checkpoint_info['filename'], exists)

        return verification_results

    def print_verification_checklist(self, results: Dict[str, bool]):
        """Print a formatted verification checklist"""
        print("\nFile Placement Verification:")
        print("--------------------------------------------------")
        for file, exists in results.items():
            status = "[OK]" if exists else "[MISSING]"
            print(f"{status} {file}")
        print("--------------------------------------------------")
        
        if all(results.values()):
            print("All files are in their correct locations! [OK]")
        else:
            print("Some files are missing or in incorrect locations. [MISSING]")
            missing_files = [file for file, exists in results.items() if not exists]
            print("Missing files:")
            for file in missing_files:
                print(f"  - {file}")

    def check_and_download_dependencies(self, models_dir: str):
        """Check and download required base models"""
        print(f"\nChecking dependencies in: {models_dir}")
        logger.info(f"Starting dependency check in directory: {models_dir}")
        
        # Convert to Path object for better path handling
        models_dir = Path(models_dir)
        
        # Debug: List contents of models directory
        if models_dir.exists():
            print(f"Models directory exists: {models_dir}")
            print("Contents:")
            for item in models_dir.rglob('*'):
                print(f"  {'Dir: ' if item.is_dir() else 'File: '}{item}")
        else:
            print(f"Models directory does not exist: {models_dir}")
            models_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created models directory: {models_dir}")

        for model_name, model_info in BASE_MODELS.items():
            print(f"\nProcessing {model_name}...")
            
            # Create full model directory path using Path for better handling
            model_dir = models_dir / model_info['path'].strip('/')
            model_path = model_dir / model_info['filename']
            
            print(f"Target directory: {model_dir}")
            print(f"Target file path: {model_path}")
            
            logger.info(f"=== Processing {model_name} ===")
            logger.info(f"Target directory: {model_dir}")
            logger.info(f"Target file path: {model_path}")
            
            # Skip if file already exists
            if model_path.exists():
                print(f"{model_name} already exists at {model_path}")
                logger.info(f"Model {model_name} already exists at {model_path}")
                if self.progress_callback:
                    self.progress_callback(100, f"{model_name} already exists, skipping...")
                continue

            try:
                # Create model directory if it doesn't exist
                model_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created/verified directory: {model_dir}")
                logger.info(f"Created/verified model directory: {model_dir}")

                # Handle local files (like upscaler) differently from downloadable models
                if model_info.get('source') == 'local':
                    # For local files, construct the source path relative to the project root
                    source_path = Path(os.getcwd()) / 'required_files' / 'Comfyui files' / 'models' / 'upscale_models' / model_info['filename']
                    source_path = source_path.resolve()  # Resolve to absolute path
                    
                    print(f"\nProcessing local file: {model_name}")
                    print(f"Source path: {source_path}")
                    print(f"Destination path: {model_path}")
                    
                    if source_path.exists() and source_path.is_file():
                        print(f"Found {model_name} at {source_path}")
                        print(f"Source file size: {source_path.stat().st_size} bytes")
                        
                        if self.progress_callback:
                            self.progress_callback(0, f"Copying {model_name} from local files...")
                        
                        # Create parent directories if they don't exist
                        model_path.parent.mkdir(parents=True, exist_ok=True)
                        print(f"Copying {model_name}...")
                        
                        # Copy the file
                        shutil.copy2(str(source_path), str(model_path))
                        
                        if model_path.exists():
                            print(f"Successfully copied {model_name}")
                            print(f"Source path: {source_path}")
                            print(f"Destination path: {model_path}")
                            print(f"Destination file size: {model_path.stat().st_size} bytes")
                            logger.info(f"Successfully copied {model_name} to {model_path}")
                            if self.progress_callback:
                                self.progress_callback(100, f"Successfully copied {model_name}")
                        else:
                            error_msg = f"Failed to copy {model_name} - destination file not found after copy"
                            print(f"Error: {error_msg}")
                            logger.error(error_msg)
                            raise FileNotFoundError(error_msg)
                    else:
                        error_msg = f"{model_name} not found at source path: {source_path}"
                        print(f"Error: {error_msg}")
                        logger.error(error_msg)
                        raise FileNotFoundError(error_msg)
                else:
                    # Download remote models (HuggingFace, CivitAI)
                    if self.progress_callback:
                        self.progress_callback(0, f"Downloading {model_name}...")
                    print(f"Downloading {model_name}...")
                    self.download_file(
                        file_info=model_info,
                        output_path=str(model_path),
                        token=self.hf_token if model_info['source'] == 'huggingface' else self.civitai_token,
                        source=model_info['source']
                    )
            except Exception as e:
                error_msg = f"Error handling {model_name}: {str(e)}"
                print(f"Error: {error_msg}")
                logger.error(error_msg)
                raise

    def load_env(self) -> Dict[str, str]:
        """Load existing environment variables from .env file"""
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
                return env_vars
            except Exception as e:
                logger.error(f"Error reading .env file: {str(e)}")
                return {}
        return {}

    def save_env(self, env_vars: Dict[str, str]):
        """Save environment variables while preserving formatting"""
        try:
            existing_lines = []
            if os.path.exists(self.env_file):
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()

            new_lines = []
            updated_vars = set()

            for line in existing_lines:
                line_strip = line.strip()
                if line_strip and not line_strip.startswith('#'):
                    try:
                        if '=' in line_strip:
                            key = line_strip.split('=', 1)[0].strip()
                            if key in env_vars:
                                if key in ['BOT_SERVER', 'server_address', 'fluxversion']:
                                    comment_part = line[line.find('#'):] if '#' in line else ''
                                    value = env_vars[key].replace('"', '')
                                    new_lines.append(f'{key}="{value}"{comment_part}\n')
                                else:
                                    new_lines.append(f'{key}={env_vars[key]}\n')
                                updated_vars.add(key)
                            else:
                                new_lines.append(line)
                        else:
                            new_lines.append(line)
                    except Exception:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            for key, value in env_vars.items():
                if key not in updated_vars:
                    if key in ['BOT_SERVER', 'server_address', 'fluxversion']:
                        value = value.replace('"', '')
                        new_lines.append(f'{key}="{value}"\n')
                    else:
                        new_lines.append(f'{key}={value}\n')

            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        except Exception as e:
            logger.error(f"Error saving to .env file: {str(e)}")
            raise

    def update_env_file(self, workflow_file: str):
        """Update .env file with selected workflow"""
        try:
            env_vars = self.load_env()
            env_vars['fluxversion'] = workflow_file
            self.save_env(env_vars)
        except Exception as e:
            logger.error(f"Error updating workflow in .env: {str(e)}")
            raise

    def get_tokens(self) -> Dict[str, str]:
        """Get both Hugging Face and CivitAI tokens"""
        env_vars = self.load_env()
        tokens = {}

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

            # Select base directory
            print("\nPlease select your ComfyUI base directory...")
            base_dir = self.select_base_directory()
            if not base_dir:
                logger.info("No directory selected. Setup cancelled.")
                print("No directory selected. Setup cancelled.")
                return False
            
            # Copy gguf_reader.py
            print("\nCopying required files...")
            if not self.validator.copy_gguf_reader(os.getcwd(), base_dir):
                raise Exception("Failed to copy gguf_reader.py")
                
            print("\n!!!!!!!!!! BEFORE UPSCALER SECTION !!!!!!!!!!")
            
            # Copy upscaler
            print("\n=== Copying Upscaler ===")
            source_dir = os.getcwd()
            print(f"DEBUG: Current working directory: {os.getcwd()}")
            print(f"DEBUG: Source directory absolute path: {os.path.abspath(source_dir)}")
            print(f"DEBUG: Base directory absolute path: {os.path.abspath(base_dir)}")
            
            # Check if source file exists
            expected_source = os.path.join(source_dir, "required_files", "Comfyui files", "models", "upscale_models", "4x-ClearRealityV1.pth")
            if os.path.isfile(expected_source):
                print(f"DEBUG: Source file exists at: {expected_source}")
            else:
                print(f"DEBUG: Source file NOT found at: {expected_source}")
                # List contents of the directory
                try:
                    parent_dir = os.path.dirname(expected_source)
                    print(f"DEBUG: Contents of {parent_dir}:")
                    if os.path.exists(parent_dir):
                        for item in os.listdir(parent_dir):
                            print(f"DEBUG:   {item}")
                    else:
                        print(f"DEBUG: Directory does not exist: {parent_dir}")
                except Exception as e:
                    print(f"DEBUG: Error listing directory: {e}")
            
            # Get models path from .env before copy
            env_vars = self.load_env()
            models_path = env_vars.get('COMFYUI_MODELS_PATH')
            print(f"DEBUG: COMFYUI_MODELS_PATH from .env: {models_path}")
            
            print("\nAttempting to call copy_upscaler...")
            success = self.validator.copy_upscaler(source_dir, base_dir)
            print(f"DEBUG: copy_upscaler returned: {success}")
            
            if not success:
                error_msg = "Failed to copy upscaler model - check logs for details"
                print(f"DEBUG: {error_msg}")
                raise Exception(error_msg)
            else:
                print("DEBUG: Successfully called copy_upscaler")
            
            print("\n!!!!!!!!!! AFTER UPSCALER SECTION !!!!!!!!!!")

            # Save the models path to .env
            env_vars = self.load_env()
            self.models_path = os.path.join(base_dir, 'ComfyUI', 'models')
            env_vars['COMFYUI_MODELS_PATH'] = self.models_path
            self.save_env(env_vars)

            # Check and download dependencies
            print("\nChecking and downloading required models...")
            logger.info("Starting dependency downloads")
            logger.info(f"Using models directory: {self.models_path}")
            self.check_and_download_dependencies(self.models_path)

            # Select and download checkpoint
            print("\nAvailable checkpoints:")
            for i, (name, info) in enumerate(CHECKPOINTS.items(), 1):
                print(f"{i}. {name}")
            
            # Default to FLUXFusion 24GB if in CLI mode
            checkpoint_name = "FLUXFusion 24GB"
            print(f"\nAutomatic selection in CLI mode: {checkpoint_name}")
            checkpoint_info = CHECKPOINTS[checkpoint_name]
            logger.info(f"Selected checkpoint: {checkpoint_name}")
            self.selected_checkpoint_info = checkpoint_info  # Store for verification

            # Download selected checkpoint
            checkpoint_path = os.path.join(
                self.models_path,
                checkpoint_info['path'].strip('/'),
                checkpoint_info['filename']
            )
            
            if not os.path.exists(checkpoint_path):
                print(f"\nDownloading checkpoint: {checkpoint_name}")
                logger.info(f"Starting checkpoint download: {checkpoint_name}")
                token = self.hf_token if checkpoint_info['source'] == 'huggingface' else self.civitai_token
                self.download_file(
                    file_info=checkpoint_info,
                    output_path=checkpoint_path,
                    token=token,
                    source=checkpoint_info['source']
                )
            else:
                print(f"\nCheckpoint {checkpoint_name} already exists, skipping download...")

            # Update .env file with workflow
            logger.info(f"Updating .env with workflow: {checkpoint_info['workflow']}")
            self.update_env_file(checkpoint_info['workflow'])
            
            # After all files are copied/downloaded, verify placement
            verification_results = self.verify_file_placement()
            self.print_verification_checklist(verification_results)

            print("\nSetup completed successfully!")
            logger.info("Setup completed successfully")
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"\nError: {error_msg}")
            return False

    def select_base_directory(self) -> Optional[str]:
        """Prompt user to select ComfyUI base directory"""
        root = tk.Tk()
        root.withdraw()
        base_dir = filedialog.askdirectory(title="Select ComfyUI Base Directory")
        
        if base_dir:
            if self.validator.validate_comfyui_directory(base_dir):
                self.base_dir = base_dir
                paths = self.validator.setup_required_paths(base_dir)
                self.models_path = paths['models_dir']
                return base_dir
            else:
                raise ValueError("Invalid ComfyUI directory structure. Please ensure ComfyUI and python_embedded folders exist.")
        return None