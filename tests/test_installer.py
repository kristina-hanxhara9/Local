import hashlib
import json

import pytest

from installer import verify_payload


def test_installer_manifest_verifies_payload_bytes(tmp_path):
    exe = tmp_path / "MeetingCompanion.exe"
    exe.write_bytes(b"test-only binary fixture")
    manifest = {exe.name: hashlib.sha256(exe.read_bytes()).hexdigest()}
    (tmp_path / "SHA256SUMS.json").write_text(json.dumps(manifest))
    verify_payload(tmp_path)
    exe.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        verify_payload(tmp_path)


def test_installer_rejects_manifest_path_escape(tmp_path):
    (tmp_path / "SHA256SUMS.json").write_text(json.dumps({"../other-file": "bad"}))
    with pytest.raises(ValueError, match="path"):
        verify_payload(tmp_path)
