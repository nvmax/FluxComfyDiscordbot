import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from setup_support import SetupManager, BASE_MODELS, CHECKPOINTS
import os
import logging
from pathlib import Path
import asyncio
import requests
import shutil

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
        self.root.title("FluxComfy Setup")
        
        # Initialize setup manager
        self.setup_manager = SetupManager()
        
        # Create variables for form fields
        self.create_variables()
        
        # Create main UI
        self.create_ui()
        
        # Load existing values
        self.load_existing_values()
        
    def create_variables(self):
        # Bot Setup Variables
        self.base_dir = tk.StringVar()
        self.hf_token = tk.StringVar()
        self.civitai_token = tk.StringVar()
        self.discord_token = tk.StringVar()
        self.bot_server = tk.StringVar(value="")
        self.server_address = tk.StringVar(value="")
        self.allowed_servers = tk.StringVar()
        self.channel_ids = tk.StringVar()
        self.bot_manager_role_id = tk.StringVar()
        self.selected_checkpoint = tk.StringVar(value="Select a checkpoint...")
        
        # Progress tracking
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Ready to install")
        
        # AI Setup Variables
        self.ai_provider = tk.StringVar(value="lmstudio")
        self.enable_prompt_enhancement = tk.BooleanVar(value=False)
        self.lmstudio_host = tk.StringVar(value="")
        self.lmstudio_port = tk.StringVar(value="")
        self.gemini_api_key = tk.StringVar()
        self.xai_api_key = tk.StringVar()
        self.openai_api_key = tk.StringVar()
        
    def create_ui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create Bot Setup tab
        self.bot_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.bot_tab, text='Bot Setup')
        self.create_bot_tab()
        
        # Create AI Setup tab
        self.ai_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.ai_tab, text='AI Setup')
        self.create_ai_tab()
        
    def create_bot_tab(self):
        # Initialize StringVars if not already done
        if not hasattr(self, 'allowed_servers'):
            self.allowed_servers = tk.StringVar()
        if not hasattr(self, 'channel_ids'):
            self.channel_ids = tk.StringVar()
            
        # Load existing values before creating UI
        self.load_existing_values()
        
        # Directory Selection
        dir_frame = ttk.LabelFrame(self.bot_tab, text="ComfyUI Directory", padding=10)
        dir_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(dir_frame, text="Base Directory:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(dir_frame, textvariable=self.base_dir, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(dir_frame, text="Browse", command=self.select_base_directory).pack(side=tk.LEFT, padx=5)
        
        # API Tokens
        token_frame = ttk.LabelFrame(self.bot_tab, text="API Tokens", padding=10)
        token_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # HuggingFace Token
        hf_frame = ttk.Frame(token_frame)
        hf_frame.pack(fill=tk.X, pady=2)
        ttk.Label(hf_frame, text="HuggingFace Token:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(hf_frame, textvariable=self.hf_token, width=40, show="*").pack(side=tk.LEFT, padx=5)
        ttk.Button(hf_frame, text="Validate", command=lambda: self.validate_token("hf")).pack(side=tk.LEFT, padx=5)
        
        # CivitAI Token
        civitai_frame = ttk.Frame(token_frame)
        civitai_frame.pack(fill=tk.X, pady=2)
        ttk.Label(civitai_frame, text="CivitAI Token:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(civitai_frame, textvariable=self.civitai_token, width=40, show="*").pack(side=tk.LEFT, padx=5)
        ttk.Button(civitai_frame, text="Validate", command=lambda: self.validate_token("civitai")).pack(side=tk.LEFT, padx=5)
        
        # Discord Token
        discord_frame = ttk.Frame(token_frame)
        discord_frame.pack(fill=tk.X, pady=2)
        ttk.Label(discord_frame, text="Discord Token:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(discord_frame, textvariable=self.discord_token, width=40, show="*").pack(side=tk.LEFT, padx=5)
        
        # Server Configuration
        server_frame = ttk.LabelFrame(self.bot_tab, text="Server Configuration", padding=10)
        server_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Bot Server
        bot_server_frame = ttk.Frame(server_frame)
        bot_server_frame.pack(fill=tk.X, pady=2)
        ttk.Label(bot_server_frame, text="Bot Server:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(bot_server_frame, textvariable=self.bot_server, width=40).pack(side=tk.LEFT, padx=5)
        
        # Server Address
        server_addr_frame = ttk.Frame(server_frame)
        server_addr_frame.pack(fill=tk.X, pady=2)
        ttk.Label(server_addr_frame, text="Server Address:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(server_addr_frame, textvariable=self.server_address, width=40).pack(side=tk.LEFT, padx=5)
        
        # Discord Configuration
        discord_config_frame = ttk.LabelFrame(self.bot_tab, text="Discord Configuration", padding=10)
        discord_config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Allowed Servers
        allowed_servers_frame = ttk.Frame(discord_config_frame)
        allowed_servers_frame.pack(fill=tk.X, pady=2)
        ttk.Label(allowed_servers_frame, text="Allowed Server IDs:").pack(side=tk.LEFT, padx=5)
        server_ids_entry = tk.Text(allowed_servers_frame, height=3, width=80)
        server_ids_entry.pack(side=tk.LEFT, padx=5)
        
        # Set initial value from StringVar
        if self.allowed_servers.get():
            server_ids_entry.insert("1.0", self.allowed_servers.get())
            
        # Bind the Text widget to the StringVar
        def update_allowed_servers(*args):
            current_text = server_ids_entry.get("1.0", "end-1c")
            if self.allowed_servers.get() != current_text:
                self.allowed_servers.set(current_text)
        server_ids_entry.bind('<KeyRelease>', update_allowed_servers)
        
        # Channel IDs
        channel_ids_frame = ttk.Frame(discord_config_frame)
        channel_ids_frame.pack(fill=tk.X, pady=2)
        ttk.Label(channel_ids_frame, text="Channel IDs:").pack(side=tk.LEFT, padx=5)
        channel_ids_entry = tk.Text(channel_ids_frame, height=3, width=80)
        channel_ids_entry.pack(side=tk.LEFT, padx=5)
        
        # Set initial value from StringVar
        if self.channel_ids.get():
            channel_ids_entry.insert("1.0", self.channel_ids.get())
            
        # Bind the Text widget to the StringVar
        def update_channel_ids(*args):
            current_text = channel_ids_entry.get("1.0", "end-1c")
            if self.channel_ids.get() != current_text:
                self.channel_ids.set(current_text)
        channel_ids_entry.bind('<KeyRelease>', update_channel_ids)
        
        # Bot Manager Role
        role_frame = ttk.Frame(discord_config_frame)
        role_frame.pack(fill=tk.X, pady=2)
        ttk.Label(role_frame, text="Bot Manager Role ID:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(role_frame, textvariable=self.bot_manager_role_id, width=40).pack(side=tk.LEFT, padx=5)
        
        # Workflow Selection
        workflow_frame = ttk.LabelFrame(self.bot_tab, text="Workflow Selection", padding=10)
        workflow_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(workflow_frame, text="Select Workflow:").pack(side=tk.LEFT, padx=5)
        
        # Get list of workflow files
        datasets_path = os.path.join(os.getcwd(), 'Main', 'Datasets')
        workflow_files = []
        if os.path.exists(datasets_path):
            for file in os.listdir(datasets_path):
                if file.endswith('.json') and file not in ['lora.json', 'ratios.json', 'Redux.json', 'Reduxprompt.json']:
                    workflow_files.append(file)
        
        workflow_combo = ttk.Combobox(workflow_frame, textvariable=self.selected_checkpoint, 
                                    values=sorted(workflow_files), state="readonly", width=40)
        workflow_combo.pack(side=tk.LEFT, padx=5)
        workflow_combo.bind("<<ComboboxSelected>>", self.on_checkpoint_selected)
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(self.bot_tab, text="Installation Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Status label
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.pack(fill=tk.X, padx=5)
        
        # Install Button
        install_frame = ttk.Frame(self.bot_tab)
        install_frame.pack(fill=tk.X, padx=5, pady=10)
        self.install_button = ttk.Button(install_frame, text="Install", command=self.start_installation)
        self.install_button.pack(side=tk.LEFT, padx=5)
        
    def create_ai_tab(self):
        # AI Provider Selection
        provider_frame = ttk.LabelFrame(self.ai_tab, text="AI Configuration", padding=10)
        provider_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # AI Provider dropdown
        provider_select_frame = ttk.Frame(provider_frame)
        provider_select_frame.pack(fill=tk.X, pady=2)
        ttk.Label(provider_select_frame, text="AI Provider:").pack(side=tk.LEFT, padx=5)
        ttk.Combobox(provider_select_frame, textvariable=self.ai_provider,
                    values=["lmstudio", "openai", "xai", "gemini"], state="readonly", width=20).pack(side=tk.LEFT, padx=5)
        
        # Enable Prompt Enhancement checkbox
        enhance_frame = ttk.Frame(provider_frame)
        enhance_frame.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(enhance_frame, text="Enable Prompt Enhancement",
                       variable=self.enable_prompt_enhancement).pack(side=tk.LEFT, padx=5)
        
        # LMStudio Configuration
        lmstudio_frame = ttk.LabelFrame(self.ai_tab, text="LMStudio Configuration", padding=10)
        lmstudio_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Host
        host_frame = ttk.Frame(lmstudio_frame)
        host_frame.pack(fill=tk.X, pady=2)
        ttk.Label(host_frame, text="LMStudio Host:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(host_frame, textvariable=self.lmstudio_host, width=30).pack(side=tk.LEFT, padx=5)
        
        # Port
        port_frame = ttk.Frame(lmstudio_frame)
        port_frame.pack(fill=tk.X, pady=2)
        ttk.Label(port_frame, text="LMStudio Port:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(port_frame, textvariable=self.lmstudio_port, width=10).pack(side=tk.LEFT, padx=5)
        
        # API Keys
        api_frame = ttk.LabelFrame(self.ai_tab, text="API Keys", padding=10)
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # XAI API Key
        xai_frame = ttk.Frame(api_frame)
        xai_frame.pack(fill=tk.X, pady=2)
        ttk.Label(xai_frame, text="XAI API Key:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(xai_frame, textvariable=self.xai_api_key, width=40, show="*").pack(side=tk.LEFT, padx=5)

        # Gemini API Key
        gemini_frame = ttk.Frame(api_frame)
        gemini_frame.pack(fill=tk.X, pady=2)
        ttk.Label(gemini_frame, text="Gemini API Key:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(gemini_frame, textvariable=self.gemini_api_key, width=40, show="*").pack(side=tk.LEFT, padx=5)
        
        # OpenAI API Key
        openai_frame = ttk.Frame(api_frame)
        openai_frame.pack(fill=tk.X, pady=2)
        ttk.Label(openai_frame, text="OpenAI API Key:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(openai_frame, textvariable=self.openai_api_key, width=40, show="*").pack(side=tk.LEFT, padx=5)
        
        # Add save button at the bottom
        ttk.Button(self.ai_tab, text="Save AI Configuration", 
                  command=self.save_ai_configuration).pack(pady=10)
        
    def select_base_directory(self):
        directory = filedialog.askdirectory(title="Select ComfyUI Base Directory")
        if directory:
            self.base_dir.set(directory)
            self.setup_manager.base_dir = directory
            
            # Construct and save the models path to .env
            models_path = os.path.join(directory, "ComfyUI", "models")
            self.setup_manager.update_env_file('COMFYUI_MODELS_PATH', f'"{models_path}"')
            
            # Update the status label
            self.status_label.config(text=f"ComfyUI directory set to: {directory}\nModels path set to: {models_path}")
            
    def validate_token(self, token_type):
        """Validate API tokens with better error handling"""
        token = self.hf_token.get() if token_type == "hf" else self.civitai_token.get()
        
        if not token:
            messagebox.showwarning("Token Required", f"Please enter a {token_type.upper()} token")
            return False
        
        try:
            if token_type == "hf":
                # First check if we've already successfully downloaded files
                if hasattr(self.setup_manager, 'download_success') and self.setup_manager.download_success:
                    messagebox.showinfo("Success", "Token has been verified through successful downloads!")
                    return True
                    
                # Try file access without API validation
                headers = {'Authorization': f'Bearer {token}'}
                test_url = 'https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors'
                
                try:
                    response = requests.head(test_url, headers=headers, allow_redirects=True, verify=False)
                    if response.status_code == 200:
                        messagebox.showinfo("Success", "HuggingFace token is valid!")
                        return True
                except:
                    pass
                
                # Only try API validation as a last resort
                try:
                    api = HfApi(token=token)
                    user = api.whoami()
                    if user is not None:
                        messagebox.showinfo("Success", "HuggingFace token is valid!")
                        return True
                except:
                    pass
                
                messagebox.showerror("Error", "Could not validate token. However, if you're able to download files, you can proceed with the installation.")
                return False
                    
            elif token_type == "civitai":
                # Use SetupManager's CivitAI validation
                if self.setup_manager.validate_civitai_token(token):
                    messagebox.showinfo("Success", "CivitAI token is valid!")
                    return True
                else:
                    messagebox.showerror("Error", "Invalid CivitAI token. Check the logs for details.")
                    return False
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to validate {token_type.upper()} token: {str(e)}")
            return False

    def save_configuration(self):
        """Save configuration with better error handling"""
        try:
            # Load existing environment variables
            env_vars = self.setup_manager.load_env()
            
            # Update with new values, only if they are not empty
            tokens = {
                'HUGGINGFACE_TOKEN': self.hf_token.get(),
                'CIVITAI_API_TOKEN': self.civitai_token.get(),
                'DISCORD_TOKEN': self.discord_token.get(),
                'XAI_API_KEY': self.xai_api_key.get(),
                'OPENAI_API_KEY': self.openai_api_key.get(),
                'GEMINI_API_KEY': self.gemini_api_key.get()
            }
            
            # Only update tokens that have values
            for key, value in tokens.items():
                if value:
                    env_vars[key] = value
            
            # Update other configuration
            env_vars.update({
                'AI_PROVIDER': self.ai_provider.get(),
                'ENABLE_PROMPT_ENHANCEMENT': str(self.enable_prompt_enhancement.get()),
                'LMSTUDIO_HOST': self.lmstudio_host.get(),
                'LMSTUDIO_PORT': self.lmstudio_port.get(),
                'BOT_SERVER': self.bot_server.get(),
                'server_address': self.server_address.get(),
                'ALLOWED_SERVERS': self.allowed_servers.get(),
                'CHANNEL_IDS': self.channel_ids.get(),
                'BOT_MANAGER_ROLE_ID': self.bot_manager_role_id.get(),
                'XAI_MODEL': 'grok-beta',
                'OPENAI_MODEL': 'gpt-3.5-turbo',
                'EMBEDDING_MODEL': 'text-embedding-ada-002'
            })
            
            # Save the configuration
            if self.setup_manager.save_env(env_vars):
                messagebox.showinfo("Success", "Configuration saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save configuration")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            
    def load_existing_values(self):
        try:
            env_vars = self.setup_manager.load_env()
            
            # Load API tokens
            if 'HUGGINGFACE_TOKEN' in env_vars:
                self.hf_token.set(env_vars['HUGGINGFACE_TOKEN'])
            if 'CIVITAI_API_TOKEN' in env_vars:
                self.civitai_token.set(env_vars['CIVITAI_API_TOKEN'])
            if 'DISCORD_TOKEN' in env_vars:
                self.discord_token.set(env_vars['DISCORD_TOKEN'])
            if 'GEMINI_API_KEY' in env_vars:
                self.gemini_api_key.set(env_vars['GEMINI_API_KEY'])
            if 'XAI_API_KEY' in env_vars:
                self.xai_api_key.set(env_vars['XAI_API_KEY'])
            if 'OPENAI_API_KEY' in env_vars:
                self.openai_api_key.set(env_vars['OPENAI_API_KEY'])
                
            # Load paths
            if 'COMFYUI_MODELS_PATH' in env_vars:
                base_path = Path(env_vars['COMFYUI_MODELS_PATH']).parent.parent
                self.base_dir.set(str(base_path))
                self.setup_manager.base_dir = str(base_path)
            
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
                
            # Load AI configuration
            if 'AI_PROVIDER' in env_vars:
                self.ai_provider.set(env_vars['AI_PROVIDER'])
            if 'ENABLE_PROMPT_ENHANCEMENT' in env_vars:
                self.enable_prompt_enhancement.set(env_vars['ENABLE_PROMPT_ENHANCEMENT'] == 'True')
            if 'LMSTUDIO_HOST' in env_vars:
                self.lmstudio_host.set(env_vars['LMSTUDIO_HOST'])
            if 'LMSTUDIO_PORT' in env_vars:
                self.lmstudio_port.set(env_vars['LMSTUDIO_PORT'])
            if 'XAI_API_KEY' in env_vars:
                self.xai_api_key.set(env_vars['XAI_API_KEY'])
            if 'OPENAI_API_KEY' in env_vars:
                self.openai_api_key.set(env_vars['OPENAI_API_KEY'])
                
        except Exception as e:
            logger.error(f"Error loading existing values: {str(e)}")
            
    def save_ai_configuration(self):
        try:
            env_vars = self.setup_manager.load_env()
            
            # Save AI configuration
            env_vars['AI_PROVIDER'] = self.ai_provider.get()
            env_vars['ENABLE_PROMPT_ENHANCEMENT'] = str(self.enable_prompt_enhancement.get())
            env_vars['LMSTUDIO_HOST'] = self.lmstudio_host.get()
            env_vars['LMSTUDIO_PORT'] = self.lmstudio_port.get()
            env_vars['XAI_API_KEY'] = self.xai_api_key.get()
            env_vars['OPENAI_API_KEY'] = self.openai_api_key.get()
            env_vars['GEMINI_API_KEY'] = self.gemini_api_key.get()
            
            # Save all values
            if self.setup_manager.save_env(env_vars):
                logger.info("AI configuration saved successfully")
                messagebox.showinfo("Success", "AI configuration saved successfully!")
            else:
                logger.error("Failed to save AI configuration")
                messagebox.showerror("Error", "Failed to save AI configuration")
            
        except Exception as e:
            logger.error(f"Error saving AI configuration: {str(e)}")
            messagebox.showerror("Error", f"Error saving AI configuration: {str(e)}")
            raise
            
    def update_progress(self, value, status=""):
        """Update progress bar and status label"""
        try:
            self.progress_var.set(value)
            if status:
                self.status_var.set(status)
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}")

    def update_download_progress(self, progress, status=None):
        """Callback for download progress updates"""
        try:
            if isinstance(progress, (int, float)):
                self.progress_var.set(progress)
            if status:
                self.status_var.set(status)
            self.root.update_idletasks()
        except Exception as e:
            logger.error(f"Error updating download progress: {str(e)}")
            
    def disable_ui(self):
        """Disable UI elements during installation"""
        for tab in [self.bot_tab, self.ai_tab]:
            for child in tab.winfo_children():
                if isinstance(child, ttk.Frame) or isinstance(child, ttk.LabelFrame):
                    for widget in child.winfo_children():
                        if isinstance(widget, (ttk.Entry, ttk.Button, ttk.Combobox)):
                            widget.configure(state='disabled')
                elif isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                    child.configure(state='disabled')
                    
    def enable_ui(self):
        """Enable UI elements after installation"""
        for tab in [self.bot_tab, self.ai_tab]:
            for child in tab.winfo_children():
                if isinstance(child, ttk.Frame) or isinstance(child, ttk.LabelFrame):
                    for widget in child.winfo_children():
                        if isinstance(widget, (ttk.Entry, ttk.Button, ttk.Combobox)):
                            widget.configure(state='normal')
                elif isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                    child.configure(state='normal')
                    
    def on_checkpoint_selected(self, event=None):
        """Handle workflow selection"""
        selected = self.selected_checkpoint.get()
        if selected:
            # Map workflow files to model configurations
            workflow_to_model = {
                'fluxfusion6GB4step.json': 'FLUXFusion 6GB',
                'fluxfusion8GB4step.json': 'FLUXFusion 8GB',
                'fluxfusion10GB4step.json': 'FLUXFusion 10GB',
                'fluxfusion12GB4step.json': 'FLUXFusion 12GB',
                'fluxfusion24GB4step.json': 'FLUXFusion 24GB',
                'FluxDev24GB.json': 'FLUX.1 Dev'
            }
            
            # Check if the workflow file exists in the target directory
            target_path = os.path.join(self.base_dir.get(), 'ComfyUI', 'workflows', 'Main', 'Datasets', selected)
            if os.path.exists(target_path):
                self.install_button.config(text="Update Configuration")
                self.status_var.set("Status: Workflow already installed")
            else:
                self.install_button.config(text="Install")
                self.status_var.set("Status: Ready to install")
                
            # Store the model name for this workflow
            if selected in workflow_to_model:
                self.selected_model = workflow_to_model[selected]
            else:
                self.selected_model = None
                
    def start_installation(self):
        """Start the installation process"""
        if not self.base_dir.get():
            messagebox.showerror("Error", "Please select ComfyUI Base Directory")
            return

        # Validate directory structure
        if not self.setup_manager.validator.validate_comfyui_directory(self.base_dir.get()):
            messagebox.showerror("Error", "Invalid ComfyUI directory structure")
            return

        # Disable UI elements during installation
        self.disable_ui()

        async def run_async_installation():
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
                        await self.setup_manager.download_file(
                            file_info=model_info,
                            output_path=model_path,
                            token=token,
                            source=model_info['source']
                        )
                        self.update_progress(100, f"Successfully downloaded {model_name}")
                    except Exception as e:
                        logger.error(f"Error downloading {model_name}: {str(e)}")
                        raise

                # Handle selected workflow and model
                if self.selected_checkpoint.get() and self.selected_checkpoint.get() != "Select a workflow...":
                    workflow_file = self.selected_checkpoint.get()
                    self.update_progress(0, f"Processing workflow {workflow_file}...")
                    
                    # Copy workflow file
                    source_path = os.path.join(os.getcwd(), 'Main', 'Datasets', workflow_file)
                    target_path = os.path.join(self.base_dir.get(), 'ComfyUI', 'workflows', 'Main', 'Datasets', workflow_file)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    try:
                        # Copy the workflow file
                        shutil.copy2(source_path, target_path)
                        self.update_progress(100, f"Successfully copied workflow file")
                        
                        # Download the corresponding model if needed
                        if hasattr(self, 'selected_model') and self.selected_model in CHECKPOINTS:
                            model_info = CHECKPOINTS[self.selected_model]
                            model_path = os.path.join(
                                self.setup_manager.models_path,
                                model_info['path'].strip('/'),
                                model_info['filename']
                            )
                            
                            if not os.path.exists(model_path):
                                self.update_progress(0, f"Downloading {self.selected_model} model...")
                                token = self.hf_token.get() if model_info['source'] == 'huggingface' else self.civitai_token.get()
                                await self.setup_manager.download_file(
                                    file_info=model_info,
                                    output_path=model_path,
                                    token=token,
                                    source=model_info['source']
                                )
                                self.update_progress(100, f"Successfully downloaded {self.selected_model}")
                            else:
                                self.update_progress(100, f"Checkpoint {self.selected_model} already exists, preserving existing file")
                    
                        # Update .env file with fluxversion
                        self.update_progress(100, "Updating configuration...")
                        self.setup_manager.update_env_file('fluxversion', f'"{workflow_file}"')
                    except Exception as e:
                        logger.error(f"Error processing workflow and model: {str(e)}")
                        raise

                # Save configuration
                self.save_configuration()

                # Complete
                self.update_progress(100, "Installation completed successfully!")
                messagebox.showinfo("Success", "Installation completed successfully!")
                
            except Exception as e:
                logger.error(f"Installation failed: {str(e)}")
                messagebox.showerror("Error", f"Installation failed: {str(e)}")
            finally:
                self.enable_ui()

        # Run the async installation in the event loop
        if not hasattr(self, 'loop'):
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        def run_async():
            try:
                self.loop.run_until_complete(run_async_installation())
            except Exception as e:
                messagebox.showerror("Error", f"Installation failed: {str(e)}")
            finally:
                self.enable_ui()
                
        # Start the async process
        threading.Thread(target=run_async, daemon=True).start()
        
def main():
    root = tk.Tk()
    app = SetupUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()