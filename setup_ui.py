import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from setup_support import SetupManager, BASE_MODELS, CHECKPOINTS
import os
import logging
from pathlib import Path

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/setup.log', mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class SetupUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FLUX ComfyUI Setup")
        self.root.geometry("800x820")
        self.setup_manager = SetupManager()
        
        # Variables
        self.base_dir = tk.StringVar()
        self.hf_token = tk.StringVar()
        self.civitai_token = tk.StringVar()
        self.discord_token = tk.StringVar()
        self.selected_checkpoint = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Welcome to FLUX ComfyUI Setup")
        
        # Address variables
        self.bot_server = tk.StringVar()
        self.server_address = tk.StringVar()
        
        # Discord configuration variables
        self.allowed_servers = tk.StringVar()
        self.channel_ids = tk.StringVar()
        self.bot_manager_role_id = tk.StringVar()
        
        # Load existing values
        self.load_existing_values()
        
        self.create_ui()
        self.center_window()

    def load_existing_values(self):
        """Load existing values from .env file"""
        try:
            env_vars = self.setup_manager.load_env()
            
            # Load API tokens
            if 'HUGGINGFACE_TOKEN' in env_vars:
                self.hf_token.set(env_vars['HUGGINGFACE_TOKEN'])
            if 'CIVITAI_API_TOKEN' in env_vars:
                self.civitai_token.set(env_vars['CIVITAI_API_TOKEN'])
            if 'DISCORD_TOKEN' in env_vars:
                self.discord_token.set(env_vars['DISCORD_TOKEN'])
            
            # Load paths
            if 'COMFYUI_MODELS_PATH' in env_vars:
                base_path = Path(env_vars['COMFYUI_MODELS_PATH']).parent.parent
                self.base_dir.set(str(base_path))
            
            # Load addresses
            if 'BOT_SERVER' in env_vars:
                self.bot_server.set(env_vars['BOT_SERVER'].strip('"'))
            if 'server_address' in env_vars:
                self.server_address.set(env_vars['server_address'].strip('"'))
            
            # Load Discord configuration
            if 'ALLOWED_SERVERS' in env_vars:
                self.allowed_servers.set(env_vars['ALLOWED_SERVERS'])
            if 'CHANNEL_IDS' in env_vars:
                self.channel_ids.set(env_vars['CHANNEL_IDS'])
            if 'BOT_MANAGER_ROLE_ID' in env_vars:
                self.bot_manager_role_id.set(env_vars['BOT_MANAGER_ROLE_ID'])
                
        except Exception as e:
            logger.error(f"Error loading existing values: {str(e)}")

    def create_ui(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        current_row = 0

        # Base Directory Section
        ttk.Label(main_frame, text="ComfyUI Base Directory:", font=('Helvetica', 10, 'bold')).grid(row=current_row, column=0, sticky="w", pady=(0, 5))
        ttk.Label(main_frame, text="(Should contain 'ComfyUI' and 'python_embedded' folders)", font=('Helvetica', 8)).grid(row=current_row + 1, column=0, columnspan=2, sticky="w")
        ttk.Entry(main_frame, textvariable=self.base_dir, width=50).grid(row=current_row + 2, column=0, columnspan=2, sticky="ew", padx=(0, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_directory).grid(row=current_row + 2, column=2, sticky="w")
        current_row += 3

        # Token Section
        token_frame = ttk.LabelFrame(main_frame, text="API Tokens", padding="10")
        token_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew", pady=20)
        
        # Hugging Face Token
        ttk.Label(token_frame, text="Hugging Face Token:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(token_frame, textvariable=self.hf_token, width=40, show="*").grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(token_frame, text="Validate", command=lambda: self.validate_token("hf")).grid(row=0, column=2)

        # CivitAI Token
        ttk.Label(token_frame, text="CivitAI Token:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(token_frame, textvariable=self.civitai_token, width=40, show="*").grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(token_frame, text="Validate", command=lambda: self.validate_token("civitai")).grid(row=1, column=2)

        # Discord Token
        ttk.Label(token_frame, text="Discord Token:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(token_frame, textvariable=self.discord_token, width=40, show="*").grid(row=2, column=1, sticky="ew", padx=5)
        current_row += 1

        # Address Section
        address_frame = ttk.LabelFrame(main_frame, text="Server Addresses", padding="10")
        address_frame.grid(row=current_row + 1, column=0, columnspan=3, sticky="ew", pady=10)
        
        ttk.Label(address_frame, text="Bot Server Address:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(address_frame, textvariable=self.bot_server, width=40).grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(address_frame, text="ComfyUI Server Address:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(address_frame, textvariable=self.server_address, width=40).grid(row=1, column=1, sticky="ew", padx=5)
        current_row += 2

        # Discord Configuration Section
        discord_frame = ttk.LabelFrame(main_frame, text="Discord Configuration", padding="10")
        discord_frame.grid(row=current_row + 1, column=0, columnspan=3, sticky="ew", pady=10)
        
        ttk.Label(discord_frame, text="Allowed Server IDs:").grid(row=0, column=0, sticky="nw", pady=5)
        servers_text = tk.Text(discord_frame, height=3, width=40, wrap=tk.WORD)
        servers_text.grid(row=0, column=1, sticky="ew", padx=5)
        
        def update_servers_var(*args):
            self.allowed_servers.set(servers_text.get("1.0", "end-1c"))
        servers_text.bind('<KeyRelease>', update_servers_var)
        if self.allowed_servers.get():
            servers_text.insert("1.0", self.allowed_servers.get())
        
        servers_scroll = ttk.Scrollbar(discord_frame, orient="vertical", command=servers_text.yview)
        servers_scroll.grid(row=0, column=2, sticky="ns")
        servers_text.config(yscrollcommand=servers_scroll.set)
        
        ttk.Label(discord_frame, text="Channel IDs:").grid(row=1, column=0, sticky="nw", pady=5)
        channels_text = tk.Text(discord_frame, height=3, width=40, wrap=tk.WORD)
        channels_text.grid(row=1, column=1, sticky="ew", padx=5)
        
        def update_channels_var(*args):
            self.channel_ids.set(channels_text.get("1.0", "end-1c"))
        channels_text.bind('<KeyRelease>', update_channels_var)
        if self.channel_ids.get():
            channels_text.insert("1.0", self.channel_ids.get())
        
        channels_scroll = ttk.Scrollbar(discord_frame, orient="vertical", command=channels_text.yview)
        channels_scroll.grid(row=1, column=2, sticky="ns")
        channels_text.config(yscrollcommand=channels_scroll.set)
        
        ttk.Label(discord_frame, text="Bot Manager Role ID:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(discord_frame, textvariable=self.bot_manager_role_id, width=40).grid(row=2, column=1, sticky="ew", padx=5)
        current_row += 3

        # Checkpoint Selection
        checkpoint_frame = ttk.LabelFrame(main_frame, text="Checkpoint Selection", padding="10")
        checkpoint_frame.grid(row=current_row + 1, column=0, columnspan=3, sticky="ew", pady=10)
        
        ttk.Label(checkpoint_frame, text="Select Checkpoint:").grid(row=0, column=0, sticky="w", pady=5)
        checkpoint_combo = ttk.Combobox(checkpoint_frame, textvariable=self.selected_checkpoint, width=40)
        checkpoint_combo['values'] = list(CHECKPOINTS.keys())
        checkpoint_combo.grid(row=0, column=1, sticky="ew", padx=5)
        checkpoint_combo.set("Select a checkpoint...")
        current_row += 4

        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=current_row + 1, column=0, columnspan=3, sticky="ew", pady=10)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var,
            maximum=100,
            length=300,
            mode='determinate'
        )
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Status Label
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=current_row + 2, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Install", command=self.start_installation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.root.quit).pack(side=tk.LEFT, padx=5)

        # Configure column weights for the frames
        for frame in [token_frame, address_frame, discord_frame, checkpoint_frame, progress_frame]:
            frame.grid_columnconfigure(1, weight=1)

    def center_window(self):
        """Center the window on the screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def browse_directory(self):
        """Open directory browser dialog"""
        try:
            directory = filedialog.askdirectory(title="Select ComfyUI Base Directory")
            if directory:
                # List directory contents before validation
                contents = [f for f in os.listdir(directory)]
                logger.debug(f"Selected directory contents: {contents}")
                
                if self.setup_manager.validator.validate_comfyui_directory(directory):
                    self.base_dir.set(directory)
                    paths = self.setup_manager.validator.setup_required_paths(directory)
                    self.setup_manager.models_path = paths['models_dir']
                    self.setup_manager.base_dir = directory
                else:
                    error_msg = f"Selected directory must contain 'ComfyUI' and 'python_embeded' folders.\nFound: {contents}"
                    logger.error(error_msg)
                    messagebox.showerror("Error", error_msg)
        except Exception as e:
            logger.error(f"Error validating directory: {str(e)}")
            messagebox.showerror("Error", f"Error validating directory: {str(e)}")

    def validate_token(self, token_type):
        """Validate the specified token"""
        token = self.hf_token.get() if token_type == "hf" else self.civitai_token.get()
        
        try:
            if token_type == "hf":
                is_valid = self.setup_manager.validate_huggingface_token(token)
                token_name = "Hugging Face"
            else:
                is_valid = self.setup_manager.validate_civitai_token(token)
                token_name = "CivitAI"

            if is_valid:
                messagebox.showinfo("Success", f"{token_name} token is valid!")
            else:
                messagebox.showerror("Error", f"Invalid {token_name} token")
        except Exception as e:
            messagebox.showerror("Error", f"Error validating token: {str(e)}")

    def update_progress(self, value, status=""):
        """Update progress bar and status label"""
        try:
            self.progress_var.set(value)
            if status:
                self.status_var.set(status)
                logger.debug(f"Progress update: {value}%, Status: {status}")
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}")

    def update_download_progress(self, progress):
        """Callback for download progress updates"""
        try:
            self.progress_var.set(progress)
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error updating download progress: {str(e)}")

    def save_configuration(self):
        """Save all configuration values to .env"""
        try:
            env_vars = self.setup_manager.load_env()
            
            # Update API tokens
            if self.hf_token.get():
                env_vars['HUGGINGFACE_TOKEN'] = self.hf_token.get()
            if self.civitai_token.get():
                env_vars['CIVITAI_API_TOKEN'] = self.civitai_token.get()
            if self.discord_token.get():
                env_vars['DISCORD_TOKEN'] = self.discord_token.get()
                
            # Update paths
            if self.setup_manager.models_path:
                env_vars['COMFYUI_MODELS_PATH'] = self.setup_manager.models_path
                
            # Update addresses
            if self.bot_server.get():
                env_vars['BOT_SERVER'] = self.bot_server.get()
            if self.server_address.get():
                env_vars['server_address'] = self.server_address.get()
                
            # Update Discord configuration
            if self.allowed_servers.get():
                env_vars['ALLOWED_SERVERS'] = self.allowed_servers.get()
            if self.channel_ids.get():
                env_vars['CHANNEL_IDS'] = self.channel_ids.get()
            if self.bot_manager_role_id.get():
                env_vars['BOT_MANAGER_ROLE_ID'] = self.bot_manager_role_id.get()
                
            # Save all values
            self.setup_manager.save_env(env_vars)
            logger.info("Configuration saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            raise

    def start_installation(self):
        """Start the installation process"""
        if not self.base_dir.get():
            messagebox.showerror("Error", "Please select ComfyUI Base Directory")
            return

        # Validate directory structure
        if not self.setup_manager.validator.validate_comfyui_directory(self.base_dir.get()):
            messagebox.showerror("Error", "Invalid ComfyUI directory structure")
            return

        # Save configuration before starting installation
        try:
            self.save_configuration()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            return

        # Disable UI elements during installation
        self.disable_ui()
        
        # Start installation in a separate thread
        thread = threading.Thread(target=self.run_installation)
        thread.daemon = True
        thread.start()

    def disable_ui(self):
        """Disable UI elements during installation"""
        for child in self.root.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                child.configure(state='disabled')

    def enable_ui(self):
        """Enable UI elements after installation"""
        for child in self.root.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                child.configure(state='normal')

    def run_installation(self):
        """Run the installation process"""
        try:
            # Set up manager properties
            self.setup_manager.models_path = os.path.join(self.base_dir.get(), "ComfyUI", "models")
            self.setup_manager.hf_token = self.hf_token.get()
            self.setup_manager.civitai_token = self.civitai_token.get()
            self.setup_manager.progress_callback = self.update_download_progress
            
            # Copy gguf_reader.py
            self.update_progress(10, "Copying required files...")
            if not self.setup_manager.validator.copy_gguf_reader(os.getcwd(), self.base_dir.get()):
                raise Exception("Failed to copy gguf_reader.py")

            # Copy upscaler model
            self.update_progress(20, "Copying upscaler model...")
            if not self.setup_manager.validator.copy_upscaler(os.getcwd(), self.base_dir.get()):
                raise Exception("Failed to copy upscaler model")

            # Copy ratios.json
            self.update_progress(30, "Copying ratios.json...")
            if not self.setup_manager.validator.copy_ratios_json(os.getcwd(), self.base_dir.get()):
                raise Exception("Failed to copy ratios.json")

            # Save all configuration values
            self.save_configuration()
            
            # Process base models
            total_models = len(BASE_MODELS)
            for index, (model_name, model_info) in enumerate(BASE_MODELS.items(), 1):
                self.update_progress(0, f"Processing {model_name} ({index}/{total_models})...")
                
                model_path = os.path.join(
                    self.setup_manager.models_path,
                    model_info['path'].strip('/'),
                    model_info['filename']
                )
                
                if os.path.exists(model_path):
                    self.update_progress(100, f"{model_name} already exists, skipping...")
                    continue
                    
                self.update_progress(0, f"Downloading {model_name} from {model_info['source']}...")
                
                try:
                    token = self.hf_token.get() if model_info['source'] == 'huggingface' else self.civitai_token.get()
                    self.setup_manager.download_file(
                        file_info=model_info,
                        output_path=model_path,
                        token=token,
                        source=model_info['source']
                    )
                    self.update_progress(100, f"Successfully downloaded {model_name}")
                except Exception as e:
                    logger.error(f"Error downloading {model_name}: {str(e)}")
                    raise

            # Download selected checkpoint if one is selected
            if self.selected_checkpoint.get() and self.selected_checkpoint.get() != "Select a checkpoint...":
                checkpoint_info = CHECKPOINTS[self.selected_checkpoint.get()]
                self.update_progress(0, f"Processing checkpoint {self.selected_checkpoint.get()}...")
                
                checkpoint_path = os.path.join(
                    self.setup_manager.models_path,
                    checkpoint_info['path'].strip('/'),
                    checkpoint_info['filename']
                )
                
                if os.path.exists(checkpoint_path):
                    self.update_progress(100, f"Checkpoint already exists, skipping...")
                else:
                    self.update_progress(0, f"Downloading checkpoint from {checkpoint_info['source']}...")
                    token = self.hf_token.get() if checkpoint_info['source'] == 'huggingface' else self.civitai_token.get()
                    
                    try:
                        self.setup_manager.download_file(
                            file_info=checkpoint_info,
                            output_path=checkpoint_path,
                            token=token,
                            source=checkpoint_info['source']
                        )
                        self.update_progress(100, f"Successfully downloaded checkpoint")
                    except Exception as e:
                        logger.error(f"Error downloading checkpoint: {str(e)}")
                        raise

                # Update .env file with workflow
                self.status_var.set("Updating configuration...")
                self.setup_manager.update_env_file(checkpoint_info['workflow'])

            # Complete
            self.update_progress(100, "Installation completed successfully!")
            messagebox.showinfo("Success", "Installation completed successfully!")
            
        except Exception as e:
            logger.error(f"Installation failed: {str(e)}")
            messagebox.showerror("Error", f"Installation failed: {str(e)}")
        finally:
            self.enable_ui()

def main():
    root = tk.Tk()
    app = SetupUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()