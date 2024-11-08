import os
import json
import requests
import re
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        self.headers = {}
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
        self.headers["Content-Type"] = "application/json"

    def extract_version_id(self, url: str) -> Optional[str]:
        try:
            # Parse URL and query parameters
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Check for modelVersionId in query parameters
            if 'modelVersionId' in query_params:
                version_id = query_params['modelVersionId'][0]
                logger.info(f"Found version ID in query params: {version_id}")
                return version_id
                
            # Extract model ID and get version info
            model_id_match = re.search(r'/models/(\d+)', url)
            if model_id_match:
                model_id = model_id_match.group(1)
                logger.info(f"Found model ID: {model_id}")
                model_info = self.get_model_info(model_id)
                if model_info and 'modelVersions' in model_info:
                    version_id = str(model_info['modelVersions'][0]['id'])
                    logger.info(f"Found version ID from model info: {version_id}")
                    return version_id
                    
            return None
        except Exception as e:
            logger.error(f"Error extracting version ID: {str(e)}")
            return None

    def get_model_info(self, url_or_id: str) -> Optional[Dict]:
        """Get model information from CivitAI API"""
        try:
            # Extract model ID if URL provided
            if '/' in url_or_id:
                model_match = re.search(r'/models/(\d+)', url_or_id)
                if not model_match:
                    raise ValueError("Could not extract model ID from URL")
                model_id = model_match.group(1)
            else:
                model_id = url_or_id

            api_url = f"https://civitai.com/api/v1/models/{model_id}"
            response = requests.get(api_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            model_info = response.json()
            if not model_info:
                raise ValueError("No model information returned from API")
            
            return model_info
            
        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            return None

    def get_download_url(self, url: str) -> Optional[str]:
        try:
            version_id = self.extract_version_id(url)
            logger.info(f"Extracted version ID: {version_id}")
            
            if not version_id:
                logger.info("No version ID extracted, attempting direct API call")
                # Try direct API call with model ID
                model_id = re.search(r'/models/(\d+)', url)
                if model_id:
                    model_info = self.get_model_info(model_id.group(1))
                    if model_info and model_info.get('modelVersions'):
                        version_id = str(model_info['modelVersions'][0]['id'])
                        logger.info(f"Found version ID from model info: {version_id}")

            if version_id:
                api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
                logger.info(f"Calling API URL: {api_url}")
                response = requests.get(api_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                version_info = response.json()
                logger.info(f"API Response status: {response.status_code}")
                
                # Find primary file with SafeTensor format
                for file in version_info.get('files', []):
                    if file.get('primary', False):
                        download_url = file.get('downloadUrl')
                        logger.info(f"Found download URL: {download_url}")
                        return download_url
                        
            raise ValueError("No suitable download URL found")
                
        except Exception as e:
            logger.error(f"Error getting download URL: {str(e)}")
            return None

    def get_model_trained_words(self, url: str) -> List[str]:
        """Get trained words for the model version"""
        try:
            version_id = self.extract_version_id(url)
            if not version_id:
                return []
                
            api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
            response = requests.get(api_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            version_info = response.json()
            return version_info.get('trainedWords', [])
            
        except Exception as e:
            logger.error(f"Error getting trained words: {str(e)}")
            return []

    def download_file(self, model_info: Dict, version_id: str, dest_folder: str) -> str:
        try:
            # Get download URL using the version ID
            api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
            logger.info(f"Requesting version info from: {api_url}")
            
            response = requests.get(api_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            version_data = response.json()
            logger.info(f"Version data received for ID {version_id}")
            
            # Find the primary file
            for file in version_data.get('files', []):
                if file.get('primary', False):
                    download_url = file.get('downloadUrl')
                    if download_url:
                        logger.info(f"Found download URL: {download_url}")
                        
                        # Get filename from content disposition or URL
                        download_response = requests.get(
                            download_url,
                            headers=self.headers,
                            stream=True,
                            timeout=30
                        )
                        download_response.raise_for_status()
                        
                        content_disposition = download_response.headers.get('content-disposition')
                        if content_disposition:
                            filename = re.findall("filename=(.+)", content_disposition)[0].strip('"')
                        else:
                            filename = download_url.split('/')[-1]
                        
                        output_path = os.path.join(dest_folder, filename)
                        
                        # Download with progress tracking
                        total_size = int(download_response.headers.get('content-length', 0))
                        block_size = 1024 * 1024  # 1MB chunks
                        downloaded_size = 0
                        
                        with open(output_path, 'wb') as f:
                            for data in download_response.iter_content(block_size):
                                downloaded_size += len(data)
                                f.write(data)
                                if total_size:
                                    progress = (downloaded_size / total_size) * 100
                                    if self.progress_callback:
                                        self.progress_callback(progress)
                        
                        logger.info(f"Download completed: {output_path}")
                        return output_path
            
            raise ValueError("No primary file found in version data")
        except Exception as e:
            logger.error(f"Error in download_file: {str(e)}")
            raise