import tkinter as tk
from tkinter import ttk

from meeting_companion.services.models import timestamp


class Widget:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.root.title("Meeting Companion")
        self.root.geometry("370x300+80+80")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", app.settings.always_on_top)
        self.root.protocol("WM_DELETE_WINDOW", app.hide)
        body = ttk.Frame(self.root, padding=20)
        body.pack(fill="both", expand=True)
        top = ttk.Frame(body)
        top.pack(fill="x")
        brand = ttk.Label(top, text="◖  Meeting Companion", font=("Segoe UI", 13, "bold"))
        brand.pack(side="left")
        ttk.Button(top, text="—", width=3, command=app.hide).pack(side="right")
        self.drag_position = None
        brand.bind("<ButtonPress-1>", self._drag_start)
        brand.bind("<B1-Motion>", self._drag_move)
        self.status = ttk.Label(body, text="READY TO TRANSCRIBE", style="Muted.TLabel")
        self.status.pack(anchor="w", pady=(22, 0))
        self.timer = ttk.Label(body, text="Your meeting, on your laptop.", font=("Segoe UI", 13))
        self.timer.pack(anchor="w", pady=(4, 14))
        controls = ttk.Frame(body)
        controls.pack(fill="x")
        self.start = ttk.Button(controls, text="Start Meeting", style="Accent.TButton", command=app.start)
        self.start.pack(side="left", fill="x", expand=True)
        self.pause = ttk.Button(controls, text="Pause", command=app.pause)
        self.stop = ttk.Button(controls, text="Stop", style="Danger.TButton", command=app.stop)
        ttk.Button(body, text="View Transcript", command=app.show_transcript).pack(fill="x", pady=(8, 8))
        bottom = ttk.Frame(body)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="History", command=app.show_history).pack(side="left")
        ttk.Button(bottom, text="Settings", command=app.show_settings).pack(side="left", padx=8)
        ttk.Button(bottom, text="Quit…", command=app.quit).pack(side="right")
        self.hint = ttk.Label(body, text="Local inference · No raw audio saved", style="Muted.TLabel")
        self.hint.pack(pady=(10, 0))

    def _drag_start(self, event):
        self.drag_position = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        if self.drag_position:
            x, y = self.drag_position
            self.root.geometry(f"+{event.x_root - x}+{event.y_root - y}")

    def update(self, state, elapsed):
        active = state in {"recording", "paused", "pausing", "resuming", "stopping"}
        self.status.configure(text={"idle": "READY TO TRANSCRIBE", "recording": "● LIVE TRANSCRIPTION",
                                    "paused": "Ⅱ PAUSED · AUDIO RELEASED", "stopped": "MEETING COMPLETE",
                                    "testing": "● AUDIO TEST · CAPTURING",
                                    "error": "CAPTURE STOPPED · CHECK MESSAGE"}.get(state, state.upper() + "…"))
        self.timer.configure(text=timestamp(elapsed) if active or state == "stopped" else "Your meeting, on your laptop.",
                             font=("Segoe UI", 27 if active else 13, "bold" if active else "normal"))
        busy = state in {"starting", "setup", "checking", "testing"}
        if active:
            self.start.pack_forget()
            if not self.pause.winfo_manager():
                self.pause.pack(side="left", fill="x", expand=True, padx=(0, 5))
                self.stop.pack(side="left", fill="x", expand=True)
            self.pause.configure(text="Resume" if state == "paused" else "Pause",
                                 state="normal" if state in {"paused", "recording"} else "disabled")
            self.stop.configure(state="normal" if state in {"paused", "recording"} else "disabled")
        else:
            self.pause.pack_forget()
            self.stop.pack_forget()
            if not self.start.winfo_manager():
                self.start.pack(side="left", fill="x", expand=True)
            self.start.configure(state="disabled" if busy else "normal")
