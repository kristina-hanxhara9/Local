from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tray"]
    interpreter = Path(sys.executable)
    windowed = interpreter.with_name("pythonw.exe")
    return [str(windowed if windowed.exists() else interpreter),
            str(Path(__file__).resolve().parents[2] / "main.py"), "--tray"]


def set_startup(enabled: bool) -> None:
    if platform.system() != "Windows":
        if enabled:
            raise RuntimeError("Start at Windows login is available on Windows only.")
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, "MeetingCompanion", 0, winreg.REG_SZ,
                             subprocess.list2cmdline(launch_command()))
        else:
            try:
                winreg.DeleteValue(key, "MeetingCompanion")
            except FileNotFoundError:
                pass
