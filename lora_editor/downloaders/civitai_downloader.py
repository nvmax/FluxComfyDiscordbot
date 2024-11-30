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
        self.headers = {'Authorization': f'Bearer {civitai_token}'} if civitai_token else {}

    def get_download_url(self, url: str) -> tuple:
        """Get download URL and model info from CivitAI model page URL
        Returns:
            tuple: (download_url, trigger_words, recommended_weight)
        """
        try:
            # Extract model ID and version ID from URL
            model_id_match = re.search(r'models/(\d+)', url)
            version_match = re.search(r'modelVersionId=(\d+)', url)
            
            if not model_id_match:
                raise ValueError("Could not extract model ID from URL")
            
            model_id = model_id_match.group(1)
            version_id = version_match.group(1) if version_match else None
            
            # First get the specific version info if we have a version ID
            if version_id:
                version_api_url = f'https://civitai.com/api/v1/model-versions/{version_id}'
                version_response = requests.get(version_api_url, headers=self.headers)
                version_response.raise_for_status()
                version_data = version_response.json()
            else:
                # Get model info from API
                api_url = f'https://civitai.com/api/v1/models/{model_id}'
                response = requests.get(api_url, headers=self.headers)
                response.raise_for_status()
                model_data = response.json()
                version_data = model_data['modelVersions'][0]  # Latest version is first
            
            # Extract trigger words
            trigger_words = ""
            if 'trainedWords' in version_data:
                trigger_words = ", ".join(version_data['trainedWords'])

            # Extract recommended weight from image metadata
            recommended_weight = 1.0  # Default weight
            
            if 'images' in version_data and version_data['images']:
                # Look through images for one with metadata containing resources
                for image in version_data['images']:
                    if 'meta' in image and 'resources' in image['meta']:
                        for resource in image['meta']['resources']:
                            if resource.get('type') == 'lora' and 'weight' in resource:
                                recommended_weight = float(resource['weight'])
                                break
                        if recommended_weight != 1.0:  # If we found a weight, stop looking
                            break

            # Find the first .safetensors file
            download_url = None
            for file in version_data['files']:
                if file['name'].endswith('.safetensors'):
                    download_url = file['downloadUrl']
                    break
            
            if not download_url:
                raise ValueError("No .safetensors file found in model files")
                
            return download_url, trigger_words, recommended_weight
            
        except Exception as e:
            logger.error(f"Error getting download URL: {e}")
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
