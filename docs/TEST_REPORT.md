# Validation report — 26 October 2026

Development host: Apple Silicon macOS, Python 3.14.10, Tk 9.1. The target is Windows 11 24H2+ x64. **No Windows hardware, native WinML inference, packaged Windows executable or Intune deployment was available for this validation.**

## GitHub source publication checks — 26 October 2026

The Windows README now includes installation from GitHub, local model/runtime provisioning, device tests, relaunch/update commands and troubleshooting. `install-windows.cmd` installs runtime requirements and runs dependency/SDK checks; `start-windows.cmd` launches the app using that folder's virtual environment. These batch scripts have been reviewed but **not executed on Windows**. Model weights are provisioned by the app on each target PC and are not part of the Git repository.

For this publication, `.venv/bin/python -m pytest -q` completed with **68 passed, 10 skipped** in 2.59 s. This run did not enable optional GUI or hardware tests. Dependency checking reported no broken requirements, Python compilation succeeded, and diagnostics correctly reported this Mac as unsupported for Windows capture/inference. README local file links resolved. Development environments, caches and generated release archives are excluded from Git.

## Executed checks

| Check | Actual result | Scope |
| --- | --- | --- |
| `python -m pytest -q --run-ui` | **74 passed, 4 skipped** in 4.29 s | Portable behaviour plus six real Tkinter UI checks |
| Installed Windows SDK contract test | **Skipped** in that run | Requires Windows and the installed pinned WinML package |
| Three opt-in live-speech tests (mic/computer/Both) | **Skipped** in that run | No Windows devices; live capture was not enabled |
| `python -m compileall -q main.py build.py installer.py meeting_companion examples tools tests` | Completed without syntax errors | Python compilation, not native-library execution |
| `python -m pip check` | No broken requirements found | Development virtual environment only |
| `python main.py --diagnose` | Completed; reported unsupported OS and missing Windows packages | No device access or model download |
| `python main.py --sdk-check` | Expected actionable Windows-required error | No successful installed native SDK validation claimed |
| `python -m examples.microphone_sample` | Expected actionable Windows-required error | **No real microphone recognition occurred** |
| `python build.py --installer` | Refused cross-building from macOS | **No Windows executable or installer produced** |
| Official SDK wheel AST inspection | Required method names/signatures found in 1.2.4 | [Static contract record](sdk-wheel-contract.json); no native code executed |
| Exact native wheel inventory | DLL names and hashes recorded | [Inventory](native-wheel-inventory.json); not a loader test |
| Optional screenshot export from native preview | Host screenshot capture failed (`could not create image from rect`) | No pixel-level visual review claimed; real Tk window/geometry checks did execute |

The final combined test command explicitly enabled Tk windows, **not hardware capture**. Earlier failures in storage search and a clipped Settings layout were fixed before this recorded result. Tests use isolated temporary files; simulated PCM/SDK results are confined to tests and the clearly labelled UI-preview tool. There is no production synthetic transcript or audio fallback.

Portable coverage includes continuous resampling at five rates, filtering above the target Nyquist frequency, stereo downmix, timestamped overlap, fixed mix headroom, conservative delayed-waveform suppression, timeline wrap/gaps/late delivery, native-format callback arguments, nonblocking queue-overrun handling, callback timestamp fallback, and stream cleanup policy. These prove algorithm/control behaviour against fixtures, not real hardware timing or acoustic quality.

Lifecycle tests exercise the one-session guard, fresh sessions after pause, final-tail flushing before persistence, device/model error containment, explicit-save/autosave behaviour, notes/title persistence, save-before-new-meeting failure, save-on-quit failure/cancellation, autosave preference changes during capture, and normal unload order. Storage tests exercise Unicode exports, literal search, atomic rollback, repeated progressive saves, concurrent local reads/writes and cascading deletion. Installer tests verify manifest integrity/path confinement; they do not exercise Windows install/rollback/COM/registry operations.

Native UI smoke checks instantiate actual Tk windows and verify setup/settings scrolling fits the requested window sizes, both themes render without Tk callback errors, partial text is replaced, finals appear once, search highlighting and notes work, hiding a transcript keeps the application alive, and Quit destroys the GUI cleanly. They do not substitute for a Windows DPI/accessibility or tray review.

## Requested acceptance outcomes

| # | Outcome | Evidence / remaining work |
| --- | --- | --- |
| 1 | Runs without Node.js or .NET | Python source/build path inspected; clean packaged Windows runtime test pending |
| 2 | Application implemented in Python | Source delivered; no JS/TS/C#/web app source |
| 3 | Actual Foundry Local inference | Official native streaming adapter and inspected SDK API; **real inference pending Windows** |
| 4 | Start begins live capture | Permission/control flow and callback policy tested with doubles; actual device opening pending |
| 5 | Microphone speech becomes text | **Pending real Windows speech test** |
| 6 | Teams participant audio becomes text | **Pending real meeting and loopback test** |
| 7 | Headphone speech capture | **Pending wired/Bluetooth endpoint matrix** |
| 8 | Simultaneous microphone + computer audio | Alignment/mix algorithms tested; actual dual-device timing/recognition pending |
| 9 | Transcript updates in real time | SDK consumer and native UI update logic tested; actual recognition latency pending |
| 10 | Minimise does not stop transcription | Lifecycle/window separation implemented and hide smoke check passed; real Windows tray/live test pending |
| 11 | Stop releases devices | Cleanup policy and fake-stream tests passed; real driver release test pending |
| 12 | Transcript export | TXT/Markdown Unicode, timestamp and notes export tests passed locally |
| 13 | Works offline after provisioning | **Pending cold offline restart with model/provider cache** |
| 14 | No cloud inference transmission | App source uses native in-process SDK only; Windows process/network/native-runtime audit pending |
| 15 | Packaged EXE runs on a clean laptop | **Pending Windows build, native DLL smoke test and clean-machine validation** |

Follow [WINDOWS_ACCEPTANCE.md](WINDOWS_ACCEPTANCE.md) before accepting these pending items. Do not convert a skipped test, static API inspection, model availability check or nonempty Both-mode transcript into a claim that every real participant/device path works.

The native wheels inspected here omit redistribution notices; the SDK Python wheel and PyAudioWPatch wheel provide MIT and Apache-2.0 texts respectively. See [PACKAGING.md](PACKAGING.md). Runtime/model licence review, signing and organisational approval remain prerequisites to employee rollout, not completed test results.
