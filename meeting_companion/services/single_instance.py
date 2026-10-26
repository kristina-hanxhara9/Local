"""Per-user Windows mutex; prevents two app processes opening capture together."""
import ctypes
import getpass
import hashlib
import platform


class SingleInstance:
    def __init__(self):
        self.handle = None

    def acquire(self) -> bool:
        if platform.system() != "Windows":
            return True
        from ctypes import wintypes
        name = "Local\\MeetingCompanion-" + hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        self.handle = kernel.CreateMutexW(None, False, name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS

    def close(self):
        if self.handle:
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle(self.handle)
            self.handle = None
