from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from meeting_companion.config.settings import MODES
from .scrollable import ScrollableFrame


class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Meeting Companion · Settings")
        self.window.geometry("650x720")
        self.window.resizable(True, True)
        self.window.configure(bg=app.palette["bg"])
        self.devices = ([], [])
        self.mode = tk.StringVar(value=app.settings.mode)
        self.microphone = tk.StringVar(value=app.settings.microphone or "Windows default")
        self.loopback = tk.StringVar(value=app.settings.loopback or "Windows default")
        self.theme = tk.StringVar(value=app.settings.theme)
        self.directory = tk.StringVar(value=str(app.settings.directory))
        self.interval = tk.IntVar(value=app.settings.reminder_minutes)
        self.cooldown = tk.IntVar(value=app.settings.cooldown_minutes)
        self.flags = {name: tk.BooleanVar(value=getattr(app.settings, name)) for name in
                      ("always_on_top", "autosave", "reminders", "startup", "echo_reduction")}
        self.scroller = ScrollableFrame(self.window, app.palette)
        self.scroller.pack(fill="both", expand=True)
        body = self.scroller.body
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Make it yours", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))
        self._row(body, 1, "Audio source", ttk.Combobox(body, values=MODES, textvariable=self.mode, state="readonly"))
        self.mic_combo = ttk.Combobox(body, textvariable=self.microphone, state="readonly", values=["Windows default"])
        self.loop_combo = ttk.Combobox(body, textvariable=self.loopback, state="readonly", values=["Windows default"])
        self._row(body, 2, "Microphone", self.mic_combo)
        self._row(body, 3, "Playback loopback", self.loop_combo)
        ttk.Button(body, text="Refresh devices", command=self.refresh_devices).grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(body, text="Choose the playback endpoint used by Teams / Zoom.\nBluetooth profile changes may require selecting it again.",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 12))
        self._row(body, 6, "Appearance", ttk.Combobox(body, textvariable=self.theme, values=["light", "dark"], state="readonly"))
        self._row(body, 7, "History folder", ttk.Entry(body, textvariable=self.directory))
        ttk.Button(body, text="Choose…", command=self.choose).grid(row=7, column=2, padx=(6, 0))
        ttk.Label(body, text="Changing folders opens a separate history; existing files stay in the old folder.",
                  style="Muted.TLabel", wraplength=560).grid(row=8, column=0, columnspan=3, sticky="w", pady=6)
        for row, (name, label) in enumerate((
            ("always_on_top", "Keep the floating widget on top"),
            ("autosave", "Autosave transcripts and notes every five seconds"),
            ("echo_reduction", "Reduce strongly correlated microphone playback bleed"),
            ("startup", "Start in the tray when I sign in to Windows"),
            ("reminders", "Remind me to start local transcription")), start=9):
            ttk.Checkbutton(body, text=label, variable=self.flags[name]).grid(row=row, column=0, columnspan=3, sticky="w", pady=5)
        self._row(body, 14, "Reminder minutes", ttk.Spinbox(body, from_=5, to=1440, textvariable=self.interval))
        self._row(body, 15, "Cooldown minutes", ttk.Spinbox(body, from_=5, to=1440, textvariable=self.cooldown))
        ttk.Button(body, text="Audio & model setup…", command=app.show_setup).grid(row=16, column=0, columnspan=2, sticky="w", pady=(16, 8))
        ttk.Button(body, text="Save settings", style="Accent.TButton", command=self.save).grid(row=16, column=2, pady=(16, 8))
        ttk.Label(body, text="No audio or transcripts are sent to cloud inference.\nLocal SQLite files and exports are not encrypted by this app.",
                  style="Muted.TLabel").grid(row=17, column=0, columnspan=3, sticky="w", pady=6)
        if app.session.state not in {"recording", "paused", "starting", "setup", "checking"}:
            self.refresh_devices()

    @staticmethod
    def _row(body, row, label, control):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=6)
        control.grid(row=row, column=1, sticky="ew", pady=6)

    def refresh_devices(self):
        if not self.app.session.setup_task("devices"):
            messagebox.showinfo("Devices busy", "Stop transcription and finish setup before refreshing devices.", parent=self.window)

    def set_devices(self, devices):
        self.devices = devices
        for combo, pool in zip((self.mic_combo, self.loop_combo), devices):
            combo.configure(values=["Windows default"] + [d.key for d in pool])

    def choose(self):
        path = filedialog.askdirectory(parent=self.window, initialdir=self.directory.get(), mustexist=False)
        if path:
            self.directory.set(path)

    def save(self):
        try:
            settings = replace(self.app.settings, mode=self.mode.get(),
                               microphone="" if self.microphone.get() == "Windows default" else self.microphone.get(),
                               loopback="" if self.loopback.get() == "Windows default" else self.loopback.get(),
                               theme=self.theme.get(), storage_dir=self.directory.get(),
                               reminder_minutes=self.interval.get(), cooldown_minutes=self.cooldown.get(),
                               **{name: value.get() for name, value in self.flags.items()})
            settings.validate()
            self.app.apply_settings(settings)
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Settings not saved", str(exc), parent=self.window)
