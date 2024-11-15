import tkinter as tk
from tkinter import ttk

class LoraTreeview(ttk.Treeview):
    def __init__(self, parent, columns, **kwargs):
        super().__init__(parent, columns=columns, **kwargs)
        
        # Configure columns
        self.heading("#0", text="ID")
        self.column("#0", width=50)
        
        for col in columns:
            self.heading(col, text=col.title())
            if col in ["Weight", "Status"]:
                self.column(col, width=100)
            else:
                self.column(col, width=200)
        
        # Enable sorting
        for col in ["#0"] + list(columns):
            self.heading(col, command=lambda c=col: self.sort_by(c))
        
        self.sort_column = "#0"  # Default sort column
        self.sort_reverse = False  # Default sort direction
    
    def sort_by(self, col):
        """Sort tree contents when a column header is clicked"""
        # Get items as a list
        items = [(self.set(k, col), k) for k in self.get_children("")]
        
        # If the column clicked is already the sort column, reverse the sort order
        if col == self.sort_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
            self.sort_column = col
        
        # Sort the list
        items.sort(reverse=self.sort_reverse)
        
        # Rearrange items in sorted positions
        for index, (_, item) in enumerate(items):
            self.move(item, "", index)
    
    def insert_entry(self, values, tags=None):
        """Insert a new entry into the treeview"""
        return self.insert("", "end", text=str(values[0]), values=values[1:], tags=tags or [])
