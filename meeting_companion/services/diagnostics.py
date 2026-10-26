from __future__ import annotations

import importlib.metadata
import platform
import shutil
import struct
import sys


def hardware_report(directory) -> dict:
    windows = platform.system() == "Windows"
    build = sys.getwindowsversion().build if windows else None
    architecture = platform.machine()
    report = {"os": platform.platform(), "architecture": architecture,
              "python": platform.python_version(), "windows_build": build,
              "disk_free_gib": round(shutil.disk_usage(directory).free / 1024 ** 3, 1),
              "supported_os": windows and build >= 26100 and struct.calcsize("P") == 8,
              "notice": "Model compatibility and real-time speed must be checked by loading and testing the model."}
    if windows:
        import ctypes
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ("physical", "available", "page", "page_available",
                                                       "virtual", "virtual_available", "extended")]
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            report["ram_gib"] = round(memory.physical / 1024 ** 3, 1)
    for package in ("foundry-local-sdk-winml", "PyAudioWPatch", "numpy", "scipy", "Pillow", "pystray"):
        try:
            report[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report[package] = "not installed"
    return report
