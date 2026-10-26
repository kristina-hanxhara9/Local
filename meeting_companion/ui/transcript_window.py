from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from meeting_companion.config.settings import MODES
from meeting_companion.services.models import timestamp
from .theme import text_area


class TranscriptWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Meeting Companion · Transcript")
        self.window.geometry("920x760")
        self.window.minsize(720, 580)
        self.window.configure(bg=app.palette["bg"])
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        self.meeting_id = None
        self.displayed = 0
        self.last_partial = ""
        self.history_view = False
        self.title = tk.StringVar(value="Untitled meeting")
        self.auto_scroll = tk.BooleanVar(value=True)
        self.query = tk.StringVar()
        self.mode = tk.StringVar(value=app.settings.mode)
        body = ttk.Frame(self.window, padding=24)
        body.pack(fill="both", expand=True)
        header = ttk.Frame(body)
        header.pack(fill="x")
        ttk.Label(header, text="Meeting transcript", style="Title.TLabel").pack(side="left")
        self.status = ttk.Label(header, text="Ready", style="Muted.TLabel")
        self.status.pack(side="right")
        self.title_entry = ttk.Entry(body, textvariable=self.title, font=("Segoe UI", 15, "bold"))
        self.title_entry.pack(fill="x", pady=(18, 4))
        self.meta = ttk.Label(body, text="Start a meeting to see live speech here.", style="Muted.TLabel")
        self.meta.pack(anchor="w", pady=(0, 12))
        controls = ttk.Frame(body)
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="Start Meeting", style="Accent.TButton", command=app.start)
        self.start_button.pack(side="left")
        self.pause_button = ttk.Button(controls, text="Pause", command=app.pause)
        self.pause_button.pack(side="left", padx=6)
        self.stop_button = ttk.Button(controls, text="Stop", style="Danger.TButton", command=app.stop)
        self.stop_button.pack(side="left")
        self.mode_combo = ttk.Combobox(controls, textvariable=self.mode, values=MODES, state="readonly", width=22)
        self.mode_combo.pack(side="right")
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _: app.select_mode(self.mode.get()))
        self.levels = ttk.Label(body, text="Audio devices open only after Start.", style="Muted.TLabel")
        self.levels.pack(anchor="w", pady=(6, 0))
        search = ttk.Frame(body)
        search.pack(fill="x", pady=(16, 8))
        ttk.Label(search, text="Find").pack(side="left", padx=(0, 8))
        ttk.Entry(search, textvariable=self.query, width=26).pack(side="left")
        self.matches = ttk.Label(search, text="", style="Muted.TLabel")
        self.matches.pack(side="left", padx=8)
        ttk.Checkbutton(search, text="Auto-scroll", variable=self.auto_scroll).pack(side="right")
        self.query.trace_add("write", lambda *_: self.search())
        text_frame = ttk.Frame(body)
        text_frame.pack(fill="both", expand=True)
        self.text = text_area(text_frame, app.palette, height=13, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(text_frame, command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure("stamp", foreground=app.palette["muted"], font=("Segoe UI", 9))
        self.text.tag_configure("partial", foreground=app.palette["muted"], font=("Segoe UI", 11, "italic"))
        self.text.tag_configure("match", background="#F1D98A", foreground="#192E2B")
        self.text.mark_set("interim", "1.0")
        self.text.mark_gravity("interim", "left")
        ttk.Label(body, text="Your notes", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.notes = text_area(body, app.palette, height=4)
        self.notes.pack(fill="x")
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="Copy", command=app.copy_transcript).pack(side="left")
        ttk.Button(footer, text="Save to History", command=app.save).pack(side="left", padx=6)
        ttk.Button(footer, text="Export…", command=app.export).pack(side="left")
        ttk.Label(footer, text="Processed locally with Foundry Local", style="Muted.TLabel").pack(side="right")

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def metadata(self):
        return self.title.get(), self.notes.get("1.0", "end-1c")

    def update(self):
        meeting_id, entries, partial, state, elapsed = self.app.session.changes(self.displayed)
        if meeting_id != self.meeting_id:
            self.meeting_id = meeting_id
            self.displayed = 0
            self.last_partial = ""
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.mark_set("interim", "1.0")
            self.text.configure(state="disabled")
            snapshot = self.app.session.snapshot()
            if snapshot:
                self.title.set(snapshot.title)
                self.notes.delete("1.0", "end")
                self.notes.insert("1.0", snapshot.notes)
                self.mode.set(snapshot.mode)
                self.meta.configure(text=f"{snapshot.started[:10]}  ·  Started {snapshot.started[11:19]}  ·  {snapshot.mode}")
            _, entries, partial, state, elapsed = self.app.session.changes(0)
        if entries or partial != self.last_partial:
            self.text.configure(state="normal")
            self.text.delete("interim", "end-1c")
            for entry in entries:
                self.text.insert("end", f"{timestamp(entry.offset)}  ", "stamp")
                self.text.insert("end", entry.text + "\n\n")
            self.text.mark_set("interim", "end-1c")
            if partial:
                self.text.insert("end", partial, "partial")
            self.text.configure(state="disabled")
            self.displayed += len(entries)
            self.last_partial = partial
            if self.auto_scroll.get():
                self.text.see("end")
            if self.query.get():
                self.search()
        self.status.configure(text=f"{'● LIVE' if state == 'recording' else state.upper()}  ·  {timestamp(elapsed)}")
        active = state in {"recording", "paused"}
        busy = state in {"starting", "recording", "paused", "pausing", "resuming", "stopping", "setup", "checking"}
        self.start_button.configure(state="disabled" if busy else "normal")
        self.pause_button.configure(text="Resume" if state == "paused" else "Pause", state="normal" if active else "disabled")
        self.stop_button.configure(state="normal" if active else "disabled")
        self.mode_combo.configure(state="disabled" if busy else "readonly")

    def search(self):
        self.text.tag_remove("match", "1.0", "end")
        query = self.query.get()
        count = 0
        if query:
            position = "1.0"
            while count < 1000:
                position = self.text.search(query, position, stopindex="end", nocase=True)
                if not position:
                    break
                end = f"{position}+{len(query)}c"
                self.text.tag_add("match", position, end)
                if count == 0:
                    self.text.see(position)
                position = end
                count += 1
        self.matches.configure(text=f"{count}{'+' if count == 1000 else ''} matches" if query else "")
