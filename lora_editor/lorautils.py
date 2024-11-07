import os
import json
import requests
import re
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, List, Tuple
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_filename(filename):
    """Remove or replace characters that are invalid in Windows filenames"""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    return sanitized[:240]

class LoraConfig:
    def __init__(self, config_file: str = None):
        """Initialize LoRA configuration manager"""
        self.config_file = config_file or os.getenv('LORA_JSON_PATH', 'lora.json')
        self.data = self.load_config()
        
    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"default": "", "available_loras": []}
            
    def save_config(self) -> None:
        """Save configuration to JSON file"""
        os.makedirs(os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)
            
    def get_lora_files(self, folder: str) -> List[str]:
        """Get list of LoRA files from specified folder"""
        return [f.name for f in Path(folder).glob("*.safetensors")]
        
    def update_ids(self) -> None:
        """Update all IDs to match their position in the list"""
        for i, lora in enumerate(self.data["available_loras"], 1):
            lora["id"] = i

class HuggingFaceDownloader:
    def __init__(self, progress_callback=None):
        self.api_token = os.getenv('HUGGINGFACE_TOKEN')
        self.progress_callback = progress_callback
        self.api = HfApi(token=self.api_token)

    def extract_repo_info(self, url: str) -> Tuple[str, str]:
        """Extract repository ID and filename from URL"""
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                raise ValueError("Invalid HuggingFace URL format")
            
            repo_id = '/'.join(path_parts[:2])
            filename = path_parts[-1] if len(path_parts) > 2 else None
            
            return repo_id, filename
        except Exception as e:
            raise ValueError(f"Failed to parse HuggingFace URL: {str(e)}")

    def find_safetensors_file(self, repo_id: str) -> str:
        """Find first available safetensors file in repository"""
        try:
            files = self.api.list_repo_files(repo_id)
            safetensor_files = [f for f in files if f.endswith('.safetensors')]
            
            if not safetensor_files:
                raise ValueError("No .safetensors files found in repository")
            
            return safetensor_files[0]
        except Exception as e:
            raise ValueError(f"Error listing repository files: {str(e)}")

    def download_file(self, repo_id: str, filename: str, dest_dir: str) -> str:
        """Download file from HuggingFace"""
        try:
            return hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=dest_dir,
                token=self.api_token,
                force_download=True,
                local_files_only=False,
            )
        except Exception as e:
            raise Exception(f"Failed to download file: {str(e)}")

class CivitAIDownloader:
    def __init__(self, progress_callback=None):
        self.api_token = os.getenv('CIVITAI_API_TOKEN')
        self.progress_callback = progress_callback
        self.api_base = "https://civitai.com/api/v1"
        
        self.headers = {}
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
        self.headers["Content-Type"] = "application/json"

    def extract_model_id(self, url: str) -> Tuple[str, str]:
        """Extract model ID and version ID from URL"""
        try:
            model_id_match = re.search(r'/models/(\d+)', str(url))
            if not model_id_match:
                raise ValueError("Invalid Lora link. Please provide a valid Civitai model link.")
            
            model_id = model_id_match.group(1)
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            version_id = query_params.get('modelVersionId', [None])[0]
            
            return model_id, version_id
        except Exception as e:
            raise ValueError(f"Failed to parse URL: {str(e)}")

    def get_model_info(self, model_id: str) -> Dict:
        try:
            response = requests.get(
                f"{self.api_base}/models/{model_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch model information. Status: {response.status_code}")
            
            model_info = response.json()
            
            if model_info.get('type') != 'LORA':
                raise ValueError("This model is not a LORA type model")
            
            return model_info
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch model info: {str(e)}")

    def get_version_info(self, version_id: str) -> Dict:
        try:
            response = requests.get(
                f"{self.api_base}/model-versions/{version_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch version information. Status: {response.status_code}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch version info: {str(e)}")

    def download_file(self, model_info: Dict, version_id: str, dest_folder: str) -> str:
        """Download file from CivitAI"""
        try:
            version_info = self.get_version_info(version_id)
            
            if not version_info.get('files'):
                raise ValueError("No files available for this model version")
            
            safetensor_file = next(
                (f for f in version_info['files'] 
                 if f.get('metadata', {}).get('format') == 'SafeTensor'),
                None
            )
            
            if not safetensor_file:
                raise ValueError("No SafeTensor format file available")
            
            download_url = safetensor_file.get('downloadUrl')
            if not download_url:
                raise ValueError("No download URL available")
            
            logging.info(f"Downloading from URL: {download_url}")
            
            response = requests.get(download_url, 
                                 headers=self.headers,
                                 stream=True)
            
            if response.status_code != 200:
                raise Exception(f"Download failed. Status: {response.status_code}")
            
            # Determine filename
            content_disposition = response.headers.get('content-disposition')
            if content_disposition:
                filename_match = re.findall(r'filename\*=UTF-8\'\'(.+)', content_disposition)
                if filename_match:
                    file_name = unquote(filename_match[0])
                else:
                    filename_match = re.findall(r'filename="(.+)"', content_disposition)
                    if filename_match:
                        file_name = filename_match[0]
                    else:
                        file_name = f"{model_info['name']}_{version_id}.safetensors"
            else:
                trained_words = version_info.get('trainedWords', [])
                base_name = trained_words[0] if trained_words else model_info['name']
                file_name = f"{base_name}_{version_id}.safetensors"
            
            file_name = sanitize_filename(file_name)
            logging.info(f"Using filename: {file_name}")
            
            os.makedirs(dest_folder, exist_ok=True)
            dest_path = os.path.join(dest_folder, file_name)
            
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            last_update = time.time()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        current_time = time.time()
                        if (current_time - last_update) >= 0.1:  # Update progress every 100ms
                            if self.progress_callback and total_size:
                                progress = (bytes_downloaded / total_size) * 100
                                self.progress_callback(progress)
                                last_update = current_time
            
            return dest_path
            
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    def get_model_trained_words(self, model_info: Dict, version_id: str = None) -> List[str]:
        """Get trained words for the model version"""
        try:
            if version_id:
                version = next((v for v in model_info['modelVersions'] 
                              if str(v['id']) == version_id), None)
            else:
                version = model_info['modelVersions'][0]
            
            return version.get('trainedWords', [])
        except Exception:
            return []
