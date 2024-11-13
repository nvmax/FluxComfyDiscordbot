import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from urllib.parse import urlparse, unquote
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from lorautils import LoraConfig, CivitAIDownloader
from lora_database import LoraDatabase, LoraHistoryEntry
from EntryDialog import EntryDialog
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')
import json
import requests
import shutil
import sqlite3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_filename(filename):
    """Remove or replace characters that are invalid in Windows filenames"""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    return sanitized[:240]

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


class LoraEditor:
    def __init__(self, root: tk.Tk):  # Add the root parameter with type hint
        load_dotenv()
        
        self.root = root
        self.root.title("LoRA Configuration Editor")
        self.root.geometry("1225x825")
        
        self.db = LoraDatabase()  # Initialize database
        self.show_inactive_var = tk.BooleanVar(value=False)  # Add this variable
        
        self.setup_styles()
        self.init_variables()
        self.create_ui()
        
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        
        self.load_tree()
        self.update_status()
        self.refresh_lora_files()

    def sync_database_order(self):
        """Synchronize database order with current treeview state"""
        try:
            # Get all items from treeview in current order
            items = []
            for item in self.tree.get_children():
                values = self.tree.item(item)["values"]
                items.append({
                    "file_name": values[2],      # file name
                    "display_name": values[1],    # name
                    "weight": {
                        "min": float(values[3]),  # min weight
                        "max": float(values[4])   # max weight
                    },
                    "trigger_words": values[5],   # prompt/trigger words
                    "is_active": values[6] == "Active",  # status
                    "URL": values[7]             # URL
                })
            
            # Recreate database table with new order
            with sqlite3.connect(self.db.db_path) as conn:
                c = conn.cursor()
                # Create temporary table
                c.execute('''CREATE TABLE IF NOT EXISTS temp_lora_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    trigger_words TEXT,
                    weight_min REAL NOT NULL,
                    weight_max REAL NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                # Insert items in new order
                for item in items:
                    c.execute('''INSERT INTO temp_lora_history 
                            (file_name, display_name, trigger_words, weight_min, weight_max, is_active)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (item["file_name"], item["display_name"], 
                            item["trigger_words"], 
                            item["weight"]["min"], item["weight"]["max"],
                            item["is_active"]))
                
                # Drop original table and rename temp table
                c.execute('DROP TABLE lora_history')
                c.execute('ALTER TABLE temp_lora_history RENAME TO lora_history')
                
        except Exception as e:
            logging.error(f"Error syncing database order: {e}")
            raise
    
    def init_variables(self):
        """Initialize main variables and objects"""
        try:
            # Get paths from environment variables
            self.json_path = os.getenv('LORA_JSON_PATH', 'lora.json')
            self.lora_folder = os.getenv('LORA_FOLDER_PATH', '')
            
            # Initialize config with the specified JSON path
            self.config = LoraConfig(self.json_path)
            
            # Sync database with existing JSON if it exists
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    self.db.sync_with_json(json_data)
                except Exception as e:
                    logging.error(f"Error syncing database with JSON: {e}")
            
            # Initialize other variables
            self.downloader = CivitAIDownloader(self.update_progress)
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
        """Configure ttk styles for a more native look"""
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
        
        # Add style for the Reset button
        self.style.configure("Red.TButton",
            font=('Segoe UI', 9),
            foreground='red',
            padding=5
        )

    def create_ui(self):
        """Create the main UI layout"""
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
        self.create_history_controls()
        
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
        status_bar = ttk.Label(self.container, textvariable=self.status_var, relief="sunken", padding=(5, 2))
        status_bar.grid(row=7, column=0, sticky="ew", pady=(10, 0))

    def create_treeview(self):
        """Create the treeview with reorder buttons"""
        tree_container = ttk.Frame(self.container)
        tree_container.grid(row=5, column=0, sticky="nsew", pady=(0, 10))
        
        # Create treeview
        tree_frame = ttk.Frame(tree_container)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        columns = ("ID", "Name", "File", "Min Weight", "Max Weight", "Prompt", "Status", "URL")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        # Configure columns
        widths = {
            "ID": 50,
            "Name": 200,
            "File": 200,
            "Min Weight": 80,
            "Max Weight": 80,
            "Prompt": 200,
            "Status": 70,
            "URL": 200
        }
        
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
        
        # Single position move buttons
        ttk.Button(reorder_frame, text="▲", width=3, command=self.move_up).pack(pady=2)
        ttk.Button(reorder_frame, text="▼", width=3, command=self.move_down).pack(pady=2)
        
        # Add separator
        ttk.Separator(reorder_frame, orient='horizontal').pack(fill='x', pady=5)
        
        # Multiple position move buttons
        ttk.Button(reorder_frame, text="▲▲", width=3, command=self.move_up_five).pack(pady=2)
        ttk.Button(reorder_frame, text="▼▼", width=3, command=self.move_down_five).pack(pady=2)
        
        # Configure tree frame grid weights
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

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
                width=15,
                style="Red.TButton" if text == "Reset LoRA" else "TButton"
            )
            btn.pack(side=tk.LEFT, padx=5)

    def update_progress(self, percentage):
        """Update the progress bar"""
        self.progress_var.set(percentage)
        self.root.update()

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
                self.config = LoraConfig(filename)
                
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

    def download_from_civitai(self):
        """Handle CivitAI download process"""
        url = self.civitai_url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a CivitAI URL")
            return
            
        if not self.lora_folder:
            messagebox.showerror("Error", "Please select a LoRA folder first")
            return

        # Show progress bar
        self.progress_frame.pack(fill=tk.X, pady=5)

        def run_download():
            temp_dir = None
            try:
                # Get download URL
                download_url = self.downloader.get_download_url(url)
                if not download_url:
                    raise ValueError("Could not get download URL")

                # Create temporary directory
                temp_dir = os.path.join(self.lora_folder, 'temp_download')
                os.makedirs(temp_dir, exist_ok=True)

                # Download with progress tracking
                self.root.after(0, lambda: self.status_var.set("Downloading LoRA file..."))
                
                response = requests.get(download_url, 
                                    headers=self.downloader.headers, 
                                    stream=True,
                                    timeout=30)
                response.raise_for_status()

                # Get filename from content disposition or URL
                content_disposition = response.headers.get('content-disposition')
                if content_disposition:
                    filename = re.findall("filename=(.+)", content_disposition)[0].strip('"')
                else:
                    filename = download_url.split('/')[-1]
                
                filename = sanitize_filename(filename)
                temp_file = os.path.join(temp_dir, filename)

                # Download with progress tracking
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024 * 1024  # 1MB chunks
                downloaded_size = 0

                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            downloaded_size += len(chunk)
                            f.write(chunk)
                            if total_size:
                                progress = (downloaded_size / total_size) * 100
                                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                def show_file_dialog():
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
                            # Move file to final location
                            if os.path.exists(final_path):
                                os.remove(final_path)
                            shutil.move(temp_file, final_path)
                            
                            # Get trigger words from CivitAI
                            trigger_words = " ".join(self.downloader.get_model_trained_words(url))
                            
                            # Show entry dialog with standardized weights
                            entry_dialog = EntryDialog(
                                self.root,
                                "Add LoRA Entry",
                                {
                                    "name": os.path.splitext(dialog.result)[0].replace('_', ' ').title(),
                                    "file": dialog.result,
                                    "weight": {
                                        "min": 0.5,  # Always set to 0.5
                                        "max": 1.0   # Always set to 1.0
                                    },
                                    "prompt": trigger_words,
                                    "URL": url
                                },
                                available_files=self.available_lora_files + [dialog.result]
                            )

                            if entry_dialog.result:
                                # Add to database
                                self.db.add_lora(LoraHistoryEntry(
                                    file_name=dialog.result,
                                    display_name=entry_dialog.result["name"],
                                    trigger_words=entry_dialog.result["prompt"],
                                    weight={
                                        "min": 0.5,  # Standardized min weight
                                        "max": 1.0   # Standardized max weight
                                    },
                                    is_active=True
                                ))
                                
                                # Add to JSON config
                                new_entry = {
                                    "id": len(self.config.data["available_loras"]) + 1,
                                    "name": entry_dialog.result["name"],
                                    "file": dialog.result,
                                    "weight": {
                                        "min": 0.5,
                                        "max": 1.0
                                    },
                                    "add_prompt": entry_dialog.result["prompt"],
                                    "URL": url
                                }
                                self.config.data["available_loras"].append(new_entry)

                                # Save config file
                                self.config.save_config()
                                
                                # Insert into treeview
                                self.tree.insert("", tk.END, values=(
                                    new_entry["id"],
                                    new_entry["name"],
                                    new_entry["file"],
                                    "0.50",  # min weight formatted
                                    "1.00",  # max weight formatted
                                    new_entry["add_prompt"],
                                    "Active",
                                    new_entry["URL"]
                                ))

                                # Update UI
                                self.refresh_lora_files()
                                self.status_var.set(f"Added new entry: {entry_dialog.result['name']}")

                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                            logging.error(f"Error saving file: {str(e)}", exc_info=True)
                    
                    # Clean up temp directory
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                    except Exception as e:
                        logging.error(f"Error cleaning up temp directory: {str(e)}")

                self.root.after(0, show_file_dialog)

            except Exception as e:
                error_msg = f"Download error: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.progress_frame.pack_forget()
                
                # Clean up on error
                try:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass

        # Start download in separate thread
        threading.Thread(target=run_download, daemon=True).start()

    def download_from_huggingface(self):
        """Handle HuggingFace download process"""
        input_url = self.hf_url_var.get().strip()
        if not input_url:
            messagebox.showerror("Error", "Please enter a HuggingFace URL")
            return
            
        if not self.lora_folder:
            messagebox.showerror("Error", "Please select a LoRA folder first")
            return

        # Show progress bar
        self.progress_frame.pack(fill=tk.X, pady=5)

        def run_download(input_url):
            temp_dir = None
            try:
                # Parse repo ID and filename from URL
                parsed_url = urlparse(input_url)
                path_parts = parsed_url.path.strip('/').split('/')
                if len(path_parts) < 2:
                    raise ValueError("Invalid HuggingFace URL format")
                
                repo_id = '/'.join(path_parts[:2])
                filename = path_parts[-1] if len(path_parts) > 2 else None

                # Initialize HF API
                hf_token = os.getenv('HUGGINGFACE_TOKEN')
                api = HfApi(token=hf_token)

                if not filename:
                    # Get list of files in repo
                    self.root.after(0, lambda: self.status_var.set("Searching for SafeTensor files..."))
                    files = api.list_repo_files(repo_id)
                    safetensor_files = [f for f in files if f.endswith('.safetensors')]
                    if not safetensor_files:
                        raise ValueError("No .safetensors files found in repository")
                    filename = safetensor_files[0]

                # Create temporary directory
                temp_dir = os.path.join(self.lora_folder, 'temp_download')
                os.makedirs(temp_dir, exist_ok=True)

                # Get file size first
                self.root.after(0, lambda: self.status_var.set("Getting file information..."))
                headers = {}
                if hf_token:
                    headers["Authorization"] = f"Bearer {hf_token}"
                
                download_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
                response = requests.head(download_url, headers=headers, allow_redirects=True)
                total_size = int(response.headers.get('content-length', 0))

                # Download with progress tracking
                self.root.after(0, lambda: self.status_var.set("Downloading LoRA file..."))
                response = requests.get(download_url, headers=headers, stream=True)
                temp_file = os.path.join(temp_dir, os.path.basename(filename))
                
                downloaded_size = 0
                chunk_size = 1024 * 1024  # 1MB chunks

                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                            self.root.after(0, lambda p=progress: self.progress_var.set(p))

                downloaded_filename = os.path.basename(temp_file)

                def show_file_dialog():
                    self.progress_frame.pack_forget()
                    
                    # Show file naming dialog
                    dialog = FileNamingDialog(
                        self.root,
                        downloaded_filename,
                        self.lora_folder
                    )
                    
                    if dialog.result:
                        final_path = os.path.join(self.lora_folder, dialog.result)
                        try:
                            # Remove existing file if it exists
                            if os.path.exists(final_path):
                                os.remove(final_path)
                            
                            # Move file to final location
                            shutil.move(temp_file, final_path)
                            
                            # Show entry dialog with standardized weights
                            entry_dialog = EntryDialog(
                                self.root,
                                "Add LoRA Entry",
                                {
                                    "name": os.path.splitext(dialog.result)[0].replace('_', ' ').title(),
                                    "file": dialog.result,
                                    "weight": {
                                        "min": 0.5,  # Always set to 0.5
                                        "max": 1.0   # Always set to 1.0
                                    },
                                    "prompt": "",
                                    "URL": input_url
                                },
                                available_files=self.available_lora_files + [dialog.result]
                            )

                            if entry_dialog.result:
                                # Add to database
                                self.db.add_lora(LoraHistoryEntry(
                                    file_name=dialog.result,
                                    display_name=entry_dialog.result["name"],
                                    trigger_words=entry_dialog.result["prompt"],
                                    weight={
                                        "min": 0.5,
                                        "max": 1.0
                                    },
                                    is_active=True
                                ))

                                # Add to JSON config
                                new_entry = {
                                    "id": len(self.config.data["available_loras"]) + 1,
                                    "name": entry_dialog.result["name"],
                                    "file": dialog.result,
                                    "weight": {
                                        "min": 0.5,
                                        "max": 1.0
                                    },
                                    "add_prompt": entry_dialog.result["prompt"],
                                    "URL": input_url
                                }
                                self.config.data["available_loras"].append(new_entry)
                                
                                # Save config file
                                self.config.save_config()
                                
                                # Insert into treeview
                                self.tree.insert("", tk.END, values=(
                                    new_entry["id"],
                                    new_entry["name"],
                                    new_entry["file"],
                                    "0.50",  # min weight formatted
                                    "1.00",  # max weight formatted
                                    new_entry["add_prompt"],
                                    "Active",
                                    new_entry["URL"]
                                ))

                                # Update UI
                                self.refresh_lora_files()
                                self.status_var.set(f"Added new entry: {entry_dialog.result['name']}")

                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                            logging.error(f"Error saving file: {str(e)}", exc_info=True)

                    # Clean up temporary directory
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                    except Exception as e:
                        logging.error(f"Error cleaning up temp directory: {str(e)}")

                self.root.after(0, show_file_dialog)

            except Exception as e:
                error_msg = f"Download error: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.progress_frame.pack_forget()
                
                # Clean up on error
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass

        # Start the download thread with the URL parameter
        threading.Thread(target=run_download, args=(input_url,), daemon=True).start()

    def update_default_lora(self, event=None):
        """Update the default LoRA selection"""
        self.config.data["default"] = self.default_var.get()
        self.status_var.set(f"Default LoRA set to: {self.default_var.get()}")

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

    def refresh_tree(self):
        """Refresh the treeview with current data"""
        try:
            self.tree.delete(*self.tree.get_children())
            
            # Get entries from database
            entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
            
            # Update tree with entries
            for i, entry in enumerate(entries, 1):
                status = "Active" if entry.is_active else "Inactive"
                
                # Find URL from config
                config_entry = next(
                    (lora for lora in self.config.data.get("available_loras", [])
                    if lora.get("file") == entry.file_name),
                    None
                )
                url = config_entry.get("URL", "") if config_entry else ""
                
                self.tree.insert("", tk.END, values=(
                    i,
                    entry.display_name,
                    entry.file_name,
                    f"{entry.weight['min']:.2f}",
                    f"{entry.weight['max']:.2f}",
                    entry.trigger_words,
                    status,
                    url
                ))
                
            self.update_status()
        except Exception as e:
            logging.error(f"Error refreshing tree: {e}")
            messagebox.showerror("Error", f"Failed to refresh display: {str(e)}")

    def load_tree(self):
        """Load data into the treeview"""
        self.tree.delete(*self.tree.get_children())
        entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
        
        for i, entry in enumerate(entries, 1):
            status = "Active" if entry.is_active else "Inactive"
            
            # Find URL from config
            config_entry = next(
                (lora for lora in self.config.data.get("available_loras", [])
                if lora.get("file") == entry.file_name),
                None
            )
            url = config_entry.get("URL", "") if config_entry else ""
            
            self.tree.insert("", tk.END, values=(
                i,
                entry.display_name,
                entry.file_name,
                f"{entry.weight['min']:.2f}",
                f"{entry.weight['max']:.2f}",
                entry.trigger_words,
                status,
                url
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
        
        entries = self.db.get_lora_history(include_inactive=self.show_inactive_var.get())
        
        for i, entry in enumerate(entries, 1):
            if (search_term in str(i).lower() or
                search_term in entry.display_name.lower() or
                search_term in entry.file_name.lower() or
                search_term in entry.trigger_words.lower()):
                
                status = "Active" if entry.is_active else "Inactive"
                
                # Find URL from config
                config_entry = next(
                    (lora for lora in self.config.data.get("available_loras", [])
                    if lora.get("file") == entry.file_name),
                    None
                )
                url = config_entry.get("URL", "") if config_entry else ""
                
                self.tree.insert("", tk.END, values=(
                    i,
                    entry.display_name,
                    entry.file_name,
                    f"{entry.weight['min']:.2f}",
                    f"{entry.weight['max']:.2f}",
                    entry.trigger_words,
                    status,
                    url
                ))

    def sort_treeview(self, col):
        """Sort treeview by column"""
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
        items.sort()
        for index, (val, item) in enumerate(items):
            self.tree.move(item, "", index)

    def create_history_controls(self):
        """Create history control section"""
        history_frame = ttk.LabelFrame(self.container, text="LoRA History", padding=10)
        history_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        # Checkbox for showing inactive LoRAs
        self.show_inactive_var = tk.BooleanVar(value=False)
        show_inactive_cb = ttk.Checkbutton(
            history_frame, 
            text="Show Inactive LoRAs",
            variable=self.show_inactive_var,
            command=self.refresh_tree
        )
        show_inactive_cb.pack(side=tk.LEFT, padx=5)
        
        # Buttons for activating/deactivating
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
            try:
                new_id = len(self.config.data["available_loras"]) + 1
                new_entry = {
                    "id": new_id,
                    "name": dialog.result["name"],
                    "file": dialog.result["file"],
                    "weight": {
                        "min": 0.5,
                        "max": 1.0
                    },
                    "add_prompt": dialog.result["prompt"],
                    "URL": dialog.result["URL"]
                }
                
                # Add to JSON config
                self.config.data["available_loras"].append(new_entry)
                
                # Add to database
                self.db.add_lora(LoraHistoryEntry(
                    file_name=dialog.result["file"],
                    display_name=dialog.result["name"],
                    trigger_words=dialog.result["prompt"],
                    weight={
                        "min": 0.5,
                        "max": 1.0
                    },
                    is_active=True
                ))
                
                # Insert into treeview
                self.tree.insert("", tk.END, values=(
                    new_entry["id"],
                    new_entry["name"],
                    new_entry["file"],
                    "0.50",  # min weight formatted
                    "1.00",  # max weight formatted
                    new_entry["add_prompt"],
                    "Active",
                    new_entry["URL"]
                ))
                
                # Save and update
                self.save_config()
                self.refresh_lora_files()
                self.status_var.set(f"Added new entry: {dialog.result['name']}")
                
            except Exception as e:
                logging.error(f"Error adding entry: {e}")
                messagebox.showerror("Error", f"Failed to add entry: {str(e)}")

    def edit_entry(self):
        """Edit the selected LoRA entry"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an entry to edit")
            return 
            
        item = self.tree.item(selected[0])
        values = item["values"]
        
        initial_data = {
            "name": values[1],
            "file": values[2],
            "weight": {
                "min": float(values[3]),
                "max": float(values[4])
            },
            "prompt": values[5],
            "URL": values[7]
        }
        
        dialog = EntryDialog(self.root, "Edit LoRA Entry", initial_data, available_files=self.available_lora_files)
        
        if dialog.result:
            try:
                # Update database entry
                self.db.add_lora(LoraHistoryEntry(
                    file_name=dialog.result["file"],
                    display_name=dialog.result["name"],
                    trigger_words=dialog.result["prompt"],
                    weight={
                        "min": 0.5,
                        "max": 1.0
                    },
                    is_active=True
                ))
                
                # Update JSON config
                index = int(values[0]) - 1  # Get index from ID column
                updated_entry = {
                    "id": index + 1,
                    "name": dialog.result["name"],
                    "file": dialog.result["file"],
                    "weight": {
                        "min": 0.5,
                        "max": 1.0
                    },
                    "add_prompt": dialog.result["prompt"],
                    "URL": dialog.result["URL"]
                }
                self.config.data["available_loras"][index] = updated_entry
                
                # Update treeview entry
                self.tree.item(selected[0], values=(
                    updated_entry["id"],
                    updated_entry["name"],
                    updated_entry["file"],
                    "0.50",  # min weight formatted
                    "1.00",  # max weight formatted
                    updated_entry["add_prompt"],
                    "Active",
                    updated_entry["URL"]
                ))
                
                # Save and update
                self.save_config()
                self.refresh_lora_files()
                self.status_var.set(f"Updated entry: {dialog.result['name']}")
                
            except Exception as e:
                logging.error(f"Error updating entry: {e}")
                messagebox.showerror("Error", f"Failed to update entry: {str(e)}")

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
                
                # Remove from treeview
                self.tree.delete(selected[0])
                
                # Remove from JSON config
                self.config.data["available_loras"] = [
                    entry for entry in self.config.data["available_loras"]
                    if entry.get("file") != file_name
                ]
                
                # Update IDs in remaining entries
                for i, entry in enumerate(self.config.data["available_loras"], 1):
                    entry["id"] = i
                
                # Save JSON config
                self.config.save_config()
                
                # Deactivate in database
                self.db.deactivate_lora(file_name)
                
                # Clear default if this was the default
                if self.default_var.get() == file_name:
                    self.default_var.set("")
                    self.config.data["default"] = ""
                
                # Update UI
                self.refresh_lora_files()  # Update available files list
                self.default_combo['values'] = [lora["file"] for lora in self.config.data["available_loras"]]
                
                # Update status
                deleted_name = values[1]  # Name is in the second column
                self.status_var.set(f"Deleted entry: {deleted_name}")
                
            except Exception as e:
                logging.error(f"Error deleting entry: {e}")
                messagebox.showerror("Error", f"Failed to delete entry: {str(e)}")
                
            finally:
                # Refresh the tree to ensure proper order and IDs
                self.refresh_tree()

    def reset_lora(self):
        """Reset all LoRA entries"""
        # Show warning dialog
        result = messagebox.askokcancel(
            "Warning",
            "⚠ This will remove all LoRAs from your list!\n\n"
            "Are you sure you want to continue?",
            icon='warning'
        )
        
        if result:
            try:
                # Clear JSON config
                self.config.data["available_loras"] = []
                self.config.data["default"] = ""
                self.config.save_config()
                
                # Clear database (deactivate all entries)
                with sqlite3.connect(self.db.db_path) as conn:
                    c = conn.cursor()
                    c.execute('UPDATE lora_history SET is_active = 0')
                    conn.commit()
                
                # Clear treeview
                self.tree.delete(*self.tree.get_children())
                
                # Update UI elements
                self.default_var.set("")
                self.default_combo['values'] = []
                
                # Refresh displays
                self.refresh_tree()
                self.refresh_lora_files()
                
                # Update status
                self.status_var.set("All LoRA entries have been reset")
                
                # Show confirmation
                messagebox.showinfo(
                    "Reset Complete",
                    "All LoRA entries have been successfully removed."
                )
                
            except Exception as e:
                logging.error(f"Error resetting LoRA entries: {e}")
                messagebox.showerror(
                    "Error",
                    f"Failed to reset LoRA entries: {str(e)}"
                )

    def save_config(self):
        """Save configuration to both JSON and database"""
        try:
            # Save current treeview state to config
            self.config.data["available_loras"] = []
            for i, item in enumerate(self.tree.get_children(), 1):
                values = self.tree.item(item)["values"]
                if values[6] == "Active":  # Only include active entries
                    self.config.data["available_loras"].append({
                        "id": i,
                        "name": values[1],
                        "file": values[2],
                        "weight": {
                            "min": 0.5,
                            "max": 1.0
                        },
                        "add_prompt": values[5],
                        "URL": values[7]
                    })
            
            # Save to JSON file
            self.config.save_config()
            
            # Sync database with current treeview state
            self.sync_database_order()
            
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
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

            # Save changes
            self.sync_database_order()
            self.save_config()

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
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

            # Save changes
            self.sync_database_order()
            self.save_config()

    def move_up_five(self):
        """Move selected item up 5 positions"""
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        current_idx = self.tree.index(item)
        target_idx = max(0, current_idx - 5)  # Don't go above 0
        
        if current_idx > target_idx:  # Only move if we're not already at the top
            # Move the item
            self.tree.move(item, "", target_idx)
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

            # Save changes
            self.sync_database_order()
            self.save_config()

    def move_down_five(self):
        """Move selected item down 5 positions"""
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        current_idx = self.tree.index(item)
        max_idx = len(self.tree.get_children()) - 1
        target_idx = min(max_idx, current_idx + 5)  # Don't go below max index
        
        if current_idx < target_idx:  # Only move if we're not already at the bottom
            # Move the item
            self.tree.move(item, "", target_idx)
            
            # Keep selection on moved item
            self.tree.selection_set(item)
            self.tree.see(item)

            # Save changes
            self.sync_database_order()
            self.save_config()

def main():
    root = tk.Tk()
    app = LoraEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()