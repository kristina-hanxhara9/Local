# Windows packaging and redistribution

The build scripts are Python. There is no JavaScript build tool, .NET project, alternate model runtime or cloud inference dependency. PyInstaller packages Python and its native library dependencies; it cannot cross-build a working Windows executable from this macOS environment.

## Reproducible Windows build procedure

1. Use a clean Windows 11 24H2+ x64 VM or laptop and 64-bit Python 3.12 with Tcl/Tk selected. Keep the build environment separate from unrelated AI packages.
2. Create `.venv` and install `requirements-dev.txt` as in the README. Run `python -m pip check`. Only the WinML SDK variant may be installed.
3. Run `python main.py --sdk-check`, the normal pytest suite, and the opt-in native UI checks in an interactive session. Then reproduce the real microphone sample and run the Windows hardware procedure.
4. Run `python build.py --installer`. The build script refuses non-Windows and non-x64 hosts, checks the installed SDK contract, and runs the portable tests unless `--skip-tests` was explicitly requested. A skipped test build is a diagnostic build, not a release.
5. Retain `pip freeze --all` output with the release record and archive the exact wheels used. The SDK/audio pins are fixed, but other compatible library versions are ranges; the complete environment must be locked for each enterprise release.
6. Collect outputs:
   - `dist\MeetingCompanion\MeetingCompanion.exe` **and the full sibling directory tree**.
   - `dist\MeetingCompanionInstaller.exe` if requested.
   - `version.json`, `SHA256SUMS.json`, and `THIRD_PARTY_NOTICES` in the application bundle.
7. Sign the application and installer with your organisation's code-signing process. If you sign binaries after the bundle checksums are generated, regenerate `SHA256SUMS.json` before building the installer, because signatures change file bytes. One practical sequence is build app, sign app/native files as policy requires, regenerate manifest, then invoke PyInstaller for the installer with that signed bundle. Signing is external to this project's source and no signing keys are requested.
8. Test the signed installer/executable on a clean compatible Windows laptop with **no Python, Node.js or .NET SDK installed**. Model provisioning still requires internet and explicit consent. Repeat with networking disconnected after provisioning. Do not distribute until those results have been recorded.

The native SDK package dependencies inspected for 1.2.4 are `foundry-local-core-winml==1.2.4`, `onnxruntime-core==1.26.0` and `onnxruntime-genai-core==0.14.1`, alongside the SDK's Python dependencies. `--collect-all` includes their binary/data package trees because Foundry locates native libraries relative to the import package. Distribution metadata is copied for runtime version checks. Tk/Tcl is collected by PyInstaller's built-in hook. `pyaudiowpatch` and `_portaudiowpatch` are explicitly included, and the Windows pystray backend is included.

**This collection strategy has not been run on Windows.** Inspect PyInstaller warnings, verify the bundled native DLLs actually resolve, and adjust collection hooks against the installed wheel layout if needed. Do not claim a clean-machine executable simply because PyInstaller exits successfully.

## Runtime and models

The SDK uses Windows ML and may provision hardware-specific execution providers. Setup asks for download permission before calling `download_and_register_eps()` and `model.download()`. Windows components, vendor GPU/NPU drivers, native Microsoft runtime redistributables and any execution-provider prerequisites must be installed on the target image as required by Microsoft's actual package/runtime errors. This repository does not guess that a particular VC++ or Windows App Runtime installer is universally required or universally unnecessary.

The application never starts the optional SDK web server. It does not require the Foundry CLI. Ordinary Start only loads a cached model, creates a native live session and opens devices. It does not call a model download as a hidden fallback. If provisioned execution providers do not register/persist correctly across a restart on a target device, reopen Setup online and resolve that device's runtime provisioning before accepting the offline test.

The model is **not embedded** in the executable or installer. Its availability, hardware variants, download size, licence and cache contents are controlled by the Microsoft model catalog. Each employee provisions locally. Do not bulk-copy model caches between machines without verifying model licensing and hardware compatibility.

## Installer behaviour

```text
MeetingCompanionInstaller.exe --install
MeetingCompanionInstaller.exe --uninstall
```

No arguments produce usage, not a hidden install. Both commands are silent and need no administrator rights when run for the intended employee. Installation verifies payload checksums, stages the full app directory, preserves a recognised previous install for rollback during replacement, creates a native Start Menu shortcut through `IShellLinkW`, and registers uninstall information in HKCU. It copies an uninstaller to `%LOCALAPPDATA%\MeetingCompanion\Uninstall.exe`. The app is not launched by the installer.

Exit codes: `0` success, `1` failure, `1618` app already running (close it and retry). Installer and app share a per-user session mutex; the installer does not forcibly stop a meeting. It intentionally refuses to delete/replace unrecognised application or backup directories. Registration/shortcut operations and rollback still require Windows validation, including upgrades and failure injection.

Removal disables the user startup entry, deletes the recognised application directory and shortcut, and removes HKCU app/uninstall registration. Transcripts, settings, models and the uninstaller remain in `%LOCALAPPDATA%\MeetingCompanion`; deletion of employee data is a separate deliberate action. Installer success does not mean a model has been downloaded or audio capture has been approved.

## Licence review

The official SDK wheel inspected here includes an **MIT licence for its Python SDK code**. PyAudioWPatch's wheel includes its **Apache-2.0 licence**. These observations do not grant rights to every bundled native dependency or model.

The exact Windows native wheels were also downloaded and inventoried without executing them. `foundry-local-core-winml` contains `Microsoft.AI.Foundry.Local.Core.dll` and `Microsoft.Windows.AI.MachineLearning.dll`; the ORT wheels contain `onnxruntime.dll`, `onnxruntime_providers_shared.dll` and `onnxruntime-genai.dll`. **Those three native wheels did not contain licence/notice files**, so automatic notice copying alone is insufficient. Obtain the corresponding official distribution terms/notices before employee redistribution. [The wheel inventory](native-wheel-inventory.json) records exact filenames and SHA-256 digests; it is not a native execution or licence-approval result.

Before employee distribution, inspect and retain the exact installed versions' notices for Python/Tcl/Tk, PyAudioWPatch and bundled PortAudio/PyAudio components, NumPy/SciPy and linked math libraries, Pillow, pystray, PyInstaller and its bootloader exception, Microsoft Foundry native core, ONNX Runtime/GenAI, downloaded execution providers, and the actual Nemotron model. Their licence terms and redistribution obligations can differ. Native wheels may contain multiple third-party notices. Model terms are separate from the SDK's licence.

`build.py` copies licence/notice files from installed distributions and writes a `DEPENDENCIES.json` inventory under `THIRD_PARTY_NOTICES`. That is an evidence collection aid, **not a legal approval or a complete native/model licence audit**. Runtime downloads cannot all be captured from the build environment. Add those notices during provisioning/pilot review, resolve missing licence metadata, and obtain your organisation's redistribution approval. No application-source licence was chosen on behalf of the project owner.

Primary references: [Microsoft Python SDK packaging](https://github.com/microsoft/Foundry-Local/blob/main/sdk/python/README.md), [Microsoft Windows setup](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started), [PyInstaller bundling](https://pyinstaller.org/en/stable/operating-mode.html), [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch).
