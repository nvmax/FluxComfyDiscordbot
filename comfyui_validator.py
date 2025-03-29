import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict

class ComfyUIValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler if it doesn't exist
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

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
        If folders don't exist, create them.
        """
        try:
            print(f"\nValidating/creating directory structure in: {base_dir}")
            base_path = Path(base_dir)
            
            # Create base directory if it doesn't exist
            base_path.mkdir(parents=True, exist_ok=True)
            
            # List all contents of the directory
            print("Current directory contents:")
            for item in base_path.iterdir():
                print(f"- {item.name} ({'directory' if item.is_dir() else 'file'})")
            
            # Find or create folders
            comfyui_folder = self.find_comfyui_folder(base_path)
            python_folder = self.find_python_folder(base_path)
            
            # Create ComfyUI folder if not found
            if not comfyui_folder:
                print("ComfyUI folder not found, creating it...")
                comfyui_path = base_path / "ComfyUI"
                comfyui_path.mkdir(exist_ok=True)
                comfyui_folder = "ComfyUI"
                
            # Create python_embeded folder if not found
            if not python_folder:
                print("Python folder not found, creating it...")
                python_path = base_path / "python_embeded"
                python_path.mkdir(exist_ok=True)
                python_folder = "python_embeded"
            
            print(f"\nDirectory structure validated/created:")
            print(f"- ComfyUI folder: {comfyui_folder}")
            print(f"- Python folder: {python_folder}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating/creating ComfyUI directory: {str(e)}")
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
            try:
                print("DEBUG: Attempting to copy file...")
                print(f"DEBUG: Source path type: {type(source_path)}, Destination path type: {type(dest_path)}")
                print(f"DEBUG: Source path exists: {source_path.exists()}")
                print(f"DEBUG: Source path is file: {source_path.is_file()}")
                print(f"DEBUG: Destination directory exists: {dest_path.parent.exists()}")
                print(f"DEBUG: Destination directory is writable: {os.access(str(dest_path.parent), os.W_OK)}")
                shutil.copy2(str(source_path), str(dest_path))
                print("DEBUG: Copy operation completed")
            except Exception as e:
                print(f"DEBUG: Error during copy operation: {e}")
                print(f"DEBUG: Full error details:", exc_info=True)
                return False
            
            # Verify copy was successful
            if dest_path.is_file():
                self.logger.info(f"Successfully copied gguf_reader.py to {dest_path}")
                return True
            else:
                self.logger.error("Failed to verify gguf_reader.py copy")
                return False

        except Exception as e:
            self.logger.error(f"Error copying gguf_reader.py: {str(e)}", exc_info=True)
            return False

    def copy_upscaler(self, source_dir: str, dest_dir: str) -> bool:
        """
        Copy the upscaler model file to its destination.
        Uses COMFYUI_MODELS_PATH from .env for destination.
        """
        try:
            print("\nDEBUG: Starting copy_upscaler")
            # Load the models path from .env
            try:
                with open('.env', 'r') as f:
                    env_content = f.read()
                    print(f"DEBUG: .env file contents:\n{env_content}")
            except Exception as e:
                print(f"DEBUG: Error reading .env file: {e}")
                return False

            env_vars = {}
            for line in env_content.splitlines():
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"')  # Remove quotes if present
            
            models_path = env_vars.get('COMFYUI_MODELS_PATH')
            if not models_path:
                print("DEBUG: COMFYUI_MODELS_PATH not found in .env file")
                print(f"DEBUG: Available environment variables: {env_vars}")
                return False

            print(f"DEBUG: Models path from .env: {models_path}")

            # Define source and destination paths
            source_path = Path(source_dir) / "required_files" / "Comfyui files" / "models" / "upscale_models" / "4x-ClearRealityV1.pth"
            dest_path = Path(models_path) / "upscale_models" / "4x-ClearRealityV1.pth"

            # Convert to absolute paths and resolve any .. or .
            source_path = source_path.resolve()
            dest_path = dest_path.resolve()

            print(f"DEBUG: Source path: {source_path}")
            print(f"DEBUG: Source exists: {source_path.exists()}")
            print(f"DEBUG: Destination path: {dest_path}")

            # List contents of source directory
            try:
                parent_dir = source_path.parent
                if parent_dir.exists():
                    print(f"\nDEBUG: Contents of {parent_dir}:")
                    for item in parent_dir.iterdir():
                        print(f"DEBUG:   {item.name}")
                else:
                    print(f"DEBUG: Source directory does not exist: {parent_dir}")
            except Exception as e:
                print(f"DEBUG: Error listing source directory: {e}")

            # Verify source exists
            if not source_path.is_file():
                print(f"DEBUG: Source file not found at: {source_path}")
                # Try to find the file in the source directory
                try:
                    for root, dirs, files in os.walk(source_dir):
                        if "4x-ClearRealityV1.pth" in files:
                            found_path = Path(root) / "4x-ClearRealityV1.pth"
                            print(f"DEBUG: Found file at alternate location: {found_path}")
                            source_path = found_path
                            break
                    else:
                        print("DEBUG: File not found in any subdirectory")
                        return False
                except Exception as e:
                    print(f"DEBUG: Error searching for file: {e}")
                    return False

            # Create destination directory
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"DEBUG: Created destination directory: {dest_path.parent}")
            except Exception as e:
                print(f"DEBUG: Error creating destination directory: {e}")
                return False

            # Copy file
            try:
                print("DEBUG: Attempting to copy file...")
                print(f"DEBUG: Source path type: {type(source_path)}, Destination path type: {type(dest_path)}")
                print(f"DEBUG: Source path exists: {source_path.exists()}")
                print(f"DEBUG: Source path is file: {source_path.is_file()}")
                print(f"DEBUG: Destination directory exists: {dest_path.parent.exists()}")
                print(f"DEBUG: Destination directory is writable: {os.access(str(dest_path.parent), os.W_OK)}")
                shutil.copy2(str(source_path), str(dest_path))
                print("DEBUG: Copy operation completed")
            except Exception as e:
                print(f"DEBUG: Error during copy operation: {e}")
                print(f"DEBUG: Full error details:", exc_info=True)
                return False
            
            # Verify copy was successful
            if dest_path.is_file():
                print(f"DEBUG: Successfully copied upscaler to: {dest_path}")
                return True
            else:
                print("DEBUG: Failed to verify upscaler copy")
                return False

        except Exception as e:
            print(f"DEBUG: Error in copy_upscaler: {str(e)}")
            return False

    def copy_ratios_json(self, source_dir: str, dest_dir: str) -> bool:
        """
        Copy the ratios.json file to its destination in ComfyUI/custom_nodes/mikey_nodes.
        Uses COMFYUI_MODELS_PATH from .env as base path.
        """
        try:
            print("\nDEBUG: Starting copy_ratios_json")
            
            # Load the models path from .env
            try:
                with open('.env', 'r') as f:
                    env_content = f.read()
                    print(f"DEBUG: .env file contents:\n{env_content}")
            except Exception as e:
                print(f"DEBUG: Error reading .env file: {e}")
                return False

            # Use COMFYUI_DIR directly instead of deriving from MODELS_PATH
            comfyui_path = None
            for line in env_content.splitlines():
                if line.startswith('COMFYUI_DIR='):
                    comfyui_path = line.split('=', 1)[1].strip().strip('"')
                    break

            if not comfyui_path:
                print("DEBUG: COMFYUI_DIR not found in .env file")
                return False

            print(f"DEBUG: ComfyUI path: {comfyui_path}")
            
            # Define source and destination paths using consistent separators
            source_path = os.path.join(source_dir, "required_files", "ratios.json")
            dest_path = os.path.join(comfyui_path, "ComfyUI", "custom_nodes", "mikey_nodes", "ratios.json")

            # Convert to absolute paths
            source_path = os.path.abspath(source_path)
            dest_path = os.path.abspath(dest_path)

            print(f"DEBUG: Source path: {source_path}")
            print(f"DEBUG: Source exists: {os.path.exists(source_path)}")
            print(f"DEBUG: Destination path: {dest_path}")

            # Create destination directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            print(f"DEBUG: Created/verified destination directory: {os.path.dirname(dest_path)}")

            # Remove existing file if it exists
            if os.path.exists(dest_path):
                print(f"DEBUG: Removing existing file at: {dest_path}")
                try:
                    os.remove(dest_path)
                    print("DEBUG: Successfully removed existing file")
                except Exception as e:
                    print(f"DEBUG: Error removing existing file: {e}")
                    return False

            # Verify source exists
            if not os.path.isfile(source_path):
                print(f"DEBUG: Source file not found at: {source_path}")
                return False

            # Copy file using shutil.copy2
            try:
                print("DEBUG: Attempting to copy file...")
                shutil.copy2(source_path, dest_path)
                print("DEBUG: Copy operation completed")
            except Exception as e:
                print(f"DEBUG: Error during copy operation: {e}")
                return False
            
            # Verify copy was successful
            if os.path.isfile(dest_path):
                print(f"DEBUG: Successfully copied ratios.json to: {dest_path}")
                return True
            else:
                print("DEBUG: Failed to verify ratios.json copy")
                return False

        except Exception as e:
            print(f"DEBUG: Error in copy_ratios_json: {str(e)}")
            return False