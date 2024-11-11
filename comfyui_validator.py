import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict

class ComfyUIValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def find_folder(self, base_path: Path, possible_names: list) -> Optional[str]:
        """
        Find a folder with any of the possible naming variations.
        Returns the actual folder name if found, None otherwise.
        """
        try:
            # List all directories in the base path
            self.logger.debug(f"Searching in: {base_path}")
            self.logger.debug(f"Looking for any of: {possible_names}")
            
            # Print all directories found
            all_dirs = [f.name for f in base_path.iterdir() if f.is_dir()]
            self.logger.debug(f"All directories found: {all_dirs}")
            
            for f in base_path.iterdir():
                if f.is_dir():
                    self.logger.debug(f"Checking directory: {f.name}")
                    if f.name in possible_names:  # Direct match first
                        self.logger.debug(f"Found direct match: {f.name}")
                        return f.name
                    if f.name.lower() in [name.lower() for name in possible_names]:
                        self.logger.debug(f"Found case-insensitive match: {f.name}")
                        return f.name
                        
            self.logger.debug("No matching folder found")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding folder: {str(e)}")
            return None

    def find_comfyui_folder(self, base_path: Path) -> Optional[str]:
        """Find the ComfyUI folder with possible naming variations"""
        self.logger.debug("Starting search for ComfyUI folder")
        possible_names = ["ComfyUI"]
        result = self.find_folder(base_path, possible_names)
        self.logger.debug(f"ComfyUI folder search result: {result}")
        return result

    def find_python_folder(self, base_path: Path) -> Optional[str]:
        """Find the Python folder with possible naming variations"""
        self.logger.debug("Starting search for Python folder")
        possible_names = ["python_embeded"]
        result = self.find_folder(base_path, possible_names)
        self.logger.debug(f"Python folder search result: {result}")
        return result

    def validate_comfyui_directory(self, base_dir: str) -> bool:
        """
        Validate that the specified directory contains required ComfyUI folders.
        """
        try:
            self.logger.debug(f"Validating directory: {base_dir}")
            base_path = Path(base_dir)
            
            # List all contents of the directory
            self.logger.debug("Directory contents:")
            for item in base_path.iterdir():
                self.logger.debug(f"- {item.name} ({'directory' if item.is_dir() else 'file'})")
            
            # Find folders using the new methods
            comfyui_folder = self.find_comfyui_folder(base_path)
            python_folder = self.find_python_folder(base_path)
            
            self.logger.debug(f"Validation results:")
            self.logger.debug(f"ComfyUI folder: {comfyui_folder}")
            self.logger.debug(f"Python folder: {python_folder}")
            
            if not comfyui_folder:
                self.logger.error("ComfyUI folder not found in specified directory")
                return False
                
            if not python_folder:
                self.logger.error("Python folder (python_embeded) not found in specified directory")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating ComfyUI directory: {str(e)}")
            return False
    
    def setup_required_paths(self, base_dir: str) -> Dict[str, str]:
        """
        Setup and validate all required paths.
        """
        try:
            base_path = Path(base_dir)
            
            # Get actual folder names
            comfyui_folder = self.find_comfyui_folder(base_path)
            python_folder = self.find_python_folder(base_path)
            
            if not comfyui_folder or not python_folder:
                raise ValueError("Required folders not found")
            
            paths = {
                'models_dir': str(base_path / comfyui_folder / "models"),
                'python_dir': str(base_path / python_folder),
                'gguf_path': str(base_path / python_folder / "Lib" / "site-packages" / "gguf")
            }
            
            # Create directories if they don't exist
            for path in paths.values():
                os.makedirs(path, exist_ok=True)
                self.logger.info(f"Ensured directory exists: {path}")
                
            return paths
            
        except Exception as e:
            self.logger.error(f"Error setting up paths: {str(e)}")
            raise
        
    def copy_gguf_reader(self, source_dir: str, dest_dir: str) -> bool:
        """
        Copy the gguf_reader.py file to its destination.
        """
        try:
            # Get actual python folder name
            python_folder = self.find_python_folder(Path(dest_dir))
            if not python_folder:
                raise ValueError("Python folder not found")
            
            # Setup paths with correct folder name
            source_path = Path(source_dir) / "required_files" / "Comfyui files" / "python_embeded" / "Lib" / "site-packages" / "gguf" / "gguf_reader.py"
            dest_path = Path(dest_dir) / python_folder / "Lib" / "site-packages" / "gguf" / "gguf_reader.py"
            
            # Log the paths for debugging
            self.logger.info(f"Source path: {source_path}")
            self.logger.info(f"Destination path: {dest_path}")
            
            # Ensure destination directory exists
            os.makedirs(dest_path.parent, exist_ok=True)
            
            # Verify source file exists
            if not source_path.exists():
                self.logger.error(f"Source file not found: {source_path}")
                # Try to list contents of the required_files directory to debug
                try:
                    req_files_path = Path(source_dir) / "required_files"
                    if req_files_path.exists():
                        self.logger.debug(f"Contents of required_files directory:")
                        for item in req_files_path.rglob('*'):
                            self.logger.debug(f"  {item}")
                except Exception as e:
                    self.logger.error(f"Error listing required_files contents: {e}")
                return False
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            self.logger.info(f"Successfully copied gguf_reader.py to {dest_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying gguf_reader.py: {str(e)}", exc_info=True)
            return False