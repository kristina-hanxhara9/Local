# Windows device acceptance — pending execution

No check below has been marked passed on the development Mac. Record date, Windows build, Python/package versions or signed release hashes, CPU/GPU/NPU and driver, selected model ID/provider, microphone, playback endpoint and test result for each pilot laptop. Do not use invented or prerecorded transcript fixtures as evidence of real recognition.

## Baseline and setup

1. Use Windows 11 24H2+ x64. Install the source environment from the README. Run `python -m pip check`, `python main.py --diagnose` and `python main.py --sdk-check`. Confirm that only the Microsoft WinML SDK variant is installed.
2. Run `python -m examples.microphone_sample`. Approve runtime/model download and separately approve microphone capture. Speak a few previously unprepared sentences. Confirm that **your actual speech** appears as final streaming text. Press Ctrl+C and verify the microphone is released. Record errors and output; this must precede declaring the desktop speech path functional.
3. Open the desktop app and complete the eight setup steps. Deny the first capture prompt and verify that Windows' microphone indicator does not activate. Confirm the model download requires an affirmative action and cancellation is reported. Verify hardware/provider failures are useful and never invoke a cloud fallback.

## Live endpoint matrix

Test each configuration with a real remote participant. A local machine's own notification sound is not proof that meeting speech has been captured. Ask the participant to say a fresh sentence while you remain quiet, then reverse roles.

| Device configuration | Mic only: employee recognised | Computer only: remote participant recognised | Both voices recognised | Stop releases endpoints |
| --- | --- | --- | --- | --- |
| Laptop speakers + built-in mic | Pending | Pending | Pending; check echo | Pending |
| Wired headphones + headset/built-in mic | Pending | Pending | Pending | Pending |
| Approved Bluetooth headphones in actual meeting profile | Pending | Pending | Pending; check profile changes | Pending |

For each row, test Teams, Zoom and Google Meet as used by your organisation. Select the loopback endpoint matching the application's playback device; test an intentionally wrong endpoint and verify the visible meters/transcript expose the mismatch. Configure microphone and playback endpoints independently. Record unsupported combinations instead of treating microphone-only success as a Both-mode pass.

Automated opt-in live checks can support (not replace) the manual review:

```text
python -m pytest -s -q tests/test_windows_hardware.py --run-hardware
```

This command explicitly enables 12 seconds of real capture for each mode and requires at least one actual final model result. It does not download a model or save raw audio. During Microphone only, speak. During Computer audio only, have a remote participant speak. During Both, take turns and then speak simultaneously. **The Both test's nonempty-text assertion alone does not prove both speakers were recognised**; inspect the actual output for each voice. Cancel the command if you lack required consent. Use `-k` or pytest's parameter node selection when testing one mode at a time.

## Session and reliability checks

- Start once; double-click Start and launch a second process. Confirm only one active meeting/session/process captures audio.
- Verify live text appears while speech occurs, timestamps advance sensibly, interim text (when the model emits it) is replaced, and final words are not repeated by UI updates. Repeated spoken words should remain present. Review English recognition accuracy and latency against your requirements; no numerical accuracy target has been measured here.
- Pause, confirm audio devices are released, speak while paused, then Resume. Paused speech must be absent. Verify the new stream's timestamps align with the meeting clock. Both-mode mic/remote content must remain present after resuming.
- Close the transcript window, close/minimise the widget, and inspect the tray icon. Have the participant continue speaking. Restore from the tray and verify transcription continued. Test taskbar fallback if tray creation is unavailable. The explicit Quit command should ask before stopping an active operation.
- Run a long meeting (at least an hour) to measure latency, CPU/RAM, queue depth effects and clock drift. Play remote speech and speak simultaneously to check mix headroom/echo suppression. Repeat with echo reduction disabled. Test silence for more than five seconds; if the driver ceases callbacks and the app reports it, record that endpoint as a current limitation.
- Unplug microphone/headphones, switch Bluetooth hands-free/stereo profile, disable playback, and change default devices. Confirm an interrupted status and useful error instead of silently losing computer audio. Stop and re-select endpoints before retrying. Test sleep/resume; automatic recovery is not implemented.
- Stop while a participant finishes a sentence. Confirm the SDK's last result is flushed, the transient partial disappears, the devices release and title/notes/final status are saved correctly when enabled. Check another app can immediately open the microphone.
- Simulate insufficient disk space/unwritable history folder. Capture should stay responsive, Save/Autosave should report failure, and the in-memory transcript should remain exportable to a writable folder. A save-before-new-meeting failure must preserve the previous meeting. A requested save-on-quit failure must cancel quitting; an explicit subsequent discard choice may exit.
- Enable autosave, then terminate the process unexpectedly during the test meeting. Reopen and inspect History: final committed text/notes should be recoverable up to the most recent transaction and the meeting labelled unfinished. No raw audio files should exist.

## History, privacy and offline operation

- Save, restart, browse, search titles/notes/final words, copy, and export TXT and Markdown. Verify Unicode text, timestamps, title and typed notes. Delete a stopped saved meeting and confirm it disappears from History. Exported copies remain until separately deleted.
- Change the history folder while stopped; confirm old history remains in the previous folder and new saves use the selected folder. Try changing during a meeting and confirm it is rejected.
- Enable/disable startup and reminders, sign out/in, and verify startup goes to the tray without microphone access. Verify reminder interval/cooldown, suppression during recording, and no automatic capture. Check the HKCU startup value uses the installed executable and `--tray`.
- Monitor process networking with your organisation's approved tools. During provisioning, catalog/model/provider requests are expected. During speech, verify no audio/transcript goes to any remote inference endpoint and no local REST service is started. Investigate native SDK/runtime diagnostics as well as application code; source inspection alone is not a network-capture result.
- After successful model/provider provisioning, close the app, disconnect networking, reopen it and perform mic, loopback and Both tests. **Cold restart offline** matters; a warm loaded-model test is insufficient. If the installed catalog/provider fails offline, record the exact SDK error and do not pass acceptance until resolved.

## Packaged executable and Intune

- Build with `python build.py --installer` on Windows. Review bundled licence/notice files, runtime DLL collection and release hashes. Complete organisational licence approval and signing.
- On a clean compatible Windows laptop without Python/Node.js/.NET SDKs, silently install as the intended employee, launch from the Start Menu, provision with permission, and repeat real speech tests. Check no Python installation is consulted from the build machine.
- Test user-context Intune detection, install, retry while app runs, upgrade while idle, uninstall, optional startup removal and retention of employee history. Exercise at least two employee accounts on one device. No install/update should silently stop a meeting or turn on audio.
- Record all 15 requested acceptance outcomes individually. Portable unit tests and source/wheel inspection only establish their stated scope; they do not pass hardware, offline-runtime or clean-machine acceptance.
