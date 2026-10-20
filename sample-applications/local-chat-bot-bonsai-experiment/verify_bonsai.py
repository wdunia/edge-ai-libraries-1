#!/usr/bin/env python3
"""Verify the pinned publisher manifest without loading third-party code."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
import sys

MANIFEST_SHA256 = {
    "bonsai-1bit": "cc8648285ecee474e11b49865589c113dfe3b80b54093d66f01eb6edc79486af",
    "bonsai-ternary": "52b18b92c80a7a8099b4c8d2c92d537520677840e83cbcb6c5281c3e891198bd",
}
RUNTIME_FILES = {
    "bonsai-1bit": "runtime/intbit_runtime.py",
    "bonsai-ternary": "runtime/internary_runtime.py",
}
PLUGIN_SHA256 = {
    "bonsai-1bit": "90d151b25df57f6651b6a5a5d8f2e7486b764d2abdf2ba7d1b9f14e3cd2228a2",
    "bonsai-ternary": "fbf51b2fd61df7d3e6229b787ef97963164ae45da7e9509fe629fde2c1829cc3",
}
PLUGIN_FILE = "plugin/linux-x86_64/libopenvino_intel_gpu_plugin.so"
README_SHA256 = {
    "bonsai-1bit": "eed5415eaac5204384078d2dc7ac53a04406324279aac94e50917f2948bc0c8b",
    "bonsai-ternary": "b7c9fcd2f2a1ddbae1b7eb90a90a96b0e8d095dd37ba12abe3de1e227bb59aa0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(model_dir: Path, variant: str) -> None:
    if variant not in MANIFEST_SHA256:
        raise ValueError(f"Unsupported Bonsai variant: {variant}")
    if model_dir.is_symlink():
        raise ValueError(f"Model directory must not be a symlink: {model_dir}")
    manifest = model_dir / "CHECKSUMS.sha256"
    if sha256(manifest) != MANIFEST_SHA256[variant]:
        raise ValueError(f"Unexpected publisher checksum manifest: {manifest}")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        if match is None:
            raise ValueError(f"Malformed entry in {manifest}: {line!r}")
        digest, name = match.groups()
        relative = PurePosixPath(name)
        if (relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts)
                or name in entries):
            raise ValueError(f"Unsafe or duplicate checksum path: {name}")
        entries[name] = digest
    required = {PLUGIN_FILE, RUNTIME_FILES[variant], "runtime/install_plugin.py",
                "openvino_language_model.xml", "openvino_language_model.bin"}
    if not required.issubset(entries):
        raise ValueError(f"Publisher manifest omits required files: {required - entries.keys()}")
    if entries[PLUGIN_FILE] != PLUGIN_SHA256[variant]:
        raise ValueError("Plugin checksum differs from the pinned release")
    for name, digest in entries.items():
        path = model_dir
        for part in PurePosixPath(name).parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(f"Symlink in model artifact: {path}")
        if not path.is_file():
            raise ValueError(f"Missing Bonsai file: {path}")
        expected = README_SHA256[variant] if name == "README.md" else digest
        if sha256(path) != expected:
            raise ValueError(f"Missing or modified Bonsai file: {path}")
    for path in model_dir.rglob("*"):
        name = path.relative_to(model_dir).as_posix()
        if name == "CHECKSUMS.sha256" or name.startswith(".cache/huggingface/"):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink in model artifact: {path}")
        if path.is_file() and name not in entries:
            raise ValueError(f"Unlisted file in Bonsai artifact: {path}")
    print(f"Verified {len(entries)} files for {variant} against the pinned publisher manifest"
          + (" (README.md uses the pinned repository hash; its manifest entry is stale)"
             if "README.md" in entries else ""), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_bonsai.py <model-dir> <bonsai-1bit|bonsai-ternary>")
    verify(Path(sys.argv[1]), sys.argv[2])
