import tkinter as tk
from tkinter import ttk, messagebox
import os
import re

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
