"""Native UI preview with clearly labelled fixtures; never opens audio or AI.

python tools/preview_ui.py --window transcript --theme dark --seconds 10
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meeting_companion.config.settings import Settings
from meeting_companion.services.models import Entry, Meeting
from meeting_companion.ui.app import Application


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=["widget", "transcript", "setup", "settings", "history"], default="widget")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--screenshot", type=Path, help="Optional screenshot of only the preview window")
    args = parser.parse_args()
    screenshot_errors = []
    with tempfile.TemporaryDirectory(prefix="meeting-ui-preview-") as directory:
        with patch.dict(os.environ, {"LOCALAPPDATA": directory}), patch(
                "meeting_companion.services.system_tray.SystemTray.start", return_value=False):
            root = tk.Tk()
            app = Application(root, Settings(theme=args.theme, setup_complete=True, always_on_top=False,
                                             storage_dir=str(Path(directory) / "history")))
            app.session.meeting = Meeting(title="Product planning · UI preview fixture", duration=865, status="completed",
                                          entries=[Entry(8, "This is a layout fixture, not recognised meeting speech."),
                                                   Entry(22, "Real meeting text will appear here after explicit live capture."),
                                                   Entry(45, "You can search the transcript, add notes, and save locally.")],
                                          notes="Preview note: confirm the playback endpoint before your meeting.")
            app.session.state = "stopped"
            window = root
            if args.window == "transcript":
                app.show_transcript()
                window = app.transcript.window
            elif args.window == "setup":
                app.show_setup()
                window = app.setup_window.window
            elif args.window == "settings":
                with patch.object(app.session, "setup_task", return_value=True):
                    app.show_settings()
                window = app.settings_window.window
            elif args.window == "history":
                app.session.storage.save(app.session.snapshot())
                app.show_history()
                window = app.history.window
            if window is not root:
                root.withdraw()
            window.geometry("+100+100")
            window.title(window.title() + " — PREVIEW ONLY")
            window.lift()
            window.update_idletasks()
            if args.screenshot:
                def capture():
                    from PIL import ImageGrab
                    x, y = window.winfo_rootx(), window.winfo_rooty()
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height())).save(args.screenshot)
                    except Exception as exc:
                        screenshot_errors.append(str(exc))
                        print("Screenshot unavailable; check desktop capture permissions and display bounds:", exc, file=sys.stderr)
                root.after(1200, capture)
            def close():
                app.session.command("shutdown")
                app.destroyed = True
                root.destroy()
            root.after(max(2, args.seconds) * 1000, close)
            root.mainloop()
            app.session.worker.join(timeout=5)
    return 1 if screenshot_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
