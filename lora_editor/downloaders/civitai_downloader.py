import os
import re
import requests
import logging
from urllib.parse import urlparse, unquote

# Set logging level to INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CivitAIDownloader:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        civitai_token = os.getenv('CIVITAI_API_TOKEN')
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://civitai.com/'
        }
        if civitai_token:
            self.headers['Authorization'] = f'Bearer {civitai_token}'

    def get_download_url(self, url: str) -> tuple:
        """Get download URL and model info from CivitAI model page URL
        Returns:
            tuple: (download_url, trigger_words, recommended_weight)
        """
        try:
            # Extract model ID and version ID from URL
            logger.info(f"Processing URL: {url}")
            
            # Handle both web URLs and direct API URLs
            if 'api/v1/model-versions/' in url:
                version_id = url.split('model-versions/')[-1].split('?')[0]
                logger.info(f"Direct API URL detected, version_id: {version_id}")
                version_api_url = f'https://civitai.com/api/v1/model-versions/{version_id}'
                version_response = requests.get(version_api_url, headers=self.headers)
                version_response.raise_for_status()
                version_data = version_response.json()
                logger.info(f"Response status code: {version_response.status_code}")
                logger.info(f"Version data keys: {version_data.keys() if version_data else 'None'}")
                if 'files' in version_data:
                    logger.info(f"Files in version data: {[f.get('name', 'unnamed') for f in version_data['files']]}")
                model_id = str(version_data.get('modelId'))
                logger.info(f"Retrieved model_id from API: {model_id}")
            else:
                model_id_match = re.search(r'models/(\d+)', url)
                version_match = re.search(r'modelVersionId=(\d+)', url)
                
                if not model_id_match:
                    logger.error("Could not extract model ID from URL")
                    raise ValueError("Could not extract model ID from URL")
                
                model_id = model_id_match.group(1)
                version_id = version_match.group(1) if version_match else None
                logger.info(f"Extracted from web URL - model_id: {model_id}, version_id: {version_id}")
                
                if version_id:
                    version_api_url = f'https://civitai.com/api/v1/model-versions/{version_id}'
                    logger.info(f"Fetching version data from: {version_api_url}")
                    version_response = requests.get(version_api_url, headers=self.headers)
                    version_response.raise_for_status()
                    version_data = version_response.json()
                    logger.info(f"Response status code: {version_response.status_code}")
                    logger.info(f"Version data keys: {version_data.keys() if version_data else 'None'}")
                    if 'files' in version_data:
                        logger.info(f"Files in version data: {[f.get('name', 'unnamed') for f in version_data['files']]}")
                else:
                    api_url = f'https://civitai.com/api/v1/models/{model_id}'
                    logger.info(f"Fetching model data from: {api_url}")
                    response = requests.get(api_url, headers=self.headers)
                    response.raise_for_status()
                    model_data = response.json()
                    version_data = model_data.get('modelVersions', [{}])[0]
            
            # Extract trigger words
            trigger_words = ""
            if version_data and 'trainedWords' in version_data:
                trigger_words = ", ".join(version_data['trainedWords'])
                logger.info(f"Found trigger words: {trigger_words}")

            # Extract recommended weight
            recommended_weight = 1.0  # Default weight
            
            if version_data and 'images' in version_data and version_data['images']:
                logger.info("Found images in version data")
                for image in version_data['images']:
                    meta = image.get('meta')
                    if meta and 'resources' in meta:
                        for resource in meta['resources']:
                            if resource.get('type') == 'lora' and 'weight' in resource:
                                recommended_weight = float(resource['weight'])
                                logger.info(f"Found recommended weight: {recommended_weight}")
                                break
                        if recommended_weight != 1.0:
                            break

            # Find download URL
            download_url = None
            if version_data:
                if 'downloadUrl' in version_data:
                    logger.info("Found direct download URL in version data")
                    download_url = version_data['downloadUrl']
                elif 'files' in version_data:
                    logger.info(f"Found {len(version_data['files'])} files in version data")
                    for file in version_data['files']:
                        logger.info(f"Checking file: {file.get('name', 'unnamed')}")
                        if file.get('name', '').endswith('.safetensors'):
                            download_url = file.get('downloadUrl')
                            if download_url:
                                logger.info(f"Found download URL in file: {file['name']}")
                                break
                else:
                    logger.error("No files found in version data")
            else:
                logger.error("Version data is None")
            
            if not download_url:
                logger.error("No download URL found in version data")
                raise ValueError("No .safetensors file found in model files")
            
            logger.info(f"Final download URL: {download_url}")
            return download_url, trigger_words, recommended_weight
            
        except Exception as e:
            logger.error(f"Error getting download URL: {str(e)}")
            logger.exception("Full traceback:")
            raise

    def download_file(self, url: str, dest_folder: str) -> str:
        """Download a file from CivitAI"""
        try:
            # Get the direct download URL if needed
            if 'civitai.com/models/' in url:
                url, _, _ = self.get_download_url(url)
            
            # Start the download
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            # Get filename from Content-Disposition header or URL
            if 'Content-Disposition' in response.headers:
                filename = re.findall("filename=(.+)", response.headers['Content-Disposition'])[0]
            else:
                filename = unquote(os.path.basename(urlparse(url).path))
            
            # Remove quotes if present
            filename = filename.strip('"\'')
            
            # Get total file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download the file
            dest_path = os.path.normpath(os.path.join(dest_folder, filename))
            
            # Check if file already exists
            if os.path.exists(dest_path):
                logger.info(f"File already exists at {dest_path}")
                try:
                    # Try to remove the existing file
                    os.remove(dest_path)
                    logger.info(f"Successfully removed existing file at {dest_path}")
                except Exception as e:
                    logger.error(f"Failed to remove existing file: {e}")
                    raise ValueError(f"File already exists at {dest_path} and could not be removed")

            block_size = 1024  # 1 Kibibyte
            downloaded = 0
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            with open(dest_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    f.write(data)
                    if self.progress_callback and total_size:
                        progress = (downloaded / total_size) * 100
                        self.progress_callback(progress)
            
            return filename
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

    def download(self, url: str, dest_folder: str, progress_callback=None) -> str:
        """Download a LoRA model from CivitAI"""
        try:
            if progress_callback:
                self.progress_callback = progress_callback
            return self.download_file(url, dest_folder)
        except Exception as e:
            logger.error(f"Error downloading from CivitAI: {e}")
            raise
