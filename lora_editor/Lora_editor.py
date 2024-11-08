import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import shutil
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote
from huggingface_hub import HfApi
import json
import requests
import re
from dotenv import load_dotenv
import lorautils
from lora_database import LoraDatabase, LoraHistoryEntry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FileNamingDialog:
    def __init__(self, parent, original_filename, dest_folder):
        self.result = None
        self.original_filename = original_filename
        self.dest_folder = dest_folder
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Save LoRA File")
        self.dialog.geometry("600x200")
        self.dialog.resizable(False, False)
        
        self.setup_ui()
        self.center_dialog(parent)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        
        parent.wait_window(self.dialog)

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Original filename display
        orig_frame = ttk.Frame(main_frame)
        orig_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(orig_frame, text="Original filename:").pack(side=tk.LEFT)
        ttk.Label(orig_frame, text=self.original_filename, style="Info.TLabel").pack(side=tk.LEFT, padx=(5, 0))
        
        # New filename entry
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(name_frame, text="Save as:").pack(side=tk.LEFT)
        
        filename_base, ext = os.path.splitext(self.original_filename)
        
        self.filename_entry = ttk.Entry(name_frame, width=50)
        self.filename_entry.insert(0, filename_base)
        self.filename_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        ttk.Label(name_frame, text=ext).pack(side=tk.LEFT)
        
        self.warning_label = ttk.Label(main_frame, text="", foreground="red")
        self.warning_label.pack(fill=tk.X, pady=(0, 10))
        
        self.filename_entry.bind('<KeyRelease>', self.validate_filename)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        
        self.save_btn = ttk.Button(btn_frame, text="Save", command=self.save)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def center_dialog(self, parent):
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 600
        dialog_height = 200
        position_x = parent_x + (parent_width - dialog_width) // 2
        position_y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

    def validate_filename(self, event=None):
        filename = self.filename_entry.get()
        if not filename:
            self.warning_label.config(text="Filename cannot be empty")
            self.save_btn.config(state="disabled")
            return
            
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, filename):
            self.warning_label.config(text="Filename contains invalid characters")
            self.save_btn.config(state="disabled")
            return
            
        full_path = os.path.join(self.dest_folder, filename + os.path.splitext(self.original_filename)[1])
        if os.path.exists(full_path):
            self.warning_label.config(text="Warning: File already exists and will be overwritten")
        else:
            self.warning_label.config(text="")
            
        self.save_btn.config(state="normal")

    def save(self):
        filename = self.filename_entry.get()
        if not filename:
            messagebox.showerror("Error", "Filename cannot be empty")
            return
            
        ext = os.path.splitext(self.original_filename)[1]
        if not filename.endswith(ext):
            filename += ext
            
        self.result = filename
        self.dialog.destroy()

class EntryDialog:
    def __init__(self, parent, title, initial=None, available_files=None):
        self.result = None
        self.available_files = available_files or []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x350")
        self.dialog.resizable(False, False)
        
        self.setup_ui(initial)
        self.center_dialog(parent)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        
        parent.wait_window(self.dialog)

    def setup_ui(self, initial):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name field
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self.name_entry = ttk.Entry(name_frame, width=40)
        self.name_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # File selection
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="File:").pack(side=tk.LEFT)
        self.file_var = tk.StringVar()
        self.file_combo = ttk.Combobox(file_frame, textvariable=self.file_var, width=37)
        self.file_combo['values'] = self.available_files
        self.file_combo.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Weight field
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=5)
        ttk.Label(weight_frame, text="Weight:").pack(side=tk.LEFT)
        vcmd = (self.dialog.register(self.validate_weight), '%P')
        self.weight_entry = ttk.Entry(weight_frame, width=10, validate="key", validatecommand=vcmd)
        self.weight_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Prompt field
        prompt_frame = ttk.Frame(main_frame)
        prompt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(prompt_frame, text="Add Prompt:").pack(side=tk.LEFT)
        self.prompt_entry = ttk.Entry(prompt_frame, width=40)
        self.prompt_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Set initial values
        if initial:
            self.name_entry.insert(0, initial["name"])
            self.file_var.set(initial["file"])
            self.weight_entry.insert(0, initial["weight"])
            self.prompt_entry.insert(0, initial["prompt"])
        else:
            self.weight_entry.insert(0, "0.5")
            self.file_var.trace('w', self.update_name_from_file)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def center_dialog(self, parent):
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 500
        dialog_height = 350
        position_x = parent_x + (parent_width - dialog_width) // 2
        position_y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

    def validate_weight(self, new_value):
        if new_value == "":
            return True
        try:
            value = float(new_value)
            return 0 <= value <= 1
        except ValueError:
            return False

    def update_name_from_file(self, *args):
        file_name = self.file_var.get()
        if file_name and not self.name_entry.get():
            base_name = os.path.splitext(file_name)[0]
            suggested_name = base_name.replace('_', ' ').replace('-', ' ').title()
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, suggested_name)

    def save(self):
        try:
            if not self.name_entry.get():
                raise ValueError("Name is required")
            if not self.file_var.get():
                raise ValueError("Please select a LoRA file")
            
            weight = float(self.weight_entry.get())
            if not (0 <= weight <= 1):
                raise ValueError("Weight must be between 0 and 1")
                
            self.result = {
                "name": self.name_entry.get(),
                "file": self.file_var.get(),
                "weight": str(weight),
                "prompt": self.prompt_entry.get()
            }
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

class LoraEditor:
    def __init__(self, root):
        load_dotenv()
        
        self.root = root
        self.root.title("LoRA Configuration Editor")
        self.root.geometry("1225x825")
        
        self.db = LoraDatabase()
        self.show_inactive_var = tk.BooleanVar(value=False)
        
        self.setup_styles()
        self.init_variables()
        self.create_ui()
        
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        
        self.load_tree()
        self.update_status()
        self.refresh_lora_files()

    def init_variables(self):
        try:
            # Get paths from environment variables
            self.json_path = os.getenv('LORA_JSON_PATH', 'lora.json')
            self.lora_folder = os.getenv('LORA_FOLDER_PATH', '')
            
            # Initialize config with the specified JSON path
            self.config = lorautils.LoraConfig(self.json_path)
            
            # Sync database with existing JSON if it exists
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    self.db.sync_with_json(json_data)
                except Exception as e:
                    logging.error(f"Error syncing database with JSON: {e}")
            
            # Initialize other variables
            self.downloader = lorautils.CivitAIDownloader(self.update_progress)
            self.hf_downloader = lorautils.HuggingFaceDownloader(self.update_progress)
            self.folder_var = tk.StringVar(value=self.lora_folder)
            self.json_var = tk.StringVar(value=self.json_path)
            self.search_var = tk.StringVar()
            self.default_var = tk.StringVar(value=self.config.data.get("default", ""))
            self.status_var = tk.StringVar()
            self.civitai_url_var = tk.StringVar()
            self.hf_url_var = tk.StringVar()
            self.progress_var = tk.DoubleVar()
            self.available_lora_files = []

        except Exception as e:
            logging.error(f"Error initializing variables: {e}")
            messagebox.showerror("Error", f"Failed to initialize: {str(e)}")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure("Treeview",
            background="white",
            fieldbackground="white",
            rowheight=25,
            font=('Segoe UI', 9)
        )
        self.style.configure("Treeview.Heading",
            font=('Segoe UI', 9, 'bold'),
            padding=5
        )
        
        self.style.configure("TLabel", font=('Segoe UI', 9))
        self.style.configure("TButton", font=('Segoe UI', 9))
        self.style.configure("TEntry", font=('Segoe UI', 9))
        self.style.configure("Title.TLabel", font=('Segoe UI', 12, 'bold'))
        self.style.configure("TLabelframe", padding=5)
        self.style.configure("TLabelframe.Label", font=('Segoe UI', 9))

    def create_ui(self):
        self.container = ttk.Frame(self.root, padding=10)
        self.container.grid(row=0, column=0, sticky="nsew")
        
        # Title
        title_frame = ttk.Frame(self.container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(title_frame, text="LoRA Configuration Editor", style="Title.TLabel").pack(side=tk.LEFT)
        
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
        
        # History section
        history_frame = ttk.LabelFrame(self.container, text="LoRA History", padding=10)
        history_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        # Show inactive checkbox
        ttk.Checkbutton(
            history_frame,
            text="Show Inactive LoRAs",
            variable=self.show_inactive_var,
            command=self.refresh_tree
        ).pack(side=tk.LEFT, padx=5)
        
        # Activate/Deactivate buttons
        ttk.Button(
            history_frame,
            text="Activate Selected",
            command=self.activate_selected
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            history_frame,
            text="Deactivate Selected",
            command=self.deactivate_selected
        ).pack(side=tk.LEFT, padx=5)
        
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
        
        # Create treeview
        self.create_treeview()
        
        # Create buttons
        self.create_buttons()
        
        # Status bar
        status_bar = ttk.Label(self.container, textvariable=self.status_var, relief="sunken", padding=(5, 2))
        status_bar.grid(row=7, column=0, sticky="ew", pady=(10, 0))

    def create_treeview(self):
        tree_container = ttk.Frame(self.container)
        tree_container.grid(row=5, column=0, sticky="nsew", pady=(0, 10))
        
        # Create treeview
        tree_frame = ttk.Frame(tree_container)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        columns = ("ID", "Name", "File", "Weight", "Prompt", "Status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        # Configure columns
        widths = {"ID": 50, "Name": 200, "File": 300, "Weight": 100, "Prompt": 400, "Status": 100}
        for col, width in widths.items():
            self.tree.column(col, width=width, minwidth=width)
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Grid treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Reorder buttons frame
        reorder_frame = ttk.Frame(tree_container)
        reorder_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(reorder_frame, text="▲", width=3, command=self.move_up).pack(pady=2)
        ttk.Button(reorder_frame, text="▼", width=3, command=self.move_down).pack(pady=2)
        
        # Configure tree frame grid weights
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

    def create_buttons(self):
        btn_frame = ttk.Frame(self.container)
        btn_frame.grid(row=6, column=0, pady=10)
        
        buttons = [
            ("Add Entry", self.add_entry, "⊕"),
            ("Edit Entry", self.edit_entry, "✎"),
            ("Delete Entry", self.delete_entry, "✖"),
            ("Save", self.save_config, "💾"),
            ("Refresh Files", self.refresh_lora_files, "🔄")
        ]
        
        for text, command, symbol in buttons:
            btn = ttk.Button(btn_frame, text=f"{symbol} {text}", command=command, width=15)
            btn.pack(side=tk.LEFT, padx=5)

    def download_from_civitai(self):
        """Handle CivitAI download process"""
        url = self.civitai_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a CivitAI URL")
            return
            
        if not self.lora_folder:
            messagebox.showerror("Error", "Please select a LoRA folder first")
            return

        # Ensure the LoRA folder exists
        try:
            os.makedirs(self.lora_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create LoRA folder: {str(e)}")
            return

        # Show progress bar
        self.progress_frame.pack(fill=tk.X, pady=5)

        def run_download():
            temp_dir = None
            temp_file = None
            try:
                self.root.after(0, lambda: self.status_var.set("Getting model information..."))
                
                # Get model info
                model_info = self.downloader.get_model_info(url)
                if not model_info:
                    raise ValueError("Could not get model information from CivitAI")

                version_id = self.downloader.extract_version_id(url)
                if not version_id:
                    raise ValueError("Could not extract version ID from URL")

                # Create temporary download directory - using full path
                temp_dir = os.path.abspath(os.path.join(self.lora_folder, 'temp_download'))
                os.makedirs(temp_dir, exist_ok=True)

                try:
                    # Start download with progress tracking
                    self.root.after(0, lambda: self.status_var.set("Downloading LoRA file..."))
                    
                    # Download the file
                    temp_file = self.downloader.download_file(model_info, version_id, temp_dir)
                    if not temp_file or not os.path.exists(temp_file):
                        raise ValueError("Download failed")

                    # Get original filename
                    original_filename = os.path.basename(temp_file)

                    def show_file_dialog():
                        try:
                            self.progress_frame.pack_forget()
                            
                            # Show file naming dialog
                            dialog = FileNamingDialog(
                                self.root,
                                original_filename,
                                self.lora_folder
                            )
                            
                            if dialog.result:
                                # Use absolute paths
                                final_path = os.path.abspath(os.path.join(self.lora_folder, dialog.result))
                                temp_file_path = os.path.abspath(temp_file)
                                
                                try:
                                    # Ensure target directory exists
                                    os.makedirs(os.path.dirname(final_path), exist_ok=True)
                                    
                                    # Remove existing file if it exists
                                    if os.path.exists(final_path):
                                        os.remove(final_path)
                                    
                                    # Copy file instead of moving
                                    shutil.copy2(temp_file_path, final_path)
                                    
                                    # Get trigger words from model info
                                    trained_words = self.downloader.get_model_trained_words(url)
                                    trigger_prompt = ", ".join(trained_words) if trained_words else ""
                                    
                                    # Show entry dialog
                                    entry_dialog = EntryDialog(
                                        self.root,
                                        "Add LoRA Entry",
                                        {
                                            "name": os.path.splitext(dialog.result)[0].replace('_', ' ').title(),
                                            "file": dialog.result,
                                            "weight": "0.5",
                                            "prompt": trigger_prompt
                                        },
                                        available_files=self.available_lora_files + [dialog.result]
                                    )

                                    if entry_dialog.result:
                                        # Add to config
                                        new_entry = {
                                            "id": len(self.config.data["available_loras"]) + 1,
                                            "name": entry_dialog.result["name"],
                                            "file": dialog.result,
                                            "weight": float(entry_dialog.result["weight"]),
                                            "add_prompt": entry_dialog.result["prompt"]
                                        }
                                        self.config.data["available_loras"].append(new_entry)
                                        
                                        # Add to database
                                        self.db.add_lora(LoraHistoryEntry(
                                            file_name=dialog.result,
                                            display_name=entry_dialog.result["name"],
                                            trigger_words=entry_dialog.result["prompt"],
                                            weight=float(entry_dialog.result["weight"])
                                        ))
                                        
                                        self.refresh_tree()
                                        self.refresh_lora_files()
                                        self.status_var.set(f"Added new entry: {entry_dialog.result['name']}")

                                        # Save config after successful addition
                                        self.save_config()
                                        
                                except Exception as e:
                                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                                    logging.error(f"Error saving file: {str(e)}", exc_info=True)
                        finally:
                            # Clean up temporary files
                            try:
                                if temp_file and os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if temp_dir and os.path.exists(temp_dir):
                                    shutil.rmtree(temp_dir)
                            except Exception as e:
                                logging.error(f"Error cleaning up temporary files: {str(e)}")

                    self.root.after(0, show_file_dialog)

                except Exception as e:
                    raise Exception(f"Download failed: {str(e)}")

            except Exception as e:
                error_msg = str(e)
                logging.error(f"Error during CivitAI download: {error_msg}", exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.root.after(0, lambda: self.progress_frame.pack_forget())
                
                # Clean up on error
                try:
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass

        # Start download in separate thread
        threading.Thread(target=run_download, daemon=True).start()

    def download_from_huggingface(self):
        """Handle HuggingFace download process"""
        url = self.hf_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a HuggingFace URL")
            return

        # Get LoRA folder from environment variable if not set
        if not self.lora_folder:
            self.lora_folder = os.getenv('LORA_FOLDER_PATH')
            if not self.lora_folder:
                messagebox.showerror("Error", "LORA_FOLDER_PATH not set in .env file")
                return

        # Ensure the LoRA folder exists
        try:
            os.makedirs(self.lora_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create LoRA folder: {str(e)}")
            return

        # Show progress bar
        self.progress_frame.pack(fill=tk.X, pady=5)
        self.status_var.set("Starting download...")

        def run_download():
            temp_dir = None
            temp_file = None
            try:
                # Parse URL
                model_id = url.split('huggingface.co/')[-1].strip()
                if not model_id:
                    raise ValueError("Invalid HuggingFace URL")

                # Create temp directory
                temp_dir = os.path.join(self.lora_folder, 'temp_download')
                os.makedirs(temp_dir, exist_ok=True)

                # Initialize HF API
                hf_token = os.getenv('HUGGINGFACE_TOKEN')
                headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}

                # Download file
                try:
                    if '.safetensors' in url:
                        # Direct file URL
                        filename = url.split('/')[-1]
                        download_url = url
                    else:
                        # Get list of repository files
                        api = HfApi(token=hf_token)
                        files = api.list_repo_files(model_id)
                        safetensor_files = [f for f in files if f.endswith('.safetensors')]
                        if not safetensor_files:
                            raise ValueError("No .safetensors files found in repository")
                        filename = safetensor_files[0]
                        download_url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"

                    self.status_var.set("Downloading file...")
                    response = requests.get(download_url, headers=headers, stream=True)
                    response.raise_for_status()

                    # Get total file size
                    total_size = int(response.headers.get('content-length', 0))
                    temp_file = os.path.join(temp_dir, filename)

                    # Download with progress
                    chunk_size = 1024 * 1024  # 1MB chunks
                    downloaded = 0

                    with open(temp_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                                self.progress_var.set(progress)
                                self.root.update_idletasks()

                    def show_file_dialog():
                        try:
                            self.progress_frame.pack_forget()
                            
                            # Show file naming dialog
                            dialog = FileNamingDialog(
                                self.root,
                                filename,
                                self.lora_folder
                            )
                            
                            if dialog.result:
                                final_path = os.path.join(self.lora_folder, dialog.result)
                                try:
                                    # Ensure target directory exists
                                    os.makedirs(os.path.dirname(final_path), exist_ok=True)
                                    
                                    # Remove existing file if it exists
                                    if os.path.exists(final_path):
                                        os.remove(final_path)
                                    
                                    # Move file to final location
                                    shutil.move(temp_file, final_path)
                                    
                                    # Show entry dialog
                                    entry_dialog = EntryDialog(
                                        self.root,
                                        "Add LoRA Entry",
                                        {
                                            "name": os.path.splitext(dialog.result)[0].replace('_', ' ').title(),
                                            "file": dialog.result,
                                            "weight": "0.5",
                                            "prompt": ""
                                        },
                                        available_files=self.available_lora_files + [dialog.result]
                                    )

                                    if entry_dialog.result:
                                        # Add to config
                                        new_entry = {
                                            "id": len(self.config.data["available_loras"]) + 1,
                                            "name": entry_dialog.result["name"],
                                            "file": dialog.result,
                                            "weight": float(entry_dialog.result["weight"]),
                                            "add_prompt": entry_dialog.result["prompt"]
                                        }
                                        self.config.data["available_loras"].append(new_entry)
                                        
                                        # Add to database
                                        self.db.add_lora(LoraHistoryEntry(
                                            file_name=dialog.result,
                                            display_name=entry_dialog.result["name"],
                                            trigger_words=entry_dialog.result["prompt"],
                                            weight=float(entry_dialog.result["weight"])
                                        ))
                                        
                                        self.refresh_tree()
                                        self.refresh_lora_files()
                                        self.status_var.set(f"Added new entry: {entry_dialog.result['name']}")

                                        # Save config after successful addition
                                        self.save_config()
                                        
                                except Exception as e:
                                    messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                                    logging.error(f"Error saving file: {str(e)}", exc_info=True)
                        finally:
                            # Clean up temporary files
                            try:
                                if os.path.exists(temp_dir):
                                    shutil.rmtree(temp_dir)
                            except Exception as e:
                                logging.error(f"Error cleaning up temporary files: {str(e)}")

                    self.root.after(0, show_file_dialog)

                except Exception as e:
                    raise ValueError(f"Download failed: {str(e)}")

            except Exception as e:
                error_msg = str(e)
                logging.error(f"Error during HuggingFace download: {error_msg}", exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.root.after(0, lambda: self.progress_frame.pack_forget())
                
                # Clean up on error
                try:
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass

        # Start download in separate thread
        threading.Thread(target=run_download, daemon=True).start()

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
                self.update_env_file('LORA_JSON_PATH', filename)
                
                # Load the JSON file and update config
                self.config = lorautils.LoraConfig(filename)
                
                # Sync database with the newly loaded JSON
                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    self.db.sync_with_json(json_data)
                
                self.load_tree()
                self.update_status()
                self.refresh_lora_files()
                
                # Update default LoRA if it exists
                if self.config.data.get("default"):
                    self.default_var.set(self.config.data["default"])
        except Exception as e:
            logging.error(f"Error selecting JSON file: {e}")
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
            self.update_env_file('LORA_FOLDER_PATH', folder)
            self.refresh_lora_files()

    def update_progress(self, percentage):
        """Update the progress bar"""
        self.progress_var.set(percentage)
        self.root.update()

    def save_config(self):
        """Save configuration to both JSON and database"""
        try:
            # First get all active entries from database
            active_entries = self.db.get_lora_history(include_inactive=False)
            
            # Update config data to only include active entries
            self.config.data["available_loras"] = [
                {
                    "id": i+1,
                    "name": entry.display_name,
                    "file": entry.file_name,
                    "weight": entry.weight,
                    "add_prompt": entry.trigger_words
                }
                for i, entry in enumerate(active_entries)
            ]
            
            # Save to JSON file
            self.config.save_config()
            
            # Refresh the tree view to show current state
            self.refresh_tree()
            
            self.status_var.set("Configuration saved successfully!")
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def update_env_file(self, key: str, value: str):
        """Update a value in the .env file"""
        try:
            # Get parent directory path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env_path = os.path.join(parent_dir, '.env')
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            key_found = False
            for i, line in enumerate(lines):
                if line.startswith(f'{key}='):
                    lines[i] = f'{key}={value}\n'
                    key_found = True
                    break
            
            if not key_found:
                lines.append(f'{key}={value}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update .env file: {str(e)}")

    def refresh_tree(self):
        """Refresh the treeview with current data"""
        try:
            self.tree.delete(*self.tree.get_children())
            
            # Get entries from database
            entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
            
            # Update tree with entries
            for i, entry in enumerate(entries, 1):
                status = "Active" if entry.is_active else "Inactive"
                self.tree.insert("", tk.END, values=(
                    i,
                    entry.display_name,
                    entry.file_name,
                    entry.weight,
                    entry.trigger_words,
                    status
                ))
                
            self.update_status()
        except Exception as e:
            logging.error(f"Error refreshing tree: {e}")
            messagebox.showerror("Error", f"Failed to refresh display: {str(e)}")

    def refresh_lora_files(self):
        """Refresh the list of available LoRA files"""
        if self.lora_folder:
            self.available_lora_files = self.config.get_lora_files(self.lora_folder)

            # Update default LoRA combobox
            all_files = [lora["file"] for lora in self.config.data["available_loras"]]
            self.default_combo['values'] = all_files
            
            self.status_var.set(f"Found {len(self.available_lora_files)} LoRA files in folder")
        else:
            messagebox.showwarning("Warning", "Please select a LoRA folder first")

    def load_tree(self):
        """Load data into the treeview"""
        self.tree.delete(*self.tree.get_children())
        entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
        
        for i, entry in enumerate(entries, 1):
            status = "Active" if entry.is_active else "Inactive"
            self.tree.insert("", tk.END, values=(
                i,
                entry.display_name,
                entry.file_name,
                entry.weight,
                entry.trigger_words,
                status
            ))
        self.update_status()

    def update_status(self):
        """Update the status bar"""
        count = len(self.tree.get_children())
        self.status_var.set(f"Total entries: {count}")

    def filter_treeview(self, *args):
        """Filter the treeview based on search term"""
        search_term = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        for lora in self.config.data["available_loras"]: 
            if (search_term in str(lora.get("id", "")).lower() or
                search_term in lora.get("name", "").lower() or
                search_term in lora.get("file", "").lower() or
                search_term in str(lora.get("add_prompt", "")).lower()):
                self.tree.insert("", tk.END, values=(
                    lora.get("id", ""),
                    lora.get("name", ""),
                    lora.get("file", ""),
                    lora.get("weight", ""),
                    lora.get("add_prompt", "")
                ))

    def sort_treeview(self, col):
        """Sort treeview by column"""
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
        items.sort()
        for index, (val, item) in enumerate(items):
            self.tree.move(item, "", index)

    def move_up(self):
        """Move selected item up in the list"""
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        idx = self.tree.index(item)
        if idx > 0:  # Ensure it's not the first item
            # Get the previous item
            prev = self.tree.prev(item)
            
            # Swap items in the treeview
            self.tree.move(item, "", idx-1)
            
            # Swap items in the config data
            self.config.data["available_loras"][idx], self.config.data["available_loras"][idx-1] = \
                self.config.data["available_loras"][idx-1], self.config.data["available_loras"][idx]
            
            # Update IDs
            self.config.update_ids()
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

    def move_down(self):
        """Move selected item down in the list"""
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        idx = self.tree.index(item)
        if idx < len(self.tree.get_children()) - 1:  # Ensure it's not the last item
            # Get the next item
            next_item = self.tree.next(item)
            
            # Swap items in the treeview
            self.tree.move(item, "", idx+1)
            
            # Swap items in the config data
            self.config.data["available_loras"][idx], self.config.data["available_loras"][idx+1] = \
                self.config.data["available_loras"][idx+1], self.config.data["available_loras"][idx]
            
            # Update IDs
            self.config.update_ids()
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

    def update_default_lora(self, event=None):
        """Update the default LoRA selection"""
        self.config.data["default"] = self.default_var.get()
        self.status_var.set(f"Default LoRA set to: {self.default_var.get()}")

    def activate_selected(self):
        """Activate selected LoRA entries"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select entries to activate")
            return

        for item in selected:
            values = self.tree.item(item)["values"]
            file_name = values[2]  # file_name is in the third column
            if self.db.reactivate_lora(file_name):
                # Update the status in the treeview
                self.tree.set(item, "Status", "Active")
                self.status_var.set(f"Activated: {file_name}")
        
        # Save changes to config
        self.save_config()
        self.refresh_tree()

    def deactivate_selected(self):
        """Deactivate selected LoRA entries"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select entries to deactivate")
            return

        for item in selected:
            values = self.tree.item(item)["values"]
            file_name = values[2]  # file_name is in the third column
            if self.db.deactivate_lora(file_name):
                # Update the status in the treeview
                self.tree.set(item, "Status", "Inactive")
                self.status_var.set(f"Deactivated: {file_name}")
        
        # Save changes to config
        self.save_config()
        self.refresh_tree()

    def add_entry(self):
        """Add a new LoRA entry"""
        if not self.available_lora_files:
            messagebox.showwarning("Warning", "Please select a folder with LoRA files first")
            return 
            
        dialog = EntryDialog(self.root, "Add LoRA Entry", available_files=self.available_lora_files)
        if dialog.result:
            new_id = len(self.config.data["available_loras"]) + 1
            new_entry = {
                "id": new_id,
                "name": dialog.result["name"],
                "file": dialog.result["file"],
                "weight": float(dialog.result["weight"]),
                "add_prompt": dialog.result["prompt"]
            }
            
            # Add to JSON config
            self.config.data["available_loras"].append(new_entry)
            
            # Add to database
            self.db.add_lora(LoraHistoryEntry(
                file_name=dialog.result["file"],
                display_name=dialog.result["name"],
                trigger_words=dialog.result["prompt"],
                weight=float(dialog.result["weight"])
            ))
            
            self.refresh_tree()
            self.status_var.set(f"Added new entry: {dialog.result['name']}")

    def edit_entry(self):
        """Edit the selected LoRA entry"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an entry to edit")
            return 
            
        item = self.tree.item(selected[0])
        values = item["values"]
        
        dialog = EntryDialog(self.root, "Edit LoRA Entry", {
            "name": values[1],
            "file": values[2],
            "weight": values[3],
            "prompt": values[4]
        }, available_files=self.available_lora_files)
        
        if dialog.result:
            index = int(values[0]) - 1
            self.config.data["available_loras"][index].update({
                "name": dialog.result["name"],
                "file": dialog.result["file"],
                "weight": float(dialog.result["weight"]),
                "add_prompt": dialog.result["prompt"]
            })
            self.load_tree()
            self.status_var.set(f"Updated entry: {dialog.result['name']}")

    def delete_entry(self):
        """Delete the selected LoRA entry"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an entry to delete")
            return 
            
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this entry?"):
            try:
                item = self.tree.item(selected[0])
                values = item["values"]
                file_name = values[2]  # file_name is in the third column
                
                # Remove from JSON config
                index = int(values[0]) - 1
                deleted_name = self.config.data["available_loras"][index]["name"]
                del self.config.data["available_loras"][index]
                
                # Update IDs in JSON config
                self.config.update_ids()
                
                # Deactivate in database (soft delete)
                self.db.deactivate_lora(file_name)
                
                # Save changes
                self.save_config()
                
                # Refresh the tree view
                self.refresh_tree()
                
                self.status_var.set(f"Deleted entry: {deleted_name}")
                
            except Exception as e:
                logging.error(f"Error deleting entry: {e}")
                messagebox.showerror("Error", f"Failed to delete entry: {str(e)}")

    def update_default_lora(self, event=None):
        """Update the default LoRA selection"""
        self.config.data["default"] = self.default_var.get()
        self.save_config()
        self.status_var.set(f"Default LoRA set to: {self.default_var.get()}")

    def activate_selected(self):
        """Activate selected LoRA entries"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select entries to activate")
            return

        for item in selected:
            values = self.tree.item(item)["values"]
            file_name = values[2]  # file_name is in the third column
            if self.db.reactivate_lora(file_name):
                # Update the status in the treeview
                self.tree.set(item, "Status", "Active")
                self.status_var.set(f"Activated: {file_name}")
        
        # Save changes to config
        self.save_config()
        self.refresh_tree()

    def deactivate_selected(self):
        """Deactivate selected LoRA entries"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select entries to deactivate")
            return

        for item in selected:
            values = self.tree.item(item)["values"]
            file_name = values[2]  # file_name is in the third column
            if self.db.deactivate_lora(file_name):
                # Update the status in the treeview
                self.tree.set(item, "Status", "Inactive")
                self.status_var.set(f"Deactivated: {file_name}")
        
        # Save changes to config
        self.save_config()
        self.refresh_tree()

    def update_env_file(self, key: str, value: str):
        """Update a value in the .env file"""
        try:
            # Get parent directory path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env_path = os.path.join(parent_dir, '.env')
            
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            key_found = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f'{key}='):
                    if key in ['LORA_FOLDER_PATH', 'LORA_JSON_PATH']:
                        # Use forward slashes and preserve quotes for paths
                        value = value.replace('\\', '/')
                        lines[i] = f'{key}="{value}"\n'
                    else:
                        lines[i] = f'{key}={value}\n'
                    key_found = True
                    break
            
            if not key_found:
                if key in ['LORA_FOLDER_PATH', 'LORA_JSON_PATH']:
                    # Use forward slashes and preserve quotes for paths
                    value = value.replace('\\', '/')
                    lines.append(f'{key}="{value}"\n')
                else:
                    lines.append(f'{key}={value}\n')
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update .env file: {str(e)}")

# Main function to start the application
def main():
    try:
        root = tk.Tk()
        app = LoraEditor(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Application error: {str(e)}", exc_info=True)
        messagebox.showerror("Error", f"Application error: {str(e)}")

if __name__ == "__main__":
    main()