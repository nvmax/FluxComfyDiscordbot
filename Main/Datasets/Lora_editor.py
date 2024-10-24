import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from typing import Dict, List
import os
from pathlib import Path

class LoraEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("LoRA Config Editor")
        self.root.geometry("1200x800")
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Treeview", rowheight=25, font=('Arial', 10))
        self.style.configure("Treeview.Heading", font=('Arial', 11, 'bold'))
        self.style.configure("TButton", padding=6, font=('Arial', 10))
        self.style.configure("Title.TLabel", font=('Arial', 14, 'bold'))
        
        self.current_file = "lora.json"
        self.lora_folder = ""
        self.available_lora_files = []
        self.data = self.load_config()
        
        # Main container with padding
        container = ttk.Frame(root, padding="20")
        container.grid(row=0, column=0, sticky="nsew")
        
        # Title and folder selection
        title_frame = ttk.Frame(container)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        ttk.Label(title_frame, text="LoRA Configuration Editor", style="Title.TLabel").pack(side=tk.LEFT)
        
        folder_frame = ttk.Frame(title_frame)
        folder_frame.pack(side=tk.RIGHT)
        
        self.folder_var = tk.StringVar()
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=40)
        folder_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(folder_frame, text="Browse", command=self.select_folder).pack(side=tk.LEFT)
        
        # Search frame
        search_frame = ttk.Frame(container)
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_treeview)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT)
        
        # Treeview frame
        tree_frame = ttk.Frame(container, relief="solid", borderwidth=1)
        tree_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        
        # Configure columns
        columns = ("ID", "Name", "File", "Weight", "Prompt")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        # Configure column widths and headings
        widths = {"ID": 50, "Name": 200, "File": 300, "Weight": 100, "Prompt": 500}
        for col, width in widths.items():
            self.tree.column(col, width=width, minwidth=width)
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
        
        # Scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Button frame
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=3, column=0, pady=10)
        
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
            self.create_tooltip(btn, f"Click to {text.lower()}")
        
        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(container, textvariable=self.status_var, relief="sunken", padding=(5, 2))
        status_bar.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        
        # Configure grid weights
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        
        self.load_tree()
        self.update_status()

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select LoRA Files Folder")
        if folder:
            self.lora_folder = folder
            self.folder_var.set(folder)
            self.refresh_lora_files()

    def refresh_lora_files(self):
        if not self.lora_folder:
            messagebox.showwarning("Warning", "Please select a LoRA files folder first")
            return
            
        self.available_lora_files = []
        for file in Path(self.lora_folder).glob("*.safetensors"):
            self.available_lora_files.append(file.name)
        
        self.status_var.set(f"Found {len(self.available_lora_files)} LoRA files in folder")

    def create_tooltip(self, widget, text):
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
            label.pack()
            
            def hide_tooltip():
                tooltip.destroy()
            
            widget.tooltip = tooltip
            widget.bind('<Leave>', lambda e: hide_tooltip())
            tooltip.bind('<Leave>', lambda e: hide_tooltip())
        
        widget.bind('<Enter>', show_tooltip)

    def filter_treeview(self, *args):
        search_term = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        for lora in self.data["available_loras"]:
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
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
        items.sort()
        for index, (val, item) in enumerate(items):
            self.tree.move(item, "", index)

    def update_status(self):
        count = len(self.tree.get_children())
        self.status_var.set(f"Total entries: {count}")

    def load_config(self) -> Dict:
        try:
            with open(self.current_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"default": "", "available_loras": []}

    def save_config(self):
        try:
            with open(self.current_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            self.status_var.set("Configuration saved successfully!")
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def load_tree(self):
        self.tree.delete(*self.tree.get_children())
        for lora in self.data["available_loras"]:
            self.tree.insert("", tk.END, values=(
                lora.get("id", ""),
                lora.get("name", ""),
                lora.get("file", ""),
                lora.get("weight", ""),
                lora.get("add_prompt", "")
            ))
        self.update_status()

    def add_entry(self):
        if not self.available_lora_files:
            messagebox.showwarning("Warning", "Please select a folder with LoRA files first")
            return
            
        dialog = EntryDialog(self.root, "Add LoRA Entry", available_files=self.available_lora_files)
        if dialog.result:
            new_id = len(self.data["available_loras"]) + 1
            new_entry = {
                "id": new_id,
                "name": dialog.result["name"],
                "file": dialog.result["file"],
                "weight": float(dialog.result["weight"]),
                "add_prompt": dialog.result["prompt"]
            }
            self.data["available_loras"].append(new_entry)
            self.load_tree()
            self.status_var.set(f"Added new entry: {dialog.result['name']}")

    def edit_entry(self):
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
            self.data["available_loras"][index].update({
                "name": dialog.result["name"],
                "file": dialog.result["file"],
                "weight": float(dialog.result["weight"]),
                "add_prompt": dialog.result["prompt"]
            })
            self.load_tree()
            self.status_var.set(f"Updated entry: {dialog.result['name']}")

    def delete_entry(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an entry to delete")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this entry?"):
            item = self.tree.item(selected[0])
            index = int(item["values"][0]) - 1
            deleted_name = self.data["available_loras"][index]["name"]
            del self.data["available_loras"][index]
            
            # Update IDs
            for i, lora in enumerate(self.data["available_loras"], 1):
                lora["id"] = i
                
            self.load_tree()
            self.status_var.set(f"Deleted entry: {deleted_name}")

class EntryDialog:
    def __init__(self, parent, title, initial=None, available_files=None):
        self.result = None
        self.available_files = available_files or []
        
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("500x350")
        dialog.resizable(False, False)
        
        # Center the dialog relative to the parent window
        # Get parent window position and size
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        # Calculate dialog position
        dialog_width = 500
        dialog_height = 350
        position_x = parent_x + (parent_width - dialog_width) // 2
        position_y = parent_y + (parent_height - dialog_height) // 2
        
        # Set dialog position
        dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")
        
        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name field
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self.name_entry = ttk.Entry(name_frame, width=40)
        self.name_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # File selection (dropdown)
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="File:").pack(side=tk.LEFT)
        self.file_var = tk.StringVar()
        self.file_combo = ttk.Combobox(file_frame, textvariable=self.file_var, width=37)
        self.file_combo['values'] = self.available_files
        self.file_combo.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Weight field with validation
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=5)
        ttk.Label(weight_frame, text="Weight:").pack(side=tk.LEFT)
        vcmd = (dialog.register(self.validate_weight), '%P')
        self.weight_entry = ttk.Entry(weight_frame, width=10, validate="key", validatecommand=vcmd)
        self.weight_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Prompt field
        prompt_frame = ttk.Frame(main_frame)
        prompt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(prompt_frame, text="Add Prompt:").pack(side=tk.LEFT)
        self.prompt_entry = ttk.Entry(prompt_frame, width=40)
        self.prompt_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
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
        
        ttk.Button(btn_frame, text="Save", command=lambda: self.ok(dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Make dialog modal
        dialog.transient(parent)
        dialog.grab_set()
        
        # Force focus on dialog
        dialog.focus_force()
        
        parent.wait_window(dialog)

    def update_name_from_file(self, *args):
        """Auto-fills the name field based on the selected file name"""
        file_name = self.file_var.get()
        if file_name and not self.name_entry.get():
            # Remove file extension and replace underscores/hyphens with spaces
            base_name = os.path.splitext(file_name)[0]
            suggested_name = base_name.replace('_', ' ').replace('-', ' ').title()
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, suggested_name)

    def validate_weight(self, new_value):
        """Validates that the weight is a number between 0 and 1"""
        if new_value == "":
            return True
        try:
            value = float(new_value)
            return 0 <= value <= 1
        except ValueError:
            return False

    def ok(self, dialog):
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
            dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = LoraEditor(root)
    root.mainloop()
