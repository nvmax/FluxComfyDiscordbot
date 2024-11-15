import os
import re
import logging
from huggingface_hub import HfApi, hf_hub_download

logger = logging.getLogger(__name__)

class HuggingFaceDownloader:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')

    def get_repo_files(self, repo_id: str) -> list:
        """Get list of .safetensors files in a HuggingFace repository"""
        try:
            api = HfApi(token=self.hf_token)
            files = api.list_repo_files(repo_id)
            return [f for f in files if f.endswith('.safetensors')]
        except Exception as e:
            logger.error(f"Error getting repo files: {e}")
            raise

    def download_file(self, repo_id: str, filename: str, dest_folder: str) -> str:
        """Download a file from HuggingFace"""
        try:
            dest_path = os.path.join(dest_folder, filename)
            
            # Download the file
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=dest_folder,
                local_dir_use_symlinks=False,
                token=self.hf_token
            )
            
            return filename
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

def extract_repo_info(url: str) -> tuple:
    """Extract repository ID and filename from HuggingFace URL"""
    try:
        # Remove trailing slash if present
        url = url.rstrip('/')
        
        # Extract repo ID from URL
        if '/blob/' in url:
            # URL format: https://huggingface.co/repo_id/blob/main/filename
            match = re.match(r'https://huggingface\.co/([^/]+/[^/]+)/blob/[^/]+/(.+)', url)
            if match:
                return match.group(1), match.group(2)
        else:
            # URL format: https://huggingface.co/repo_id/resolve/main/filename
            match = re.match(r'https://huggingface\.co/([^/]+/[^/]+)(?:/resolve/[^/]+)?/(.+)', url)
            if match:
                return match.group(1), match.group(2)
        
        raise ValueError("Could not extract repository info from URL")
        
    except Exception as e:
        logger.error(f"Error extracting repo info: {e}")
        raise
