"""Read official wheel source through AST without executing its Windows code."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

CONTRACT = {
    "foundry_local_sdk/foundry_local_manager.py": {"FoundryLocalManager": ["initialize", "download_and_register_eps"]},
    "foundry_local_sdk/openai/audio_client.py": {"AudioClient": ["create_live_transcription_session"]},
    "foundry_local_sdk/openai/live_audio_session.py": {"LiveAudioTranscriptionSession": ["start", "append", "get_stream", "stop"]},
    "foundry_local_sdk/detail/model.py": {"Model": ["download", "load", "unload", "is_cached", "is_loaded", "get_audio_client"]},
}


def inspect(path):
    record = {"wheel": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "validation": "Static AST inspection only; Windows native execution not performed", "classes": {}}
    with ZipFile(path) as archive:
        for source, classes in CONTRACT.items():
            tree = ast.parse(archive.read(source).decode("utf-8"))
            for name, required in classes.items():
                cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
                methods = {node.name: [arg.arg for arg in node.args.args]
                           for node in cls.body if isinstance(node, ast.FunctionDef)}
                for method in required:
                    if method not in methods:
                        raise ValueError(f"Missing {name}.{method}")
                record["classes"][name] = {method: methods[method] for method in required}
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect(args.wheel), indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
