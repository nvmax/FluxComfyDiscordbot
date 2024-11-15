import os
import re
import requests
import logging
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

class CivitAIDownloader:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        civitai_token = os.getenv('CIVITAI_API_TOKEN')
        self.headers = {'Authorization': f'Bearer {civitai_token}'} if civitai_token else {}

    def get_download_url(self, url: str) -> tuple:
        """Get download URL from CivitAI model page URL"""
        try:
            # Extract model ID from URL
            model_id_match = re.search(r'models/(\d+)', url)
            if not model_id_match:
                raise ValueError("Could not extract model ID from URL")
            
            model_id = model_id_match.group(1)
            version_id = None
            
            # Check if URL contains version ID
            version_match = re.search(r'modelVersionId=(\d+)', url)
            if version_match:
                version_id = version_match.group(1)
            
            # Get model info from API
            api_url = f'https://civitai.com/api/v1/models/{model_id}'
            response = requests.get(api_url, headers=self.headers)
            response.raise_for_status()
            model_data = response.json()
            
            # If no specific version was requested, use the latest one
            if not version_id:
                version = model_data['modelVersions'][0]  # Latest version is first
            else:
                version = next(
                    (v for v in model_data['modelVersions'] if str(v['id']) == version_id),
                    model_data['modelVersions'][0]
                )
            
            # Extract trigger words
            trigger_words = ""
            if 'trainedWords' in version:
                trigger_words = ", ".join(version['trainedWords'])
            
            # Find the first .safetensors file
            download_url = None
            for file in version['files']:
                if file['name'].endswith('.safetensors'):
                    download_url = file['downloadUrl']
                    break
            
            if not download_url:
                raise ValueError("No .safetensors file found in model files")
                
            return download_url, trigger_words
            
        except Exception as e:
            logger.error(f"Error getting download URL: {e}")
            raise

    def download_file(self, url: str, dest_folder: str) -> str:
        """Download a file from CivitAI"""
        try:
            # Get the direct download URL if needed
            if 'civitai.com/models/' in url:
                url, _ = self.get_download_url(url)
            
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
            dest_path = os.path.join(dest_folder, filename)
            block_size = 1024  # 1 Kibibyte
            downloaded = 0
            
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
