# Foundry Python streaming contract

The AI adapter is based on Microsoft's Python-specific documentation and official Python sample, then checked against the source inside the **official `foundry-local-sdk-winml==1.2.4` wheel** downloaded during development. The mutually conflicting cross-platform SDK was not installed.

This is **source-level wheel inspection on macOS**, not a successful import/initialisation of Windows native binaries. The installed-SDK check and real model execution still require Windows. There is no assertion here that the microphone baseline produced real speech on the Mac.

## Inspected API

| Operation | Official Python API in 1.2.4 |
| --- | --- |
| Configure native SDK | `Configuration(app_name=..., app_data_dir=..., model_cache_dir=..., logs_dir=..., log_level=LogLevel.ERROR)` |
| Initialise singleton | `FoundryLocalManager.initialize(config)` |
| Access singleton/catalog | `FoundryLocalManager.instance.catalog` |
| Register execution providers | `manager.download_and_register_eps(progress_callback=..., cancel_event=...)` |
| Resolve speech alias | `manager.catalog.get_model("nemotron-speech-streaming-en-0.6b")` |
| Inspect model cache/load state | `model.is_cached`, `model.is_loaded` properties |
| Download with progress/cancellation | `model.download(callback, cancel_event=event)` |
| Load/unload locally | `model.load()`, `model.unload()` |
| Audio client/session | `model.get_audio_client().create_live_transcription_session()` |
| Configure format | `session.settings.sample_rate=16000`, `channels=1`, `bits_per_sample=16`, `language="en"` |
| Bound SDK input buffer | `session.settings.push_queue_capacity=50` |
| Begin/feed/read/finish | `session.start()`, `session.append(pcm_bytes)`, `session.get_stream()`, `session.stop()` |
| Read response | `result.content[*].text`, `result.is_final`, `result.start_time`, `result.end_time`, `result.id` |

The session methods are **synchronous**; `get_stream()` yields results on a dedicated reader thread. `append()` copies bytes into a bounded SDK queue and may block under backpressure, so capture callbacks never invoke it directly. A separate app queue and feeder thread isolate it from capture and Tk. `stop()` drains the SDK push queue and flushes a final response before finishing the output stream. The reader is joined before final persistence.

The wheel's response documentation says the selected Nemotron model returns final results; the app supports partial updates when provided but never fabricates an interim transcript. Identified or timestamped duplicate final events are ignored. Identical words in different real segments are preserved; anonymous untimed identical finals cannot safely be distinguished from repeated speech.

SDK log levels use `LogLevel.ERROR` (`"Error"`), not a guessed lowercase enum string. No SDK REST service is configured or started; no audio-file transcription method is invoked.

## Installed Windows verification

Run from the Windows source environment:

```text
python main.py --sdk-check
python -m pytest -q tests/test_sdk_contract.py
python -m examples.microphone_sample
```

`--sdk-check` verifies that the installed distribution is exactly 1.2.4, rejects a simultaneously installed `foundry-local-sdk`, imports the native SDK Python classes and checks the documented live method names. Opening an actual live session then verifies its methods/settings too. A missing native dependency or mismatched package gets an actionable failure. API presence alone is not speech-recognition validation: speak into a real microphone, inspect real output, and repeat the loopback/Both hardware tests.

To repeat wheel-only inspection without loading native code:

```text
python -m pip download --no-deps --only-binary=:all: --dest sdk-wheels foundry-local-sdk-winml==1.2.4
python tools/inspect_sdk_wheel.py sdk-wheels/foundry_local_sdk_winml-1.2.4-py3-none-any.whl
```

The resulting JSON includes the wheel digest and inspected AST method names. The development inspection record is [sdk-wheel-contract.json](sdk-wheel-contract.json).

## PyAudioWPatch contract

The final capture wrapper was checked against the source in `pyaudiowpatch-0.2.12.8-cp312-cp312-win_amd64.whl`: device dictionaries expose `isLoopbackDevice`, `maxInputChannels`, `hostApi`, `defaultSampleRate` and `index`; the API includes `get_default_wasapi_loopback()`, WASAPI host/device enumeration, `is_format_supported()` and callback `open(..., start=False)`. This confirms method availability, not real hardware behaviour. In particular the wrapper handles `LookupError` when the current playback endpoint has no matching loopback analogue.

References: [Microsoft live transcription, Python sample](https://learn.microsoft.com/en-us/azure/foundry-local/how-to/how-to-live-transcribe-audio), [official sample repository](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/foundry-local/live-audio-transcription), [official SDK source](https://github.com/microsoft/Foundry-Local/tree/main/sdk/python), [SDK reference](https://learn.microsoft.com/en-us/azure/foundry-local/reference/reference-sdk-current#python-sdk-reference).
