import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """Native Tk scrolling for setup/settings on small laptop screens and high DPI."""

    def __init__(self, parent, palette):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=palette["bg"], height=400)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = ttk.Frame(self.canvas, padding=24)
        item = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(item, width=event.width))

        def wheel(event):
            if event.delta:
                delta = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
                self.canvas.yview_scroll(delta, "units")

        # Bind at the containing toplevel, so child controls receive wheel events too.
        parent.bind("<MouseWheel>", wheel, add=True)
