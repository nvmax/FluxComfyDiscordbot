import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkthemes import ThemedTk
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
        
        # Set theme
        self.root.set_theme("black")  # Using 'arc' theme, you can change to any other available theme
        
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
        
        # Create main container with grid
        main_frame = ttk.Frame(self.bot_tab, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Configure column weights (1/5, 2/3, remainder)
        main_frame.grid_columnconfigure(0, weight=1, minsize=160)  # Label column (1/5)
        main_frame.grid_columnconfigure(1, weight=4, minsize=480)  # Entry column (2/3)
        main_frame.grid_columnconfigure(2, weight=1, minsize=160)  # Button column
        
        current_row = 0
        
        # ComfyUI Directory Section
        dir_frame = ttk.LabelFrame(main_frame, text="ComfyUI Directory", padding=10)
        dir_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        dir_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(dir_frame, text="Base Directory:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(dir_frame, textvariable=self.base_dir).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(dir_frame, text="Browse", command=self.select_base_directory).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        current_row += 1
        
        # API Tokens Section
        token_frame = ttk.LabelFrame(main_frame, text="API Tokens", padding=10)
        token_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        token_frame.grid_columnconfigure(1, weight=1)
        
        # HuggingFace Token
        ttk.Label(token_frame, text="HuggingFace Token:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(token_frame, textvariable=self.hf_token, show="*").grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(token_frame, text="Validate", command=lambda: self.validate_token("hf")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        
        # CivitAI Token
        ttk.Label(token_frame, text="CivitAI Token:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(token_frame, textvariable=self.civitai_token, show="*").grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(token_frame, text="Validate", command=lambda: self.validate_token("civitai")).grid(row=1, column=2, padx=5, pady=5, sticky="w")
        
        # Discord Token
        ttk.Label(token_frame, text="Discord Token:", anchor="e").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(token_frame, textvariable=self.discord_token, show="*").grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        current_row += 1
        
        # Server Configuration Section
        server_frame = ttk.LabelFrame(main_frame, text="Server Configuration", padding=10)
        server_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        server_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(server_frame, text="Bot Server:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(server_frame, textvariable=self.bot_server).grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Label(server_frame, text="Server Address:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(server_frame, textvariable=self.server_address).grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        current_row += 1
        
        # Discord Configuration Section
        discord_frame = ttk.LabelFrame(main_frame, text="Discord Configuration", padding=10)
        discord_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        discord_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(discord_frame, text="Allowed Server IDs:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="ne")
        server_ids_entry = tk.Text(discord_frame, height=3)
        server_ids_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        if self.allowed_servers.get():
            server_ids_entry.insert("1.0", self.allowed_servers.get())
        def update_allowed_servers(*args):
            self.allowed_servers.set(server_ids_entry.get("1.0", "end-1c"))
        server_ids_entry.bind('<KeyRelease>', update_allowed_servers)
        
        ttk.Label(discord_frame, text="Channel IDs:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="ne")
        channel_ids_entry = tk.Text(discord_frame, height=3)
        channel_ids_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        if self.channel_ids.get():
            channel_ids_entry.insert("1.0", self.channel_ids.get())
        def update_channel_ids(*args):
            self.channel_ids.set(channel_ids_entry.get("1.0", "end-1c"))
        channel_ids_entry.bind('<KeyRelease>', update_channel_ids)
        
        ttk.Label(discord_frame, text="Bot Manager Role ID:", anchor="e").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(discord_frame, textvariable=self.bot_manager_role_id).grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        current_row += 1
        
        # Workflow Selection Section
        workflow_frame = ttk.LabelFrame(main_frame, text="Workflow Selection", padding=10)
        workflow_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        workflow_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(workflow_frame, text="Select Workflow:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        datasets_path = os.path.join(os.getcwd(), 'Main', 'Datasets')
        workflow_files = []
        if os.path.exists(datasets_path):
            for file in os.listdir(datasets_path):
                if file.endswith('.json') and file not in ['lora.json', 'ratios.json', 'Redux.json', 'Reduxprompt.json', 'Pulid6GB.json', 'Pulid8GB.json', 'Pulid10GB.json', 'Pulid12GB.json', 'Pulid24GB.json', 'PulidFluxDev.json']:
                    workflow_files.append(file)
        workflow_combo = ttk.Combobox(workflow_frame, textvariable=self.selected_checkpoint, 
                                    values=sorted(workflow_files), state="readonly")
        workflow_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        workflow_combo.bind("<<ComboboxSelected>>", self.on_checkpoint_selected)
        current_row += 1
        
        # Installation Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Installation Progress", padding=10)
        progress_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var, wraplength=600)
        self.status_label.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        # Create a frame to center the install button
        button_frame = ttk.Frame(progress_frame)
        button_frame.grid(row=2, column=0, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)  # This helps center the button
        
        self.install_button = ttk.Button(button_frame, text="Install", 
                                       command=self.start_installation, width=20)  # Set fixed width
        self.install_button.grid(row=0, column=0)
        
    def create_ai_tab(self):
        # Create main container with grid
        main_frame = ttk.Frame(self.ai_tab, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Configure column weights (1/5, 4/5)
        main_frame.grid_columnconfigure(0, weight=1, minsize=150)  # Label column (1/5)
        main_frame.grid_columnconfigure(1, weight=4, minsize=600)  # Entry column (4/5)
        
        current_row = 0
        
        # AI Configuration Section
        ai_config_frame = ttk.LabelFrame(main_frame, text="AI Configuration", padding=10)
        ai_config_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        ai_config_frame.grid_columnconfigure(1, weight=1)
        
        # AI Provider Selection
        ttk.Label(ai_config_frame, text="AI Provider:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Combobox(ai_config_frame, textvariable=self.ai_provider,
                    values=["lmstudio", "openai", "xai", "gemini"], 
                    state="readonly").grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Enable Prompt Enhancement
        ttk.Label(ai_config_frame, text="Prompt Enhancement:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Checkbutton(ai_config_frame, text="Enable",
                       variable=self.enable_prompt_enhancement).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        current_row += 1
        
        # LMStudio Configuration Section
        lmstudio_frame = ttk.LabelFrame(main_frame, text="LMStudio Configuration", padding=10)
        lmstudio_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        lmstudio_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(lmstudio_frame, text="LMStudio Host:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(lmstudio_frame, textvariable=self.lmstudio_host).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(lmstudio_frame, text="LMStudio Port:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(lmstudio_frame, textvariable=self.lmstudio_port).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        current_row += 1
        
        # API Keys Section
        api_frame = ttk.LabelFrame(main_frame, text="API Keys", padding=10)
        api_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        api_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(api_frame, text="XAI API Key:", anchor="e").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(api_frame, textvariable=self.xai_api_key, show="*").grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(api_frame, text="Gemini API Key:", anchor="e").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(api_frame, textvariable=self.gemini_api_key, show="*").grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(api_frame, text="OpenAI API Key:", anchor="e").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        ttk.Entry(api_frame, textvariable=self.openai_api_key, show="*").grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        current_row += 1
        
        # Save Button - Create a frame to center the button
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=current_row, column=0, columnspan=2, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)  # This helps center the button
        
        save_button = ttk.Button(button_frame, text="Save AI Configuration", 
                               command=self.save_ai_configuration, width=20)  # Set fixed width
        save_button.grid(row=0, column=0)
        
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
            
            # Map workflow names to Pulid files
            workflow_to_pulid = {
                'fluxfusion6GB4step.json': 'Pulid6GB.json',
                'fluxfusion8GB4step.json': 'Pulid8GB.json',
                'fluxfusion10GB4step.json': 'Pulid10GB.json',
                'fluxfusion12GB4step.json': 'Pulid12GB.json',
                'fluxfusion24GB4step.json': 'Pulid24GB.json',
                'FluxDev24GB.json': 'PulidFluxDev.json'
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
                
            # Update PULIDWORKFLOW in .env file if workflow has a corresponding Pulid file
            if selected in workflow_to_pulid:
                pulid_file = workflow_to_pulid[selected]
                self.setup_manager.update_env_file('PULIDWORKFLOW', f'"{pulid_file}"')
                self.status_var.set(f"Status: Updated PULIDWORKFLOW to '{pulid_file}'")
                
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
                if self.selected_checkpoint.get() and self.selected_checkpoint.get() != "Select a checkpoint...":
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
    root = ThemedTk(theme="arc")  # Create themed root window
    root.title("FluxComfy Setup")
    
    # Set a reasonable window size
    window_width = 830
    window_height = 800
    
    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Calculate position
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    
    # Set window size and position
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Make window resizable
    root.resizable(True, True)
    
    app = SetupUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()