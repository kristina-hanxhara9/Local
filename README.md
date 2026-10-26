# Local — Meeting Companion

Install this app on your own Windows PC from [kristina-hanxhara9/Local](https://github.com/kristina-hanxhara9/Local). Follow the [Windows installation steps](#install-on-your-windows-pc-step-by-step) below, including the local AI model download.

A Python-only Windows desktop assistant for live meeting transcription. Tkinter provides a compact floating widget and a larger transcript window. Microsoft Foundry Local performs speech recognition **in process on the laptop**, using `nemotron-speech-streaming-en-0.6b`. WASAPI microphone and playback loopback capture cover your voice and other meeting participants.

**Validation status:** implemented source and portable tests are available. Development took place on Apple Silicon macOS, not Windows. Real microphone/loopback recognition, offline WinML execution, the Windows installer, and the clean-laptop executable acceptance tests remain **unverified**. No Windows executable is included. See [the test report](docs/TEST_REPORT.md) and [Windows acceptance procedure](docs/WINDOWS_ACCEPTANCE.md).

## Requirements

- **Windows 11 24H2, build 26100 or later, x64.** This release targets x64 because the pinned PyAudioWPatch wheel is validated by inspection for Windows x64. Native ARM64 is not supported by this build script.
- **Python 3.11 or newer**, 64 bit, with Tcl/Tk, for source execution. Python **3.12 x64** is the suggested packaging target; installed native wheels must match the interpreter architecture. End users of a successfully validated packaged release do not need Python installed.
- A microphone and a WASAPI playback endpoint (speakers, wired headphones, or a compatible Bluetooth playback profile).
- A compatible Foundry speech-model variant and execution provider. Setup must actually load and test the model; a CPU, GPU or NPU that supports another model does not establish support for this speech model.
- Enough free memory and storage for the selected model/runtime. **16 GB system RAM and 8 GB free disk are planning allowances, not verified minimums or performance guarantees.** Device/runtime-specific memory and acceleration requirements must be established in the Windows pilot. Setup reports the OS, RAM on Windows, and free disk.
- Internet for initial pip installation, execution providers, and model provisioning. The application makes no cloud inference calls. Offline transcription after provisioning still needs Windows acceptance testing.

No Node.js, JavaScript, .NET SDK, web server, CLI inference service, or alternative inference engine is used by the application or build scripts. Foundry's native binaries, Windows ML, device drivers, and any Microsoft native runtime dependencies are distinct from the Python source; validate them on the target Windows image.

## Install on your Windows PC: step by step

Use **PowerShell** (Windows Terminal is fine). Run each block in order. These instructions install the app from source; no prebuilt Windows `.exe` is included. You do not need a paid AI account, an API key, Node.js, or a separately installed Foundry CLI.

### 1. Check your PC

Open **Settings → System → About**. You need Windows 11 **24H2 or later**, OS build **26100 or later**, and an **x64-based processor** (Intel/AMD). This version does not support Windows 10 or native ARM64. Update Windows and your graphics drivers first. See the memory/storage allowances under [Requirements](#requirements); model compatibility must be checked on your actual PC.

### 2. Install Python 3.12 x64 and Git

In PowerShell:

```powershell
winget install --exact --id Python.Python.3.12 --architecture x64 --source winget
winget install --exact --id Git.Git --architecture x64 --source winget
```

Accept the installers' prompts. If already installed, continue. **Close the terminal completely and open a new PowerShell window** so it sees the new commands. Check:

```powershell
py -3.12 --version
git --version
```

If `winget` is unavailable, install/update **App Installer** from the Microsoft Store, or use [Python's Windows installer](https://www.python.org/downloads/windows/) (Python 3.12, **Windows installer (64-bit)**) and [Git for Windows](https://gitforwindows.org/). Keep the Python launcher, pip, and Tcl/Tk options selected in the Python installer.

Package IDs and x64 installers are listed in Microsoft's WinGet manifests for [Python](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/12) and [Git](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Git/Git).

### 3. Download this app

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Apps" | Out-Null
Set-Location "$env:USERPROFILE\Apps"
git clone https://github.com/kristina-hanxhara9/Local.git
Set-Location .\Local
```

If GitHub asks you to sign in, use the GitHub account that has access to this repository. If you already cloned it into this folder, open that folder and use `git pull --ff-only` instead of cloning again.

Alternative without Git: use **Code → Download ZIP** on the repository, extract the ZIP, and open PowerShell in the extracted folder containing `main.py` and `install-windows.cmd`.

### 4. Install the application dependencies

In the `Local` folder:

```powershell
.\install-windows.cmd
```

Wait for **Installation complete**. The script checks Windows/Python, creates an isolated `.venv`, installs the pinned Windows speech SDK and audio packages from `requirements.txt`, and runs dependency and SDK checks. It stops at the first error. It does not download model weights or start audio capture. No virtual-environment activation or PowerShell execution-policy change is needed.

The equivalent manual commands are:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe main.py --diagnose
.\.venv\Scripts\python.exe main.py --sdk-check
```

Install **only** `foundry-local-sdk-winml==1.2.4` in this environment. Do not add `foundry-local-sdk` or the unrelated `foundry-local` package. The SDK supplies its own required OpenAI Python dependency; this app does not instantiate an OpenAI client or use an inference HTTP endpoint.

### 5. Open the app and download the local AI model

```powershell
.\start-windows.cmd
```

In the setup window:

1. Review **Check this computer**.
2. Click **Check** beside **Check the speech model**. The model alias is `nemotron-speech-streaming-en-0.6b` (English speech recognition).
3. Click **Download** beside **Prepare local inference**, approve the download, and wait until the app reports **Model loaded successfully**. This downloads the speech model and hardware-specific execution providers using Microsoft Foundry Local. It can take several minutes and several GB. If the availability check fails, try **Download** to prepare the execution providers, then retry; persistent failures need the troubleshooting steps below.

**The model is downloaded onto your Windows PC; its weights are not committed to GitHub.** The default model cache is `%LOCALAPPDATA%\MeetingCompanion\Foundry\Models`. Runtime data is kept under `%LOCALAPPDATA%\MeetingCompanion\Foundry`. Keep these folders after setup. You do not need to download the model manually or run a cloud service. Microsoft's [Python live transcription guide](https://learn.microsoft.com/en-us/azure/foundry-local/how-to/how-to-live-transcribe-audio#prerequisites-2) describes the native SDK integration.

### 6. Test your microphone and meeting audio

1. In Windows **Settings → Privacy & security → Microphone**, enable microphone access and access for desktop apps.
2. In the app, click **Devices** and select the microphone and playback device used by Teams/Zoom/Meet. A headset helps reduce echo.
3. Click **Test mic**, approve the four-second test, and speak.
4. Play speech through your selected headphones/speakers, click **Test audio**, and approve the four-second test.
5. Click **Live test**, approve capture, speak, and have speech playing on the selected computer-audio device. Open the transcript and check that actual words appear from each source. Press **Stop**.
6. Tick the box confirming that you reviewed the recognised speech, then click **Finish setup**. Startup and reminders are optional and default off.

The model and transcription run locally. The PC still needs internet for initial package, model and runtime downloads. Real Windows recognition and offline behaviour must be verified on your hardware; see [Windows acceptance](docs/WINDOWS_ACCEPTANCE.md).

### 7. Open it again later

In PowerShell:

```powershell
Set-Location "$env:USERPROFILE\Apps\Local"
.\start-windows.cmd
```

You can also double-click `start-windows.cmd` in File Explorer. Keep its console window open while using the app; use the app's **Quit…** action to close cleanly. Use **Start Meeting**, **View Transcript**, and **Stop** for everyday transcription. If you used a ZIP or a different folder, use your actual folder path instead.

After a successful first test, quit the app, disconnect networking, reopen it, and repeat a short live test to verify offline use on your PC. If it fails, reconnect, reopen Setup, prepare the runtime/model again, and retry. Offline operation is not yet validated by this repository's development tests.

### Update the app later

Stop the meeting and quit the app, then:

```powershell
Set-Location "$env:USERPROFILE\Apps\Local"
git pull --ff-only
.\install-windows.cmd
.\start-windows.cmd
```

Updates keep settings, saved transcripts and the model cache in `%LOCALAPPDATA%\MeetingCompanion`. If you installed from ZIP, download and extract a fresh ZIP and run its installer script. Do not copy `.venv` from another PC; create it locally.

### Troubleshooting

| Problem | What to do |
| --- | --- |
| `py` or `git` is not recognised | Reopen the terminal after installing. Repair Python 3.12 with its launcher selected, or reinstall Git with its command-line option enabled. |
| `No suitable Python runtime found` | Install **Python 3.12 x64**, then reopen PowerShell. |
| `Repository not found` or clone authentication fails | Check the URL and sign in to GitHub with an account that has access; use Code → Download ZIP while signed in if needed. |
| Installation or `--sdk-check` fails | Read the first error. Confirm Windows 11 24H2+ x64 and Python 3.12 x64, internet access, Windows updates and current drivers. Rerun the installer after fixing it. |
| Conflicting Foundry SDKs | Run `.\.venv\Scripts\python.exe -m pip uninstall -y foundry-local-sdk foundry-local`, then `.\.venv\Scripts\python.exe -m pip install --force-reinstall foundry-local-sdk-winml==1.2.4`, and rerun the installer. |
| Model unavailable or unable to load | Reopen Setup and use Download to provision providers/model. Check Windows/drivers, free RAM/disk, and the SDK error. This speech model may not support your hardware/runtime. |
| Missing native DLL or runtime | Apply Windows/driver updates and install the native prerequisite identified by the actual SDK error. See [packaging/runtime notes](docs/PACKAGING.md#runtime-and-models). |
| No microphone or computer-audio text | Enable microphone permission, match devices to your meeting app, and test each source separately in Settings. Computer audio must be playing through the selected endpoint. |
| App is already running or no window appears | Open Meeting Companion from the system tray/taskbar, or quit that instance before relaunching. |

For a diagnostic report without opening audio devices:

```powershell
.\.venv\Scripts\python.exe main.py --diagnose
.\.venv\Scripts\python.exe main.py --sdk-check
```

The final app uses **PyAudioWPatch for both microphone and system capture**. Its WASAPI API was checked against the pinned wheel; simultaneous operation still requires real Windows testing.

## First run

The setup window has eight steps:

1. Inspect Windows version, architecture, memory and disk.
2. Check whether the speech-model alias is available and cached. This does not approve downloads.
3. Approve model and execution-provider downloads. Progress and cancellation are available; loading verifies that the model can actually run locally.
4. Approve a four-second microphone access/level test.
5. Approve a four-second playback loopback test while real speech is playing through the selected meeting endpoint.
6. Choose devices in Settings. `Windows default` resolves again when capture starts. Explicit choices store names plus host API instead of stale numeric indices; a missing choice fails clearly.
7. Start a short **live** transcription test. Speak, have a remote participant speak, inspect the transcript, and press Stop. Confirm the recognised speech before finishing setup.
8. Optionally enable startup and periodic reminders. These options default off. Setup completion checks that the selected capture modes were exercised and that a stopped live test contains actual final text. It cannot independently judge recognition accuracy.

The capture tests show RMS levels; opening an audio stream is not proof of successful recognition. Test microphone and computer audio independently before accepting Both mode.

## Everyday use

- Join Teams, Zoom or Google Meet, then press **Start Meeting**. Confirm live-capture permission and your employer's recording/consent policy requirements. Transcription never starts from login, a timer, a process detector, a window opening, or a model download.
- **Both** is the default. Settings and the transcript window offer Microphone only, Computer audio only, or Both. Change sources while stopped. Match the loopback endpoint to the playback device selected by the meeting application, which can differ from the Windows default.
- Partial hypotheses replace the current temporary segment; final SDK results become timestamped entries. Nemotron in SDK 1.2.4 may produce only final results. No speaker identification or diarisation is provided. Timestamps are offsets from meeting start, including paused periods.
- **Pause** closes audio devices and flushes the current SDK session; **Resume** creates a fresh live session. Speech during the pause is not captured. The timer includes the pause.
- **View Transcript** opens title/date/start-time/duration, live text, search, copy, save, export and notes. Auto-scroll can be disabled. Input meters help detect an incorrect endpoint.
- Close either window or use the widget's minimise button to keep an active meeting running. The root hides in the system tray when available; if tray creation fails it minimises to the taskbar. **Quit…** is explicit and asks before stopping an active operation.
- **Stop** closes capture, flushes pending final results and leaves the transcript available. Save to History or export UTF-8 TXT/Markdown. Export and copy include final text, metadata and notes, never speculative partial text.
- **History** searches saved titles, notes and transcript text and supports export, copy and deletion. A crash-recovered `active` record is displayed as unfinished. Search shows the latest 200 matches.

## Local storage and privacy

Default paths:

| Content | Location |
| --- | --- |
| Settings | `%LOCALAPPDATA%\MeetingCompanion\settings.json` |
| SQLite history | `%LOCALAPPDATA%\MeetingCompanion\Transcripts\meetings.sqlite3` |
| Foundry data/cache | `%LOCALAPPDATA%\MeetingCompanion\Foundry` |
| Installed application | `%LOCALAPPDATA%\Programs\MeetingCompanion` |

Autosave defaults **off**. Enable it to save metadata, notes and final entries in a local SQLite transaction every five seconds, with a final save after Stop. An explicit Save during a meeting also updates that saved record on Stop. Without autosave or an explicit Save, the meeting lives in memory; starting another meeting or quitting offers a save/discard choice. Save failures are reported and an unsuccessful save-before-new-meeting does not discard the previous transcript. Export can recover the current in-memory transcript if SQLite is unavailable.

Changing the history folder opens a separate database there; it does not move or merge old history. Use a **local disk** for SQLite WAL transactions. Keep the old folder if you need its history. Back up a stopped app's database together with any remaining `-wal`/`-shm` files, or use SQLite's backup API; do not copy just a live database file.

No raw audio files are created. Short bounded PCM buffers are held in memory. Model/runtime downloads and catalog access may contact Microsoft's provisioning infrastructure; meeting content is passed only to the SDK's native local audio API. No REST service is started, and the application has no telemetry or external transcript store. SDK logging is configured at Error level; native-runtime behaviour and operating-system diagnostics should be checked by the organisation during a privacy review.

**Loopback can include notifications, music and other applications on the selected playback endpoint.** It is endpoint capture, not per-process meeting capture. Local transcripts/exports are not encrypted by this application. Use Windows account security, disk encryption and your employer's retention policies. Windows may page process memory to disk. Deleting a meeting from history is not a forensic secure erase and does not delete exported copies. This app is not compliance-certified.

## Audio design and limitations

Capture callbacks only enqueue native PCM with device ADC timestamps mapped onto a common monotonic clock. Dedicated threads perform float downmixing, continuous-phase resampling with stateful anti-alias filtering, timeline alignment with a 240 ms jitter buffer, and headroom-controlled mixing into 16 kHz mono PCM16. Independent device timestamps place each block so relative clock drift does not accumulate as a simple concatenation error. Final buffered audio is drained on Stop.

Both-mode signals each receive 0.5 gain to avoid clipping. Conservative high-correlation waveform suppression can reduce delayed playback bleed (up to 200 ms). **It is not acoustic echo cancellation**: room echo, Bluetooth latency, double-talk, severe device drift and endpoint changes can impair quality. A headset is preferable for the pilot. Arrival-time fallback for missing ADC timestamps produces an explicit alignment warning. There is no silent fallback to microphone-only capture.

Capture overruns, persistently missing/misaligned sources, a disconnected device, or an inference backlog stop capture and mark the meeting interrupted. Some WASAPI drivers cease delivering callbacks during silence; a five-second callback absence is reported rather than pretending that source is verified. If this affects your hardware, use a compatible endpoint or explicitly select a different capture mode. Switching Bluetooth profiles or hot-plugging devices requires Stop, device re-selection, and a new meeting. Extremely stalled native drivers/inference can require a process restart; Python cannot safely terminate a blocked native call. The UI remains on its own event loop while cleanup runs.

Additional limits: English default, no audio/file import, no summarisation, no per-person labels, no process/meeting detection, no calendar access, no sleep/resume recovery, no native ARM64 release and no production certification. There is no promised recognition latency or accuracy before the hardware pilot.

## Test and package

For development, optional tests and building an `.exe`, install the extra tools first. Run these commands from the app folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```text
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q tests\test_ui.py --run-ui
.venv\Scripts\python.exe -m pytest -s -q tests\test_windows_hardware.py --run-hardware
.venv\Scripts\python.exe build.py --installer
```

The hardware command explicitly enables live capture; provision the model first and follow [the Windows acceptance instructions](docs/WINDOWS_ACCEPTANCE.md). Normal tests do not capture audio. GUI checks use an explicit test fixture, not a production demo mode.

To reproduce the separate Microsoft microphone baseline after installing development dependencies:

```powershell
.\.venv\Scripts\python.exe -m examples.microphone_sample
```

It uses upstream **PyAudio**. Approve runtime/model download and microphone capture separately, speak and check recognised words, then press Ctrl+C to stop and unload. It could not run on the development Mac.

Build **on Windows x64**, not on macOS. PyInstaller collects Tk/Tcl, PyAudioWPatch, NumPy/SciPy, SDK Python modules, distribution metadata and native Foundry/ONNX Runtime package trees. The output is the complete `dist\MeetingCompanion` directory plus, with `--installer`, `dist\MeetingCompanionInstaller.exe`. The onedir executable is not standalone without its sibling `_internal` directory. Models and hardware-specific execution providers remain first-run downloads with explicit user permission. No Windows build has been produced or smoke-tested here.

See [packaging and licences](docs/PACKAGING.md), [SDK contract verification](docs/SDK_VERIFICATION.md), and [Intune distribution](docs/INTUNE.md). The installer is silent, per user, creates a Start Menu shortcut and uninstall registration, and never enables capture/startup/reminders or downloads a model during installation. User data is retained on uninstall.

## Source layout

```text
main.py                       GUI and diagnostic entry point
examples/microphone_sample.py  Phase-1 official-API/PyAudio baseline
meeting_companion/
  ai/                         Native Foundry adapter and streaming workers
  audio/                      WASAPI devices, resampler, timeline mixer and pump
  config/                     Validated settings and atomic file writes
  services/                   Session lifecycle, SQLite, tray, reminders, startup
  ui/                         Tkinter widget, transcript, setup, settings, history
tests/                        Portable, UI and opt-in Windows hardware tests
build.py                      PyInstaller application/installer build
installer.py                  Silent user installation/removal
docs/                         Validation, packaging, SDK and Intune procedures
```

## Primary references

AI integration follows only Microsoft's Python documentation, official sample and official SDK package source:

- [Microsoft live microphone transcription, Python section](https://learn.microsoft.com/en-us/azure/foundry-local/how-to/how-to-live-transcribe-audio#prerequisites-2)
- [Official Python sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/foundry-local/live-audio-transcription)
- [Microsoft Python SDK source](https://github.com/microsoft/Foundry-Local/tree/main/sdk/python)
- [Foundry Local SDK reference](https://learn.microsoft.com/en-us/azure/foundry-local/reference/reference-sdk-current#python-sdk-reference)
- [Windows Foundry Local getting started](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started)
- [Foundry Local documentation](https://learn.microsoft.com/en-us/azure/foundry-local/)
- [Microsoft WASAPI loopback behaviour](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)
- [PyAudioWPatch upstream device/capture API](https://github.com/s0d3s/PyAudioWPatch)
