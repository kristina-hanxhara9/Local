"""Native in-process SDK only. No REST service or alternate runtime.

Contract checked against Microsoft's foundry-local-sdk-winml 1.2.4 wheel.
See docs/SDK_VERIFICATION.md for inspected methods and Windows validation.
"""
from __future__ import annotations

import importlib.metadata
import platform
import struct
import sys
import threading
from pathlib import Path

from meeting_companion.config.settings import MODEL_ALIAS


class ProvisioningRequired(RuntimeError):
    pass


class FoundryClient:
    _init_lock = threading.Lock()
    _manager = None

    def __init__(self, directory: Path):
        self.directory = directory
        self.model = None

    @staticmethod
    def installed_contract() -> dict:
        if platform.system() != "Windows":
            raise RuntimeError("Foundry WinML transcription requires Windows 11 24H2 or later.")
        if (sys.getwindowsversion().build < 26100 or struct.calcsize("P") != 8
                or platform.machine().lower() not in ("amd64", "x86_64")):
            raise RuntimeError("This release requires x64 Windows 11 24H2 (build 26100+) and 64-bit Python.")
        try:
            version = importlib.metadata.version("foundry-local-sdk-winml")
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError("Install requirements.txt in a Windows Python environment.") from exc
        try:
            importlib.metadata.version("foundry-local-sdk")
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise RuntimeError("Conflicting SDKs: remove foundry-local-sdk and reinstall the WinML SDK.")
        if version != "1.2.4":
            raise RuntimeError(f"SDK {version} is not the validated contract. Install foundry-local-sdk-winml==1.2.4.")
        from foundry_local_sdk import Configuration, FoundryLocalManager
        from foundry_local_sdk.openai.audio_client import AudioClient
        from foundry_local_sdk.openai.live_audio_session import LiveAudioTranscriptionSession
        required = {FoundryLocalManager: ("initialize", "download_and_register_eps"),
                    AudioClient: ("create_live_transcription_session",),
                    LiveAudioTranscriptionSession: ("start", "append", "get_stream", "stop")}
        for cls, names in required.items():
            for name in names:
                if not callable(getattr(cls, name, None)):
                    raise RuntimeError(f"Installed SDK lacks {cls.__name__}.{name}; reinstall requirements.txt.")
        return {"sdk": version, "model": MODEL_ALIAS, "format": "16000 Hz / mono / PCM16 LE"}

    def initialize(self):
        self.installed_contract()
        from foundry_local_sdk import Configuration, FoundryLocalManager
        from foundry_local_sdk.logging_helper import LogLevel
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._init_lock:
            if FoundryClient._manager is None:
                config = Configuration(app_name="MeetingCompanion", app_data_dir=str(self.directory),
                                       model_cache_dir=str(self.directory / "Models"),
                                       logs_dir=str(self.directory / "RuntimeLogs"), log_level=LogLevel.ERROR)
                FoundryLocalManager.initialize(config)
                FoundryClient._manager = FoundryLocalManager.instance
        return FoundryClient._manager

    def check(self) -> dict:
        manager = self.initialize()
        candidate = manager.catalog.get_model(MODEL_ALIAS)
        if candidate is None:
            raise RuntimeError(f"{MODEL_ALIAS} is unavailable for this hardware/runtime. "
                               "Update Windows and drivers, provision execution providers, then retry. "
                               "There is no cloud fallback.")
        if self.model is not None and self.model.id != candidate.id and self.model.is_loaded:
            self.model.unload()
        self.model = candidate
        return {"id": self.model.id, "cached": self.model.is_cached}

    def provision(self, progress, cancel: threading.Event) -> None:
        manager = self.initialize()
        progress("Preparing local execution providers", 0)
        result = manager.download_and_register_eps(
            progress_callback=lambda name, percent: progress(f"Runtime: {name}", percent),
            cancel_event=cancel)
        if cancel.is_set():
            raise RuntimeError("Setup cancelled.")
        if not result.success:
            raise RuntimeError("Execution provider installation failed. Check Windows, GPU drivers and SDK logs.")
        self.check()
        self.model.download(lambda percent: progress("Downloading speech model", percent), cancel_event=cancel)
        if cancel.is_set():
            raise RuntimeError("Setup cancelled.")
        self.load()
        progress("Speech model loaded locally", 100)

    def load(self) -> None:
        if self.model is None:
            self.check()
        if not self.model.is_cached:
            raise ProvisioningRequired("The speech model needs downloading. Open Setup and approve the download.")
        try:
            if not self.model.is_loaded:
                self.model.load()
        except Exception as exc:
            raise RuntimeError("The local speech model could not load. Check compatible execution providers, "
                               f"available RAM/VRAM, Windows and GPU drivers. SDK: {exc}") from exc

    def create_session(self):
        self.load()
        session = self.model.get_audio_client().create_live_transcription_session()
        for name in ("start", "append", "get_stream", "stop"):
            if not callable(getattr(session, name, None)):
                raise RuntimeError(f"Installed SDK session is missing {name}().")
        session.settings.sample_rate = 16000
        session.settings.channels = 1
        session.settings.bits_per_sample = 16
        session.settings.language = "en"
        session.settings.push_queue_capacity = 50
        return session

    def unload(self) -> None:
        if self.model is not None and self.model.is_loaded:
            self.model.unload()
