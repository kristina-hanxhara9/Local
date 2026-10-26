# Employee distribution with Microsoft Intune

Use a **user-context Win32 application** for this per-employee build. Do not install this per-user package as SYSTEM: its paths and registry entries belong to the account executing it. Keep installation separate from employee consent and model provisioning.

This procedure is prepared for an IT pilot; deployment has not been executed from this repository.

1. Complete [Windows acceptance](WINDOWS_ACCEPTANCE.md), licence review and signing. Build `MeetingCompanionInstaller.exe` on Windows x64. Keep only release installation content in the input folder; exclude transcripts, model caches, signing keys and the development environment.
2. Package the installer using Microsoft's **Win32 Content Prep Tool**. This is an Intune administrative distribution tool, not an application build/runtime dependency:

   ```text
   IntuneWinAppUtil.exe -c C:\Release\MeetingCompanion -s MeetingCompanionInstaller.exe -o C:\Release\Intune -q
   ```

3. In Intune admin center, create a Windows app (Win32), upload the `.intunewin` file, and enter employee-facing name/description/privacy/support information. Use the organisation as publisher only after it has accepted ownership of the release.
4. Configure **Install behavior: User**. Target a pilot employee group first. Set x64 architecture and Windows 11 24H2+ applicability; if Intune's OS selector is coarser, use the organisation's supported custom requirement mechanism to enforce build 26100. The installer also rejects older builds. Establish memory/disk/model/provider eligibility from the pilot; do not claim every x64 laptop supports the speech model.
5. Use these silent commands from the staged package:

   ```text
   MeetingCompanionInstaller.exe --install
   MeetingCompanionInstaller.exe --uninstall
   ```

   The uninstall command intentionally names the packaged installer rather than an environment-variable path. Microsoft's Intune documentation states environment-variable expansion is not supported directly in uninstall commands. Both operations are noninteractive and do not open audio devices. Map `0` to success, `1618` to retry, and `1` to failed. Configure no requested reboot.
6. Use a **registry detection rule**, in the user context / HKCU, for:

   ```text
   HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\MeetingCompanion
   Value: DisplayVersion
   Detection: version equals 1.0.0
   Associated with a 32-bit app on 64-bit clients: No
   ```

   Pair this, if your policy requires, with a file-exists rule for the installed executable under the employee's local app-data Programs folder. Test HKCU evaluation in your enrolled device/user model; Intune context differences matter. Upgrade the detection version when you publish a new release. The presence of app files is not a model-readiness test.
7. Publish as available in Company Portal for the pilot, or assign required only after testing installation/retry/upgrade/removal for your managed user context. If the app is running, the installer returns retry instead of ending a meeting. Communicate that employees should Quit from the tray before an update. Set supersedence and dependencies to match your release policy.
8. On first employee launch, the setup window requests permission for model/runtime downloads, microphone tests, computer-audio tests and a real transcription test. Nothing starts recording because Intune installed the app. Startup, reminders and autosave default off; the employee chooses them.
9. If Windows/driver/native-runtime prerequisites are needed on the corporate image, deploy their approved vendor packages as separate Intune dependencies. Do not add cloud transcription as a workaround for unsupported devices. Coordinate allowed provisioning network access with IT; meeting content does not need outbound inference access.
10. Pilot with speakers, wired headphones and the Bluetooth devices employees actually use. Verify two-user isolation, HKCU startup, tray access, uninstall data retention, updates while idle and updates attempted during a meeting. Monitor installation results using ordinary Intune deployment reporting; do not collect meeting transcripts as telemetry.

Keep employee instructions simple: open **Meeting Companion** from the Start Menu, finish setup, select the meeting playback endpoint, obtain required consent, then explicitly Start when joining a meeting. User data survives app removal; retention/deletion is governed separately by the employer.

Official references: [Prepare Win32 app content](https://learn.microsoft.com/en-us/intune/intune-service/apps/apps-win32-prepare), [Add and assign Win32 apps](https://learn.microsoft.com/en-us/mem/intune-service/apps/apps-win32-add). Verify portal labels and context behaviour against your tenant at rollout time.
