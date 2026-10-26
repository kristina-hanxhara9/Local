from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from meeting_companion.services.models import timestamp
from meeting_companion.services.meeting_session import BUSY
from .theme import text_area


class HistoryWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Meeting Companion · Local history")
        self.window.geometry("940x680")
        self.window.minsize(720, 500)
        self.window.configure(bg=app.palette["bg"])
        body = ttk.Frame(self.window, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Your meetings", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Saved on this computer. Search titles, transcripts and notes.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        search = ttk.Frame(body)
        search.pack(fill="x")
        self.query = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _: self.refresh())
        ttk.Button(search, text="Search", command=self.refresh).pack(side="left", padx=(8, 0))
        self.tree = ttk.Treeview(body, columns=("title", "date", "duration", "status"), show="headings", height=6)
        for column, label, width in (("title", "Meeting", 330), ("date", "Started", 190),
                                      ("duration", "Duration", 90), ("status", "Status", 100)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width)
        self.tree.pack(fill="x", pady=12)
        self.tree.bind("<<TreeviewSelect>>", self.open)
        self.detail = text_area(body, app.palette, height=14, state="disabled")
        self.detail.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="Export selected…", command=self.export).pack(side="left")
        ttk.Button(footer, text="Copy", command=self.copy).pack(side="left", padx=6)
        ttk.Button(footer, text="Delete…", style="Danger.TButton", command=self.delete).pack(side="right")
        self.selected = None
        self.refresh()

    def refresh(self):
        try:
            rows = self.app.session.storage.search(self.query.get())
            self.tree.delete(*self.tree.get_children())
            for identity, title, started, duration, status in rows:
                label = "Interrupted / unfinished" if status == "active" else status
                self.tree.insert("", "end", iid=identity,
                                 values=(title, started[:19].replace("T", " "), timestamp(duration), label))
        except Exception as exc:
            messagebox.showerror("History unavailable", str(exc), parent=self.window)

    def open(self, _=None):
        selection = self.tree.selection()
        if not selection:
            return
        try:
            self.selected = self.app.session.storage.load(selection[0])
            self.detail.configure(state="normal")
            self.detail.delete("1.0", "end")
            self.detail.insert("1.0", self.selected.render())
            self.detail.configure(state="disabled")
        except Exception as exc:
            messagebox.showerror("Meeting unavailable", str(exc), parent=self.window)

    def copy(self):
        if self.selected:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.selected.render())

    def export(self):
        if not self.selected:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".txt",
                                          filetypes=[("Text", "*.txt"), ("Markdown", "*.md")])
        if path:
            try:
                self.app.session.storage.export(self.selected, Path(path))
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc), parent=self.window)

    def delete(self):
        if not self.selected:
            return
        snapshot = self.app.session.snapshot()
        if snapshot and snapshot.id == self.selected.id and self.app.session.state in BUSY:
            messagebox.showinfo("Meeting active", "Stop this meeting before deleting it.", parent=self.window)
            return
        if messagebox.askyesno("Delete meeting?", "Delete this saved meeting and its notes from local history? "
                               "Exported copies are separate files.", parent=self.window):
            try:
                self.app.session.storage.delete(self.selected.id)
                self.selected = None
                self.detail.configure(state="normal")
                self.detail.delete("1.0", "end")
                self.detail.configure(state="disabled")
                self.refresh()
            except Exception as exc:
                messagebox.showerror("Delete failed", str(exc), parent=self.window)
