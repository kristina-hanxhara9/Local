"""Python-only silent per-user installer, packaged separately with PyInstaller.

MeetingCompanionInstaller.exe --install
MeetingCompanionInstaller.exe --uninstall
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from meeting_companion.services.single_instance import SingleInstance
from meeting_companion.services.startup import set_startup

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MeetingCompanion"
APP_PATH_KEY = r"Software\Microsoft\Windows\CurrentVersion\App Paths\MeetingCompanion.exe"


def create_shortcut(target: Path, shortcut: Path):
    """IShellLinkW / IPersistFile through ctypes; no script host or .NET."""
    from ctypes import wintypes
    ole = ctypes.OleDLL("ole32")
    ole.CoInitialize(None)
    pointer = ctypes.c_void_p()
    persist = ctypes.c_void_p()

    def guid(value):
        return (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(value).bytes_le)

    def call(obj, index, argtypes, *values):
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(table[index])
        result = fn(obj, *values)
        if result < 0:
            raise OSError(f"Windows shortcut operation failed: 0x{result & 0xffffffff:08x}")

    try:
        clsid = guid("00021401-0000-0000-C000-000000000046")
        iid = guid("000214F9-0000-0000-C000-000000000046")
        ole.CoCreateInstance.argtypes = (ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)
        ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(pointer))
        call(pointer, 20, (wintypes.LPCWSTR,), str(target))
        call(pointer, 9, (wintypes.LPCWSTR,), str(target.parent))
        call(pointer, 7, (wintypes.LPCWSTR,), "Meeting Companion — local meeting transcription")
        ipersist = guid("0000010b-0000-0000-C000-000000000046")
        call(pointer, 0, (ctypes.c_void_p, ctypes.c_void_p), ctypes.byref(ipersist), ctypes.byref(persist))
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        call(persist, 6, (wintypes.LPCWSTR, wintypes.BOOL), str(shortcut), True)
    finally:
        for obj in (persist, pointer):
            if obj.value:
                table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(obj)
        ole.CoUninitialize()


def verify_payload(payload: Path):
    manifest = json.loads((payload / "SHA256SUMS.json").read_text(encoding="utf-8"))
    import hashlib
    for relative, expected in manifest.items():
        path = payload / relative
        if not path.resolve().is_relative_to(payload.resolve()) or not path.is_file():
            raise ValueError("Invalid installer payload path.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Installer payload checksum mismatch: {relative}")
    if not (payload / "MeetingCompanion.exe").is_file():
        raise ValueError("Installer payload is missing MeetingCompanion.exe.")


def install(payload: Path, target: Path, user_data: Path, shortcut: Path):
    import winreg
    verify_payload(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="MeetingCompanion-stage-", dir=target.parent))
    backup = target.with_name("MeetingCompanion.previous")
    try:
        shutil.copytree(payload, staging, dirs_exist_ok=True)
        if backup.exists():
            if not (backup / "version.json").is_file():
                raise RuntimeError("Unrecognised backup directory; refusing to remove it.")
            shutil.rmtree(backup)
        if target.exists():
            if not (target / "version.json").is_file():
                raise RuntimeError("Unrecognised application directory; refusing to replace it.")
            target.rename(backup)
        staging.rename(target)
        user_data.mkdir(parents=True, exist_ok=True)
        uninstaller = user_data / "Uninstall.exe"
        if getattr(sys, "frozen", False):
            if Path(sys.executable).resolve() != uninstaller.resolve():
                shutil.copy2(sys.executable, uninstaller)
            uninstall_command = subprocess.list2cmdline([str(uninstaller), "--uninstall"])
        else:
            uninstall_command = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()), "--uninstall"])
        create_shortcut(target / "MeetingCompanion.exe", shortcut)
        version = json.loads((target / "version.json").read_text(encoding="utf-8"))["version"]
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            for name, value in {"DisplayName": "Meeting Companion", "DisplayVersion": version,
                                "Publisher": "Meeting Companion", "InstallLocation": str(target),
                                "UninstallString": uninstall_command, "QuietUninstallString": uninstall_command,
                                "DisplayIcon": str(target / "MeetingCompanion.exe")}.items():
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            for name in ("NoModify", "NoRepair"):
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_PATH_KEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(target / "MeetingCompanion.exe"))
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if backup.exists():
            if target.exists():
                shutil.rmtree(target)
            backup.rename(target)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def uninstall(target: Path, shortcut: Path):
    import winreg
    set_startup(False)
    if target.exists():
        if not (target / "version.json").is_file():
            raise RuntimeError("Unrecognised application directory; refusing to delete it.")
        shutil.rmtree(target)
    shortcut.unlink(missing_ok=True)
    for path in (UNINSTALL_KEY, APP_PATH_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass
    # Transcripts, notes, models, settings and this uninstaller remain in user_data.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--install", action="store_true")
    actions.add_argument("--uninstall", action="store_true")
    parser.add_argument("--payload", type=Path, help="Development only: built application directory")
    args = parser.parse_args()
    if platform.system() != "Windows":
        parser.exit(1, "This installer requires Windows.\n")
    local = Path(os.environ["LOCALAPPDATA"])
    target = local / "Programs" / "MeetingCompanion"
    user_data = local / "MeetingCompanion"
    shortcut = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Meeting Companion.lnk"
    instance = SingleInstance()
    try:
        if not instance.acquire():
            print("Meeting Companion is running. Quit it from the system tray before installation/removal.")
            return 1618
        if args.install:
            if sys.getwindowsversion().build < 26100:
                raise RuntimeError("Windows 11 24H2 (26100) or later is required.")
            payload = args.payload or Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "payload"
            install(payload, target, user_data, shortcut)
        else:
            uninstall(target, shortcut)
        print("Installation complete." if args.install else "Application removed. Local user data was retained.")
        return 0
    except Exception as exc:
        print(f"Installer failed: {exc}", file=sys.stderr)
        return 1
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
