import tkinter as tk
from tkinter import ttk, messagebox
import os

class EntryDialog:
    def __init__(self, parent, title, initial=None, available_files=None):
        self.result = None
        self.available_files = available_files or []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("550x200")  # Increased width by 250px, same height
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
        main_frame = ttk.Frame(self.dialog, padding="15")  # Slightly reduced padding
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name field
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=3)  # Reduced padding
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self.name_entry = ttk.Entry(name_frame, width=40)
        self.name_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # File selection
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=3)  # Reduced padding
        ttk.Label(file_frame, text="File:").pack(side=tk.LEFT)
        self.file_var = tk.StringVar()
        self.file_combo = ttk.Combobox(file_frame, textvariable=self.file_var, width=37)
        self.file_combo['values'] = self.available_files
        self.file_combo.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        self.file_var.trace('w', self.update_name_from_file)
        
        # Weight field
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=3)  # Reduced padding
        ttk.Label(weight_frame, text="Weight:").pack(side=tk.LEFT)
        vcmd = (self.dialog.register(self.validate_weight), '%P')
        self.weight_entry = ttk.Entry(weight_frame, width=10, validate="key", validatecommand=vcmd)
        self.weight_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Trigger field
        prompt_frame = ttk.Frame(main_frame)
        prompt_frame.pack(fill=tk.X, pady=3)  # Reduced padding
        ttk.Label(prompt_frame, text="Add Trigger:").pack(side=tk.LEFT)
        self.add_prompt_entry = ttk.Entry(prompt_frame, width=40)  
        self.add_prompt_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # URL field
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=3)  # Reduced padding
        ttk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, width=40)
        self.url_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Set initial values
        if initial:
            self.name_entry.insert(0, initial["name"])
            self.file_var.set(initial["file"])
            self.weight_entry.insert(0, initial["weight"])
            prompt_value = initial.get("add_prompt", initial.get("prompt", ""))
            self.add_prompt_entry.insert(0, prompt_value)
            self.url_entry.insert(0, initial.get("url", ""))
        else:
            self.weight_entry.insert(0, "1.0")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))  # Keep slightly larger padding before buttons
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def center_dialog(self, parent):
        """Center the dialog relative to parent window"""
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 550
        dialog_height = 200
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
        """Update the name field based on the selected file"""
        file_name = self.file_var.get()
        if file_name:
            # Remove .safetensors extension and use as default name
            default_name = os.path.splitext(file_name)[0]
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, default_name)

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
                "add_prompt": self.add_prompt_entry.get(),  
                "url": self.url_entry.get()
            }
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
