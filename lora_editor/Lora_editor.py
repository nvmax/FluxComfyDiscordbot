import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from dotenv import load_dotenv
from pathlib import Path
from lorautils import LoraConfig, CivitAIDownloader
import logging

class LoraEditor:
    def __init__(self, root):
        load_dotenv()
        
        self.root = root
        self.root.title("LoRA Config Editor")
        self.root.geometry("1225x725")
        
        self.setup_styles()
        self.init_variables()
        self.create_ui()
        
        # Configure grid weights
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        
        self.load_tree()
        self.update_status()
        self.refresh_lora_files()

    def init_variables(self):
        """Initialize main variables and objects"""
        self.json_path = os.getenv('LORA_JSON_PATH', 'lora.json')
        self.config = LoraConfig(self.json_path)
        self.lora_folder = os.getenv('LORA_FOLDER_PATH', '')
        self.downloader = CivitAIDownloader(self.update_progress)
        self.folder_var = tk.StringVar(value=self.lora_folder)
        self.json_var = tk.StringVar(value=self.json_path)
        self.search_var = tk.StringVar()
        self.default_var = tk.StringVar(value=self.config.data.get("default", ""))
        self.status_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.available_lora_files = []

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
        
        # CivitAI Download section
        download_frame = ttk.LabelFrame(self.container, text="CivitAI Download", padding=10)
        download_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        url_frame = ttk.Frame(download_frame)
        url_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(url_frame, text="CivitAI URL:").pack(side=tk.LEFT, padx=(0, 5))
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=80)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(url_frame, text="Download", command=self.download_from_civitai).pack(side=tk.LEFT)
        
        # Progress bar (hidden by default)
        self.progress_frame = ttk.Frame(download_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5)
        self.progress_frame.pack_forget()
        
        # Default LoRA selection
        default_frame = ttk.Frame(self.container)
        default_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
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
        
        columns = ("ID", "Name", "File", "Weight", "Prompt")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        # Configure columns
        widths = {"ID": 50, "Name": 200, "File": 300, "Weight": 100, "Prompt": 500}
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
        """Create the main action buttons"""
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

    def update_progress(self, percentage):
        """Update the progress bar"""
        self.progress_var.set(percentage)
        self.root.update()

    def select_json(self):
        """Handle JSON file selection"""
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
            self.config = LoraConfig(filename)
            self.load_tree()
            self.update_status()
            self.refresh_lora_files()

    def update_env_file(self, key: str, value: str):
        """Update a value in the .env file"""
        try:
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
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
            
            with open('.env', 'w') as f:
                f.writelines(lines)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update .env file: {str(e)}")

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
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a CivitAI URL")
            return
            
        if not self.lora_folder:
            messagebox.showerror("Error", "Please select a LoRA folder first")
            return

        # Show progress bar immediately
        self.progress_frame.pack(fill=tk.X, pady=5)

        def update_ui(success: bool, message: str):
            """Helper function to update UI"""
            self.progress_frame.pack_forget()
            if success:
                self.load_tree()
                self.refresh_lora_files()
                self.status_var.set(message)
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)

        def run_download():
            try:
                model_id, version_id = self.downloader.extract_model_id(url)
                model_info = self.downloader.get_model_info(model_id)
                
                if version_id:
                    version = next((v for v in model_info['modelVersions'] if str(v['id']) == version_id), None)
                    if not version:
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Version ID {version_id} not found"))
                        return
                else:
                    version = model_info['modelVersions'][0]
                
                version_id = str(version['id'])
                filename = self.downloader.download_file(model_info, version_id, self.lora_folder)
                
                trigger_words = self.downloader.get_model_trained_words(model_info, version_id)

                def show_entry_dialog():
                    self.progress_frame.pack_forget()
                    dialog = EntryDialog(
                        self.root, 
                        "Add LoRA Entry",
                        {
                            "name": model_info['name'],
                            "file": os.path.basename(filename),
                            "weight": "0.5",
                            "prompt": ", ".join(trigger_words)
                        },
                        available_files=self.available_lora_files
                    )

                    if dialog.result:
                        new_entry = {
                            "id": len(self.config.data["available_loras"]) + 1,
                            "name": dialog.result["name"],
                            "file": dialog.result["file"],
                            "weight": float(dialog.result["weight"]),
                            "add_prompt": dialog.result["prompt"]
                        }
                        self.config.data["available_loras"].append(new_entry)
                        self.load_tree()
                        self.status_var.set(f"Added new entry: {dialog.result['name']}") 
                
                self.root.after(0, show_entry_dialog)

            except Exception as e:
                error_msg = f"Download error: {str(e)}"
                logging.error(f"Download error: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.progress_frame.pack_forget()

        threading.Thread(target=run_download, daemon=True).start()

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

    def load_tree(self):
        """Load data into the treeview"""
        self.tree.delete(*self.tree.get_children())
        for lora in self.config.data["available_loras"]:
            self.tree.insert("", tk.END, values=(
                lora.get("id", ""),
                lora.get("name", ""),
                lora.get("file", ""),
                lora.get("weight", ""),
                lora.get("add_prompt", "")
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
        if idx > 0:
            # Update data list
            self.config.data["available_loras"][idx], self.config.data["available_loras"][idx-1] = \
                self.config.data["available_loras"][idx-1], self.config.data["available_loras"][idx]
            
            # Update IDs 
            self.config.update_ids()
            
            # Reload tree and reselect item
            self.load_tree()
            new_item = self.tree.get_children()[idx-1]
            self.tree.selection_set(new_item)
            self.tree.see(new_item)

    def move_down(self):
        """Move selected item down in the list"""
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        idx = self.tree.index(item)
        if idx < len(self.config.data["available_loras"]) - 1:
            # Update data list
            self.config.data["available_loras"][idx], self.config.data["available_loras"][idx+1] = \
                self.config.data["available_loras"][idx+1], self.config.data["available_loras"][idx]
            
            # Update IDs 
            self.config.update_ids()
            
            # Reload tree and reselect item
            self.load_tree()
            new_item = self.tree.get_children()[idx+1]
            self.tree.selection_set(new_item)
            self.tree.see(new_item)

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
            self.config.data["available_loras"].append(new_entry)
            self.load_tree()
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
            item = self.tree.item(selected[0])
            index = int(item["values"][0]) - 1
            deleted_name = self.config.data["available_loras"][index]["name"]
            del self.config.data["available_loras"][index]
            
            # Update IDs 
            self.config.update_ids()
            
            self.load_tree()
            self.status_var.set(f"Deleted entry: {deleted_name}")

    def save_config(self):
        """Save the configuration to file"""
        try:
            self.config.save_config()
            self.status_var.set("Configuration saved successfully!")
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")


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

        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        
        parent.wait_window(self.dialog)

    def setup_ui(self, initial):
        """Set up the dialog UI"""
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
        """Center the dialog relative to parent window"""
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
        """Validate weight input"""
        if new_value == "":
            return True
        try:
            value = float(new_value)
            return 0 <= value <= 1
        except ValueError:
            return False

    def update_name_from_file(self, *args):
        """Auto-fill name based on selected file"""
        file_name = self.file_var.get()
        if file_name and not self.name_entry.get():
            base_name = os.path.splitext(file_name)[0] 
            suggested_name = base_name.replace('_', ' ').replace('-', ' ').title()
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, suggested_name)

    def save(self):
        """Save dialog results"""
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


def main():
    root = tk.Tk()
    app = LoraEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
