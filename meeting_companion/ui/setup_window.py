from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from meeting_companion.config.settings import data_directory
from meeting_companion.services.diagnostics import hardware_report
from meeting_companion.services.meeting_session import BUSY
from .scrollable import ScrollableFrame


class SetupWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Welcome to Meeting Companion")
        self.window.geometry("800x760")
        self.window.minsize(750, 720)
        self.window.configure(bg=app.palette["bg"])
        self.tested = set()
        self.model_ready = False
        self.reviewed = tk.BooleanVar(value=False)
        self.scroller = ScrollableFrame(self.window, app.palette)
        self.scroller.pack(fill="both", expand=True)
        body = self.scroller.body
        ttk.Label(body, text="A little setup. All on your laptop.", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="English speech · Microsoft Foundry Local · Windows WASAPI", style="Muted.TLabel").pack(anchor="w", pady=(5, 14))
        self.report = hardware_report(data_directory())
        hardware = (f'{self.report["os"]} · {self.report["architecture"]} · {self.report["disk_free_gib"]} GiB free')
        self.labels = {}
        self.step(body, 1, "Check this computer", hardware, None)
        self.step(body, 2, "Check the speech model", "Check availability without approving a model download.", self.check)
        self.step(body, 3, "Prepare local inference", "Approve model and runtime downloads, then load the model.", self.download)
        self.step(body, 4, "Test your microphone", "Speak for four seconds. Audio stays in memory.", lambda: self.audio_test("Microphone only"))
        self.step(body, 5, "Test computer audio", "Play speech through your meeting headphones or speakers.", lambda: self.audio_test("Computer audio only"))
        self.step(body, 6, "Choose your devices", "Select the microphone and playback endpoint used by your meeting.", app.show_settings)
        self.step(body, 7, "Try live transcription", "Start a short live test, speak, review real text, then press Stop.", self.live_test)
        self.step(body, 8, "Choose reminders & startup", "Optional. Capture will always need your explicit Start.", app.show_settings)
        self.progress = ttk.Progressbar(body, maximum=100)
        self.progress.pack(fill="x", pady=(12, 4))
        self.status = ttk.Label(body, text="Windows 11 24H2+ and a compatible speech model are required.",
                                style="Muted.TLabel", wraplength=740)
        self.status.pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text="I reviewed the live test and confirmed that the recognised speech is correct.",
                        variable=self.reviewed).pack(anchor="w", pady=8)
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(6, 0))
        ttk.Button(footer, text="Cancel download", command=app.session.cancel_setup.set).pack(side="left")
        ttk.Button(footer, text="Finish setup", style="Accent.TButton", command=self.complete).pack(side="right")
        ttk.Label(body, text="Follow your employer’s recording and consent policies. Loopback captures all sounds on the selected "
                  "playback endpoint. This application is not compliance-certified.", wraplength=740,
                  style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
        if not self.report["supported_os"]:
            self.status.configure(text="This computer cannot run Windows WinML / WASAPI capture. "
                                  "Use a 64-bit Windows 11 24H2+ computer for the live tests.")

    def step(self, parent, number, title, text, command):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=f"{number:02}", foreground=self.app.palette["accent"],
                  font=("Segoe UI", 13, "bold"), width=4).pack(side="left", anchor="n")
        description = ttk.Frame(row)
        description.pack(side="left", fill="x", expand=True)
        ttk.Label(description, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        label = ttk.Label(description, text=text, style="Muted.TLabel", wraplength=540)
        label.pack(anchor="w")
        self.labels[number] = label
        if command:
            ttk.Button(row, text={2: "Check", 3: "Download", 4: "Test mic", 5: "Test audio",
                                  6: "Devices", 7: "Live test", 8: "Options"}[number],
                       command=command, width=11).pack(side="right", padx=(8, 0))

    def check(self):
        if not self.app.session.setup_task("check_model"):
            self.status.configure(text="Finish the current operation first.")

    def download(self):
        if messagebox.askyesno("Download local speech model?",
                              "Download Microsoft Foundry execution providers and the Nemotron speech model to this laptop? "
                              "This needs internet and several GB of disk space. No meeting audio is involved. "
                              "Your organisation must review the model and runtime licences before distribution.", parent=self.window):
            if self.app.session.setup_task("provision"):
                self.status.configure(text="Preparing the runtime. This can take several minutes…")

    def audio_test(self, mode):
        if messagebox.askyesno("Allow four seconds of live capture?",
                              f"Test {mode.lower()} now? No raw audio is saved. Computer audio can include other "
                              "system sounds. Follow your employer’s recording and consent policies.", parent=self.window):
            if self.app.session.setup_task("audio_test", replace(self.app.settings, mode=mode, autosave=False)):
                self.status.configure(text=f"Testing {mode.lower()} for four seconds…")

    def live_test(self):
        self.app.start(test=True)

    def event(self, kind, value):
        if kind == "model":
            self.labels[2].configure(text=f'{value["id"]} · {"downloaded" if value["cached"] else "download needed"}')
        elif kind == "provisioned":
            self.model_ready = True
            self.labels[3].configure(text="Model loaded successfully. Run a live test to check real-time performance.")
        elif kind == "tested":
            self.tested.add(value)
            self.labels[4 if value == "Microphone only" else 5].configure(
                text="Capture opened and delivered PCM. Confirm the level moves while speech is playing.")
            self.status.configure(text=f"{value} test ended. Device access alone does not prove speech recognition.")
        elif kind == "progress":
            label, percent = value
            self.progress["value"] = percent
            self.status.configure(text=f"{label} · {percent:.1f}%")
        elif kind == "error":
            self.status.configure(text=value)
        elif kind == "levels":
            self.status.configure(text="Live input levels: " + " · ".join(f"{k}: {min(100, v * 300):.0f}%" for k, v in value.items()))

    def complete(self):
        snapshot = self.app.session.snapshot()
        needed = set()
        if self.app.settings.mode != "Computer audio only":
            needed.add("Microphone only")
        if self.app.settings.mode != "Microphone only":
            needed.add("Computer audio only")
        if not (self.report["supported_os"] and needed <= self.tested and snapshot and snapshot.entries
                and self.reviewed.get() and snapshot.status == "completed" and self.app.session.state not in BUSY):
            messagebox.showinfo("Finish the live checks", "Run the audio tests for your selected sources, complete a real "
                                "live-transcription test, stop it, and confirm the recognised speech before finishing.", parent=self.window)
            return
        self.app.settings.setup_complete = True
        self.app.settings.save()
        self.window.destroy()
