import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import json
from pathlib import Path
import threading
import sys  # Added sys import

# Import our modular components
from dialogs.entry_dialog import EntryDialog
from dialogs.file_naming_dialog import FileNamingDialog
from downloaders.civitai_downloader import CivitAIDownloader
from downloaders.huggingface_downloader import HuggingFaceDownloader
from ui.treeview import LoraTreeview
from ui.controls import HistoryControls, ActionButtons, NavigationButtons, StatusBar
from utils.config import load_env, load_json_config, save_json_config, update_env_file
from lora_database import LoraDatabase, LoraHistoryEntry

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LoraEditor:
    def __init__(self, root: tk.Tk):
        # Initialize environment and configuration
        self.root = root
        self.root.title("LoRA Configuration Editor")
        self.root.geometry("1400x925")
        
        # Load environment variables
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            exe_dir = Path(sys.executable).parent
            potential_paths = [
                exe_dir,  # Same directory as exe
                exe_dir.parent,  # One level up
                exe_dir.parent.parent,  # Two levels up
                exe_dir.parent.parent.parent,  # Three levels up
            ]
        else:
            # Running as script
            script_dir = Path(__file__).parent
            potential_paths = [
                script_dir,  # Same directory as script
                script_dir.parent,  # One level up (root)
            ]

        # Try to load environment variables from each potential path
        env_loaded = False
        for base_path in potential_paths:
            if load_env(base_path):
                logger.info(f"Loaded environment variables from: {base_path}")
                env_loaded = True
                break

        if not env_loaded:
            logger.warning("Could not find .env file in any of the expected locations")
            
        # Initialize database and variables
        self.db = LoraDatabase()
        self.init_variables()
        
        # Create UI components
        self.create_ui()
        
        # Configure root window grid
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        
        # Load initial data
        self.load_tree()
        self.status_bar.set_status("Ready")
        self.refresh_lora_files()

    def create_ui(self):
        """Create the main UI layout"""
        # Main container
        self.container = ttk.Frame(self.root, padding=10)
        self.container.grid(row=0, column=0, sticky="nsew")
        
        # Title
        title_frame = ttk.Frame(self.container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(title_frame, text="LoRA Configuration Editor", font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)
        
        # File Locations section
        locations_frame = ttk.LabelFrame(self.container, text="File Locations", padding=10)
        locations_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # JSON file selection
        json_frame = ttk.Frame(locations_frame)
        json_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(json_frame, text="Config JSON:").pack(side=tk.LEFT, padx=(0, 5))
        json_entry = ttk.Entry(json_frame, textvariable=self.json_var, width=60)
        json_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(json_frame, text="Browse", command=self.select_json).pack(side=tk.LEFT)
        
        # LoRA folder selection
        folder_frame = ttk.Frame(locations_frame)
        folder_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(folder_frame, text="LoRA Folder:").pack(side=tk.LEFT, padx=(0, 5))
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=60)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", command=self.select_folder).pack(side=tk.LEFT)
        
        # Download section
        download_frame = ttk.LabelFrame(self.container, text="Download LoRAs", padding=10)
        download_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        # CivitAI URL
        civitai_frame = ttk.Frame(download_frame)
        civitai_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(civitai_frame, text="CivitAI URL:").pack(side=tk.LEFT, padx=(0, 5))
        civitai_entry = ttk.Entry(civitai_frame, textvariable=self.civitai_url_var, width=80)
        civitai_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(civitai_frame, text="Download from CivitAI", command=self.download_from_civitai).pack(side=tk.LEFT)

        # HuggingFace URL section
        hf_frame = ttk.Frame(download_frame)
        hf_frame.pack(fill=tk.X, pady=5)
        ttk.Label(hf_frame, text="HuggingFace URL:").pack(side=tk.LEFT, padx=(0, 5))
        hf_entry = ttk.Entry(hf_frame, textvariable=self.hf_url_var, width=80)
        hf_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(hf_frame, text="Download from HF", command=self.download_from_huggingface).pack(side=tk.LEFT)
        
        # Progress bar frame
        self.progress_frame = ttk.Frame(download_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5)
        self.progress_frame.pack_forget()
        
        # Default LoRA selection
        default_frame = ttk.Frame(self.container)
        default_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(default_frame, text="Default LoRA:").pack(side=tk.LEFT, padx=(0, 5))
        self.default_combo = ttk.Combobox(default_frame, textvariable=self.default_var, width=50)
        self.default_combo.pack(side=tk.LEFT)
        self.default_combo.bind('<<ComboboxSelected>>', self.update_default_lora)
        
        # Search frame
        search_frame = ttk.Frame(self.container)
        search_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var.trace('w', self.filter_treeview)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT)
        
        # TreeView
        self.create_treeview()
        
        # Buttons
        self.create_buttons()
        
        # Status bar
        self.status_bar = StatusBar(self.container)
        self.status_bar.grid(row=7, column=0, sticky="ew", pady=(10, 0))

    def create_buttons(self):
        """Create the main action buttons"""
        btn_frame = ttk.Frame(self.container)
        btn_frame.grid(row=6, column=0, pady=10)
        
        buttons = [
            ("Add Entry", self.add_entry, "⊕"),
            ("Edit Entry", self.edit_entry, "✎"),
            ("Delete Entry", self.delete_entry, "✖"),
            ("Save", self.save_config, "💾"),
            ("Refresh Files", self.refresh_lora_files, "🔄"),
            ("Reset LoRA", self.reset_lora, "⚠")
        ]
        
        for text, command, symbol in buttons:
            btn = ttk.Button(
                btn_frame, 
                text=f"{symbol} {text}", 
                command=command, 
                width=15
            )
            btn.pack(side=tk.LEFT, padx=5)

    def create_treeview(self):
        """Create the treeview with reorder buttons"""
        # Create main frame
        main_frame = ttk.Frame(self.container)
        main_frame.grid(row=4, column=0, sticky="nsew")
        
        # Create navigation buttons frame with border
        nav_frame = ttk.LabelFrame(main_frame, text="Move", padding=(2, 2))
        nav_frame.grid(row=0, column=0, sticky="ns", padx=2)
        
        # Create navigation buttons with command dictionary
        nav_commands = {
            'up': self.move_up,
            'down': self.move_down,
            'up_five': self.move_up_five,
            'down_five': self.move_down_five
        }
        self.nav_buttons = NavigationButtons(nav_frame, nav_commands)
        
        # Create treeview
        columns = ("ID", "Status", "Name", "File", "Weight", "Trigger Words", "URL")
        self.tree = LoraTreeview(
            main_frame,
            columns=columns,
            selectmode="extended",
            show="headings"  # Only show column headings, not tree structure
        )
        self.tree.grid(row=0, column=1, sticky="nsew")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=2, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewReordered>>", lambda e: self.sync_database_order())
        
        # Configure main frame grid weights
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Make tree container expand to fill available space
        self.container.grid_rowconfigure(4, weight=1)

    def init_variables(self):
        """Initialize main variables and objects"""
        # Variables for file paths
        self.json_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.json_path = os.getenv('LORA_JSON_PATH', '')
        self.lora_folder = os.getenv('LORA_FOLDER_PATH', '')
        
        # Set initial values
        self.json_var.set(self.json_path)
        self.folder_var.set(self.lora_folder)
        
        # Load initial configuration
        self.config = load_json_config(self.json_path) if os.path.exists(self.json_path) else {"default": "", "available_loras": []}
        
        # Sync database with JSON
        if self.config and "available_loras" in self.config:
            self.db.sync_with_json(self.config)
            
        # Variables for UI state
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_treeview)
        self.show_inactive_var = tk.BooleanVar(value=False)
        self.show_inactive_var.trace('w', lambda *args: self.refresh_tree())
        self.default_var = tk.StringVar(value=self.config.get("default", ""))
        self.default_var.trace('w', self.update_default_lora)
        
        # Download-related variables
        self.civitai_url_var = tk.StringVar()
        self.hf_url_var = tk.StringVar()
        self.progress_var = tk.IntVar()
        
        # Initialize downloaders
        self.civitai_downloader = CivitAIDownloader()
        self.huggingface_downloader = HuggingFaceDownloader()
        
        # List of available LoRA files
        self.available_lora_files = []

    def add_entry(self):
        """Add a new LoRA entry"""
        if not self.available_lora_files:
            messagebox.showwarning("Warning", "Please select a folder with LoRA files first")
            return 

        # Create initial values dict
        initial_values = {
            "name": "",
            "file": "",
            "weight": "1.0",
            "add_prompt": "",  
            "url": ""
        }

        dialog = EntryDialog(
            self.root, 
            "Add LoRA Entry", 
            initial=initial_values,
            available_files=self.available_lora_files
        )
        
        if dialog.result:
            try:
                # Add to database
                self.db.add_lora(LoraHistoryEntry(
                    file_name=dialog.result["file"],
                    display_name=dialog.result["name"],
                    trigger_words=dialog.result["add_prompt"],  
                    weight=float(dialog.result["weight"]),
                    url=dialog.result["url"],
                    is_active=True
                ))
                
                # Save config
                self.save_config()
                
                self.refresh_tree()
                self.status_bar.set_status(f"Added new entry: {dialog.result['name']}")
                
            except Exception as e:
                logger.error(f"Error adding entry: {e}")
                messagebox.showerror("Error", f"Failed to add entry: {str(e)}")

    def select_json(self):
        """Handle JSON file selection"""
        try:
            initialdir = os.path.dirname(self.json_var.get()) if self.json_var.get() else os.getcwd()
            filename = filedialog.askopenfilename(
                title="Select LoRA Configuration File",
                initialdir=initialdir,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                self.json_path = filename
                self.json_var.set(filename)
                update_env_file('LORA_JSON_PATH', filename)
                
                # Load the JSON file and update config
                self.config = load_json_config(filename)
                
                # Sync database with the newly loaded JSON
                if os.path.exists(filename):
                    self.db.sync_with_json(self.config)
                
                self.load_tree()
                self.status_bar.set_status("JSON configuration loaded")
                self.refresh_lora_files()
                
                # Update default LoRA if it exists
                if self.config.get("default"):
                    self.default_var.set(self.config["default"])
        except Exception as e:
            logger.error(f"Error selecting JSON file: {e}")
            messagebox.showerror("Error", f"Failed to load JSON file: {str(e)}")

    def select_folder(self):
        """Handle folder selection"""
        initialdir = self.folder_var.get() if self.folder_var.get() else os.getcwd()
        folder = filedialog.askdirectory(
            title="Select LoRA Files Folder",
            initialdir=initialdir
        )
        
        if folder:
            self.lora_folder = folder
            self.folder_var.set(folder)
            update_env_file('LORA_FOLDER_PATH', folder)
            self.refresh_lora_files()

    def refresh_lora_files(self):
        """Refresh the list of available LoRA files"""
        try:
            if not os.path.exists(self.lora_folder):
                return
            
            # Get list of .safetensors files
            self.available_lora_files = []
            for file in os.listdir(self.lora_folder):
                if file.endswith('.safetensors'):
                    self.available_lora_files.append(file)
                    
            # Update default LoRA combobox
            self.default_combo['values'] = self.available_lora_files
            if self.config.get("default") in self.available_lora_files:
                self.default_var.set(self.config["default"])
                
        except Exception as e:
            logger.error(f"Error refreshing LoRA files: {e}")
            messagebox.showerror("Error", f"Failed to refresh LoRA files: {str(e)}")

    def load_tree(self):
        """Load data into the treeview"""
        try:
            self.tree.delete(*self.tree.get_children())
            
            # Get entries from database and sort by ID
            entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
            entries.sort(key=lambda x: x.id)  # Sort by ID to maintain order
            
            # Update tree with entries
            for entry in entries:
                status = "Active" if entry.is_active else "Inactive"
                # Store all values including ID in the values list
                self.tree.insert('', 'end', values=(
                    entry.id,
                    status, 
                    entry.display_name, 
                    entry.file_name, 
                    entry.weight, 
                    entry.trigger_words, 
                    entry.url or ""
                ))
                
            self.status_bar.set_status(f"Loaded {len(entries)} entries")
        except Exception as e:
            logger.error(f"Error loading tree: {e}")
            messagebox.showerror("Error", f"Failed to load entries: {str(e)}")

    def refresh_tree(self):
        """Refresh the treeview with current data"""
        # Store current selection
        selected_items = self.tree.selection()
        selected_ids = [self.tree.item(item)["values"][0] for item in selected_items]
        
        # Reload the tree
        self.load_tree()
        
        # Restore selection
        for item in self.tree.get_children():
            if self.tree.item(item)["values"][0] in selected_ids:
                self.tree.selection_add(item)
        
        self.filter_treeview()

    def filter_treeview(self, *args):
        """Filter the treeview based on search term"""
        search_term = self.search_var.get().lower()
        
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if any(str(value).lower().find(search_term) >= 0 for value in values):
                self.tree.reattach(item, '', 'end')
            else:
                self.tree.detach(item)

    def move_up(self, save_changes=True):
        """Move selected item up in the list"""
        selected = self.tree.selection()
        if not selected:
            return False  # Return False if no movement occurred
            
        moved = False
        
        for item in selected:
            idx = self.tree.index(item)
            if idx > 0:
                # Get the current values of both items
                current_values = list(self.tree.item(item)["values"])
                above_item = self.tree.prev(item)
                above_values = list(self.tree.item(above_item)["values"])
                
                # Swap all values except the ID
                current_id = current_values[0]
                above_id = above_values[0]
                current_values[0] = above_id
                above_values[0] = current_id
                
                # Update both items
                self.tree.item(item, values=current_values)
                self.tree.item(above_item, values=above_values)
                
                # Move the item up in the treeview
                self.tree.move(item, '', idx - 1)
                moved = True
        
        if moved:
            # Keep the same items selected
            self.tree.selection_set(selected)
            self.tree.see(selected[0])  # Ensure first selected item is visible
            self.sync_database_order()
            if save_changes:
                self.save_config()
        
        return moved

    def move_down(self, save_changes=True):
        """Move selected item down in the list"""
        selected = self.tree.selection()
        if not selected:
            return False  # Return False if no movement occurred
            
        moved = False
        
        # Process items in reverse to maintain order when moving down
        for item in reversed(selected):
            idx = self.tree.index(item)
            if idx < len(self.tree.get_children()) - 1:
                # Get the current values of both items
                current_values = list(self.tree.item(item)["values"])
                below_item = self.tree.next(item)
                below_values = list(self.tree.item(below_item)["values"])
                
                # Swap all values except the ID
                current_id = current_values[0]
                below_id = below_values[0]
                current_values[0] = below_id
                below_values[0] = current_id
                
                # Update both items
                self.tree.item(item, values=current_values)
                self.tree.item(below_item, values=below_values)
                
                # Move the item down in the treeview
                self.tree.move(item, '', idx + 1)
                moved = True
        
        if moved:
            # Keep the same items selected
            self.tree.selection_set(selected)
            self.tree.see(selected[-1])  # Ensure last selected item is visible
            self.sync_database_order()
            if save_changes:
                self.save_config()
        
        return moved

    def move_up_five(self):
        """Move selected items up five positions"""
        moves_made = 0
        selected = self.tree.selection()  # Remember initial selection
        for _ in range(5):
            if self.move_up(save_changes=False):  # Only count successful moves
                moves_made += 1
            else:
                break  # Stop if we can't move up anymore
        
        if moves_made > 0:
            self.save_config()  # Save once at the end if any moves were made
            self.tree.selection_set(selected)  # Restore initial selection
            self.tree.see(selected[0])  # Ensure first selected item is visible
            
    def move_down_five(self):
        """Move selected items down five positions"""
        moves_made = 0
        selected = self.tree.selection()  # Remember initial selection
        for _ in range(5):
            if self.move_down(save_changes=False):  # Only count successful moves
                moves_made += 1
            else:
                break  # Stop if we can't move down anymore
        
        if moves_made > 0:
            self.save_config()  # Save once at the end if any moves were made
            self.tree.selection_set(selected)  # Restore initial selection
            self.tree.see(selected[-1])  # Ensure last selected item is visible

    def sort_treeview(self, col):
        """Sort treeview by column"""
        try:
            # Get current items
            items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
            
            # Determine sort order
            reverse = False
            if hasattr(self, '_last_sort'):
                if self._last_sort[0] == col:
                    reverse = not self._last_sort[1]
            self._last_sort = (col, reverse)
            
            # Sort items
            items.sort(reverse=reverse)
            
            # Rearrange items in sorted order
            for index, (_, item) in enumerate(items):
                self.tree.move(item, '', index)
                
            # Update column headers
            for column in self.tree["columns"]:
                if column == col:
                    self.tree.heading(column, text=f"{column} {'↓' if reverse else '↑'}")
                else:
                    self.tree.heading(column, text=column)
                    
            # Sync the new order to the database
            self.sync_database_order()
            
        except Exception as e:
            logger.error(f"Error sorting treeview: {e}")
            messagebox.showerror("Error", f"Failed to sort entries: {str(e)}")

    def sync_database_order(self):
        """Synchronize database order with current treeview state"""
        try:
            # Get all items in current order from treeview
            entries = []
            for index, item in enumerate(self.tree.get_children('')):
                values = self.tree.item(item)["values"]
                entry = LoraHistoryEntry(
                    id=values[0],  # Preserve the original ID
                    file_name=values[3],  # file_name
                    display_name=values[2],  # name
                    trigger_words=values[5],  # trigger words
                    weight=float(values[4]),  # weight
                    url=values[6] if values[6] else "",  # url
                    is_active=values[1] == "Active",  # status
                    display_order=index  # Use current position as display order
                )
                entries.append(entry)
            
            # Update database entries preserving their IDs
            for entry in entries:
                self.db.add_lora(entry, order=entry.display_order)
            
            # Save to JSON file
            self.save_config()
            
        except Exception as e:
            logger.error(f"Error syncing database order: {e}")
            messagebox.showerror("Error", f"Failed to sync database order: {str(e)}")

    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            # Get items directly from treeview in current order
            json_entries = []
            for item in self.tree.get_children(''):
                values = self.tree.item(item)["values"]
                json_entries.append({
                    'id': values[0],  # ID
                    'name': values[2],  # display_name
                    'file': values[3],  # file_name
                    'weight': float(values[4]),  # weight
                    'prompt': values[5],  # trigger_words
                    'url': values[6] if values[6] else ""  # url
                })
            
            # Update config with entries in current treeview order
            self.config['available_loras'] = json_entries
            
            # Save to file with proper formatting
            save_json_config(self.json_path, self.config)
            self.status_bar.set_status("Configuration saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            self.status_bar.set_status("Failed to save configuration")
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def on_download_complete(self, file_name, url, trigger_words):
        """Handle download completion"""
        self.refresh_lora_files()
        self.status_bar.set_status(f"Download complete: {file_name}")
        
        # Ask user if they want to add the downloaded file to the configuration
        if messagebox.askyesno("Add Entry", 
                             f"Do you want to add {file_name} to the configuration?"):
            # Create initial values for the dialog
            name = os.path.splitext(file_name)[0]  # Remove .safetensors extension
            initial = {
                "name": name,
                "file": file_name,
                "weight": "1.0",
                "add_prompt": trigger_words,
                "url": url
            }
            
            dialog = EntryDialog(
                self.root, 
                "Add LoRA Entry", 
                initial=initial,
                available_files=self.available_lora_files
            )
            
            if dialog.result:
                # Convert dialog result to LoraHistoryEntry
                entry = LoraHistoryEntry(
                    file_name=dialog.result["file"],
                    display_name=dialog.result["name"],
                    trigger_words=dialog.result["add_prompt"],
                    weight=float(dialog.result["weight"]),
                    url=dialog.result["url"]
                )
                self.db.add_lora(entry)
                self.save_config()
                self.refresh_tree()

    def download_from_civitai(self):
        """Download a LoRA model from CivitAI"""
        url = self.civitai_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a CivitAI URL")
            return
            
        def download_thread():
            try:
                # Show progress bar
                self.root.after(0, lambda: self.progress_frame.pack(fill=tk.X, pady=5))
                self.root.after(0, lambda: self.progress_var.set(0))  # Reset progress
                
                # Get download URL and trigger words
                download_url, trigger_words = self.civitai_downloader.get_download_url(url)
                
                # Start download
                file_name = self.civitai_downloader.download(
                    download_url,
                    self.lora_folder,
                    progress_callback=lambda p: self.root.after(0, lambda: self.update_progress(p))
                )
                
                # Handle download completion with trigger words
                self.root.after(0, lambda: self.on_download_complete(file_name, url, trigger_words))
                
            except Exception as e:
                logger.error(f"Error downloading from CivitAI: {e}")
                self.root.after(0, lambda: messagebox.showerror("Download Error", str(e)))
            finally:
                self.root.after(0, lambda: self.progress_frame.pack_forget())
                self.root.after(0, lambda: self.civitai_url_var.set(""))
        
        # Start download in a separate thread
        threading.Thread(target=download_thread, daemon=True).start()

    def download_from_huggingface(self):
        """Download a LoRA model from HuggingFace"""
        url = self.hf_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a HuggingFace URL")
            return
            
        def download_thread():
            try:
                # Show progress bar
                self.root.after(0, lambda: self.progress_frame.pack(fill=tk.X, pady=5))
                self.root.after(0, lambda: self.progress_var.set(0))  # Reset progress
                
                # Start download
                file_name = self.huggingface_downloader.download(
                    url,
                    self.lora_folder,
                    progress_callback=lambda p: self.root.after(0, lambda: self.update_progress(p))
                )
                
                # Handle download completion (no trigger words for HF)
                self.root.after(0, lambda: self.on_download_complete(file_name, url, ""))
                
            except Exception as e:
                logger.error(f"Error downloading from HuggingFace: {e}")
                self.root.after(0, lambda: messagebox.showerror("Download Error", str(e)))
            finally:
                self.root.after(0, lambda: self.progress_frame.pack_forget())
                self.root.after(0, lambda: self.hf_url_var.set(""))
        
        # Start download in a separate thread
        threading.Thread(target=download_thread, daemon=True).start()

    def update_progress(self, progress: float):
        """Update the progress bar with download progress"""
        self.progress_var.set(int(progress))
        self.root.update_idletasks()  # Force UI update

    def update_default_lora(self, *args):
        """Update the default LoRA in the configuration"""
        try:
            selected = self.default_var.get()
            if selected and selected in self.available_lora_files:
                self.config["default"] = selected
                save_json_config(self.json_path, self.config)
                self.status_bar.set_status(f"Default LoRA set to: {selected}")
            else:
                self.status_bar.set_status("Invalid default LoRA selection")
        except Exception as e:
            logger.error(f"Error updating default LoRA: {e}")
            self.status_bar.set_status("Failed to update default LoRA")

    def setup_styles(self):
        """Set up custom styles for the UI"""
        style = ttk.Style()
        
        # Configure treeview style
        style.configure("Treeview",
            background='white',
            fieldbackground='white',
            foreground='black',
            rowheight=25  # Slightly taller rows
        )
        
        # Configure treeview headings
        style.configure("Treeview.Heading",
            background='#333333',
            foreground='white',
            padding=5
        )
        
        # Configure button style
        style.configure("TButton",
            padding=5
        )
        
        # Configure title style
        style.configure("Title.TLabel",
            font=('Helvetica', 16, 'bold')
        )

    def on_double_click(self, event):
        """Handle double-click on treeview item"""
        item = self.tree.selection()
        if item:
            self.edit_entry()

    def edit_entry(self):
        """Edit selected LoRA entry"""
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an entry to edit")
                return

            item = selected[0]
            values = self.tree.item(item)["values"]
            
            # Create initial values with correct keys
            current_entry = {
                "name": values[2],  # display_name
                "file": values[3],  # file_name
                "weight": values[4],  # weight
                "add_prompt": values[5],  
                "url": values[6] or ""  # url
            }
            
            dialog = EntryDialog(
                self.root, 
                "Edit LoRA Entry", 
                initial=current_entry,
                available_files=self.available_lora_files
            )
            
            if dialog.result:
                # Convert dialog result back to database format
                entry = {
                    "file_name": dialog.result["file"],
                    "display_name": dialog.result["name"],
                    "weight": float(dialog.result["weight"]),
                    "trigger_words": dialog.result["add_prompt"],  
                    "is_active": values[1] == "Active",
                    "url": dialog.result.get("url", ""),
                    "display_order": int(values[0])  # Add display_order from the original entry
                }
                self.db.update_entry(current_entry["file"], entry)
                self.save_config()
                self.refresh_tree()
                self.status_bar.set_status("Entry updated successfully")
        except Exception as e:
            logger.error(f"Error editing entry: {e}")
            messagebox.showerror("Error", f"Failed to edit entry: {str(e)}")

    def delete_entry(self):
        """Delete selected LoRA entry"""
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an entry to delete")
                return

            if not messagebox.askyesno("Confirm Delete", 
                                     "Are you sure you want to delete the selected entries?"):
                return

            for item in selected:
                values = self.tree.item(item)["values"]
                file_name = values[3]
                self.db.delete_entry(file_name)
            
            self.save_config()
            self.refresh_tree()
            self.status_bar.set_status("Entry(s) deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting entry: {e}")
            messagebox.showerror("Error", f"Failed to delete entry: {str(e)}")

    def reset_lora(self):
        """Reset LoRA configuration"""
        try:
            if not messagebox.askyesno("Confirm Reset", 
                                     "Are you sure you want to reset all entries?"):
                return

            self.db.reset_database()
            self.save_config()
            self.refresh_tree()
            self.status_bar.set_status("Configuration reset successfully")
        except Exception as e:
            logger.error(f"Error resetting configuration: {e}")
            messagebox.showerror("Error", f"Failed to reset configuration: {str(e)}")

def main():
    root = tk.Tk()
    app = LoraEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()