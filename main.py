"""Windows GUI entry point, with a non-capturing diagnostic mode."""
from __future__ import annotations

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Meeting Companion — local live transcription")
    parser.add_argument("--tray", action="store_true", help="Start in tray; never starts capture")
    parser.add_argument("--diagnose", action="store_true", help="Print OS/package diagnostics without opening devices")
    parser.add_argument("--sdk-check", action="store_true", help="Validate installed Windows SDK API; no capture/download")
    args = parser.parse_args()
    if args.diagnose:
        from meeting_companion.services.diagnostics import hardware_report
        print(json.dumps(hardware_report("."), indent=2))
        return 0
    if args.sdk_check:
        from meeting_companion.ai.foundry_client import FoundryClient
        try:
            print(json.dumps(FoundryClient.installed_contract(), indent=2))
            return 0
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("Tkinter is required. On Windows, install Python from python.org with Tcl/Tk selected.", file=sys.stderr)
        return 1
    from meeting_companion.config.settings import Settings
    from meeting_companion.services.single_instance import SingleInstance
    from meeting_companion.ui.app import Application
    root = tk.Tk()
    instance = SingleInstance()
    try:
        if not instance.acquire():
            messagebox.showinfo("Meeting Companion is already running",
                                "Open Meeting Companion from the system tray or taskbar.", parent=root)
            root.destroy()
            return 0
        try:
            settings = Settings.load()
        except (ValueError, TypeError, OSError) as exc:
            messagebox.showwarning("Settings need attention", f"Using defaults. Your settings file was not replaced. {exc}", parent=root)
            settings = Settings()
        Application(root, settings, args.tray)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("Meeting Companion could not start", str(exc), parent=root)
        root.destroy()
        return 1
    finally:
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
