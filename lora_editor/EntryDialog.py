import tkinter as tk
from tkinter import ttk, messagebox
import os

class EntryDialog:
    def __init__(self, parent, title, initial=None, available_files=None):
        self.result = None
        self.available_files = available_files or []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x450")  # Increased height for new fields
        self.dialog.resizable(False, False)
        
        self.setup_ui(initial)
        self.center_dialog(parent)
        
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
        
        # Weight frame with min/max
        weight_frame = ttk.LabelFrame(main_frame, text="Weight Range")
        weight_frame.pack(fill=tk.X, pady=5)
        
        # Min weight
        min_frame = ttk.Frame(weight_frame)
        min_frame.pack(fill=tk.X, pady=2)
        ttk.Label(min_frame, text="Min Weight:").pack(side=tk.LEFT)
        vcmd = (self.dialog.register(self.validate_weight), '%P')
        self.min_weight_entry = ttk.Entry(min_frame, width=10, validate="key", validatecommand=vcmd)
        self.min_weight_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Max weight
        max_frame = ttk.Frame(weight_frame)
        max_frame.pack(fill=tk.X, pady=2)
        ttk.Label(max_frame, text="Max Weight:").pack(side=tk.LEFT)
        self.max_weight_entry = ttk.Entry(max_frame, width=10, validate="key", validatecommand=vcmd)
        self.max_weight_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # URL field
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, width=40)
        self.url_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
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
            
            # Handle weight values
            if isinstance(initial.get("weight"), dict):
                self.min_weight_entry.insert(0, str(initial["weight"].get("min", "0.5")))
                self.max_weight_entry.insert(0, str(initial["weight"].get("max", "1.0")))
            else:
                # Legacy format support
                self.min_weight_entry.insert(0, "0.5")
                self.max_weight_entry.insert(0, str(initial.get("weight", "1.0")))
                
            self.url_entry.insert(0, initial.get("URL", ""))
            self.prompt_entry.insert(0, initial.get("prompt", ""))
        else:
            self.min_weight_entry.insert(0, "0.5")
            self.max_weight_entry.insert(0, "1.0")
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
            
            min_weight = float(self.min_weight_entry.get() or "0.5")
            max_weight = float(self.max_weight_entry.get() or "1.0")
            
            if not (0 <= min_weight <= 1 and 0 <= max_weight <= 1):
                raise ValueError("Weights must be between 0 and 1")
            if min_weight > max_weight:
                raise ValueError("Minimum weight cannot be greater than maximum weight")
                
            self.result = {
                "name": self.name_entry.get(),
                "file": self.file_var.get(),
                "weight": {
                    "min": min_weight,
                    "max": max_weight
                },
                "prompt": self.prompt_entry.get(),
                "URL": self.url_entry.get()
            }
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def update_file_list(self, file_list):
        """Update the available files in the combobox"""
        self.available_files = file_list
        self.file_combo['values'] = self.available_files