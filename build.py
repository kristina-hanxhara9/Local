"""Build on Windows x64 with Python only: python build.py [--installer]."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from meeting_companion import __version__

ROOT = Path(__file__).resolve().parent


def collect_licences(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    packages = []
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        version = distribution.version
        packages.append({"name": name, "version": version,
                         "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
                         "homepage": distribution.metadata.get("Home-page")})
        for file in distribution.files or []:
            if any(word in str(file).lower() for word in ("license", "licence", "notice", "copying")):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    target = destination / name / Path(str(file))
                    # Distribution RECORD paths may include ../; keep all writes within notices.
                    if not target.resolve().is_relative_to(destination.resolve()):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    (destination / "DEPENDENCIES.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")


def run(args):
    subprocess.run([sys.executable, "-m", "PyInstaller", *args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", action="store_true", help="Also build a silent per-user installer")
    parser.add_argument("--skip-tests", action="store_true", help="Explicitly skip portable tests for a local diagnostic build")
    args = parser.parse_args()
    if platform.system() != "Windows":
        parser.exit(1, "Windows executables must be built on Windows. Cross-compiling from macOS is unsupported.\n")
    if platform.machine().lower() not in ("amd64", "x86_64"):
        parser.exit(1, "This release targets Windows x64; native ARM64 PyAudioWPatch wheels are not validated.\n")
    from meeting_companion.ai.foundry_client import FoundryClient
    FoundryClient.installed_contract()
    if not args.skip_tests:
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", "not hardware and not ui"], cwd=ROOT, check=True)
    from meeting_companion.services.system_tray import icon_image
    output = ROOT / "build" / "assets"
    output.mkdir(parents=True, exist_ok=True)
    icon = output / "meeting.ico"
    icon_image().save(icon, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    notices = output / "THIRD_PARTY_NOTICES"
    collect_licences(notices)
    options = ["--noconfirm", "--clean", "--onedir", "--windowed", "--noupx", "--name", "MeetingCompanion",
               "--icon", str(icon), "--add-data", f"{ROOT / 'docs'};docs",
               "--add-data", f"{notices};THIRD_PARTY_NOTICES",
               "--add-data", f"{ROOT / 'README.md'};.",
               "--hidden-import", "_portaudiowpatch", "--hidden-import", "pystray._win32"]
    for package in ("foundry_local_sdk", "foundry_local_core_winml", "onnxruntime_core",
                    "onnxruntime_genai_core", "pyaudiowpatch", "pystray", "PIL"):
        options.extend(["--collect-all", package])
    for distribution in ("foundry-local-sdk-winml", "foundry-local-core-winml", "onnxruntime-core",
                         "onnxruntime-genai-core", "PyAudioWPatch", "numpy", "scipy", "Pillow", "pystray"):
        options.extend(["--copy-metadata", distribution])
    run([*options, "main.py"])
    bundle = ROOT / "dist" / "MeetingCompanion"
    (bundle / "version.json").write_text(json.dumps({"version": __version__, "architecture": "x64"}), encoding="utf-8")
    shutil.copy2(ROOT / "README.md", bundle)
    shutil.copytree(ROOT / "docs", bundle / "docs", dirs_exist_ok=True)
    shutil.copytree(notices, bundle / "THIRD_PARTY_NOTICES", dirs_exist_ok=True)
    manifest = {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in bundle.rglob("*") if p.is_file()}
    (bundle / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.installer:
        run(["--noconfirm", "--clean", "--onefile", "--console", "--noupx", "--name", "MeetingCompanionInstaller",
             "--icon", str(icon), "--add-data", f"{bundle};payload", "installer.py"])
    print(f"Built {bundle}. The complete directory is required. Validate on a clean Windows laptop before distributing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
