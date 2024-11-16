import tkinter as tk
from tkinter import ttk

class LoraTreeview(ttk.Treeview):
    def __init__(self, parent, columns, **kwargs):
        super().__init__(parent, columns=columns, **kwargs)
        
        # Hide the #0 column since we'll store ID in values
        self.column("#0", width=0, stretch=False)
        
        for col in columns:
            self.heading(col, text=col.title())
            if col == "ID":
                self.column(col, width=35)
            elif col == "Weight":
                self.column(col, width=50)  # Increased from 35
            elif col == "Status":
                self.column(col, width=100)
            elif col == "Name":
                self.column(col, width=280)  # Reduced from 300
            elif col == "Trigger Words":
                self.column(col, width=300)
            elif col == "URL":
                self.column(col, width=300)  # Increased from 250
            else:
                self.column(col, width=250)
        
        # Enable sorting
        for col in columns:
            self.heading(col, command=lambda c=col: self.sort_by(c))
        
        self.sort_column = "ID"  # Default sort column
        self.sort_reverse = False  # Default sort direction

        # Enable drag and drop
        self.enable_drag_and_drop()
    
    def enable_drag_and_drop(self):
        """Set up drag and drop functionality"""
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_motion)
        self.bind("<ButtonRelease-1>", self.on_release)
        self._drag_data = {"item": None, "x": 0, "y": 0}

    def on_press(self, event):
        """Handle mouse button press"""
        # Get the item under the mouse
        item = self.identify_row(event.y)
        if item:
            self._drag_data["item"] = item
            self._drag_data["x"] = event.x
            self._drag_data["y"] = event.y

    def on_motion(self, event):
        """Handle mouse motion with button held down"""
        if self._drag_data["item"]:
            # Get the target item (where we'd drop)
            target = self.identify_row(event.y)
            if target:
                # Get the target's bbox
                bbox = self.bbox(target)
                if bbox:
                    # Determine if we're dropping above or below target
                    middle_y = bbox[1] + bbox[3] // 2
                    if event.y < middle_y:
                        self.move(self._drag_data["item"], "", self.index(target))
                    else:
                        self.move(self._drag_data["item"], "", self.index(target) + 1)

    def on_release(self, event):
        """Handle mouse button release"""
        if self._drag_data["item"]:
            # Reset the drag data
            self._drag_data = {"item": None, "x": 0, "y": 0}
            # Notify parent to sync database order
            self.event_generate("<<TreeviewReordered>>")

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
        return self.insert("", "end", text="", values=values, tags=tags or [])
