import tkinter as tk
from tkinter import ttk

class HistoryControls(ttk.Frame):
    def __init__(self, parent, on_search=None, on_show_inactive=None):
        super().__init__(parent)
        
        # Search frame
        search_frame = ttk.Frame(self)
        search_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        if on_search:
            self.search_var.trace('w', on_search)
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Show inactive checkbox
        self.show_inactive_var = tk.BooleanVar(value=False)
        if on_show_inactive:
            self.show_inactive_var.trace('w', on_show_inactive)
        
        show_inactive_check = ttk.Checkbutton(
            self, 
            text="Show Inactive", 
            variable=self.show_inactive_var
        )
        show_inactive_check.pack(side=tk.LEFT, padx=20)

class ActionButtons(ttk.Frame):
    def __init__(self, parent, commands):
        super().__init__(parent)
        
        # Create buttons
        ttk.Button(self, text="Add Entry", command=commands.get('add', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="Edit", command=commands.get('edit', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="Delete", command=commands.get('delete', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="Reset", command=commands.get('reset', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="Save", command=commands.get('save', None)).pack(side=tk.LEFT, padx=2)

class NavigationButtons(ttk.Frame):
    def __init__(self, parent, commands):
        super().__init__(parent)
        
        # Create buttons
        ttk.Button(self, text="↑↑↑↑↑", command=commands.get('up_five', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="↑", command=commands.get('up', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="↓", command=commands.get('down', None)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="↓↓↓↓↓", command=commands.get('down_five', None)).pack(side=tk.LEFT, padx=2)

class StatusBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Status label
        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self,
            variable=self.progress_var,
            maximum=100,
            length=200
        )
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        self.progress_bar.pack_forget()  # Hidden by default
    
    def set_status(self, text):
        """Update status text"""
        self.status_label.config(text=text)
    
    def show_progress(self, show=True):
        """Show or hide progress bar"""
        if show:
            self.progress_bar.pack(side=tk.LEFT, padx=5)
        else:
            self.progress_bar.pack_forget()
    
    def set_progress(self, value):
        """Update progress bar value"""
        self.progress_var.set(value)
