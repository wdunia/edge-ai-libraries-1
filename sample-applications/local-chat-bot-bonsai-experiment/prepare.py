#!/usr/bin/env python3
"""Prepare only the experiment's disposable ChatQnA copy and OVMS config."""

import argparse
import json
from pathlib import Path


def prepare_chat(work_dir: Path) -> None:
    chain = work_dir / "app" / "chain.py"
    content = chain.read_text(encoding="utf-8")
    start_marker = 'template = """\n'
    start = content.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Chat prompt anchor missing: {chain}")
    end = content.find('"""', start + len(start_marker))
    if end < 0 or "<|start|>system" not in content[start:end]:
        raise RuntimeError(f"Expected gpt-oss-specific template: {chain}")
    template = (
        'template = """\n'
        "Answer the question directly. Use relevant context if available; otherwise "
        "answer from general knowledge. If you do not know, say so.\n\n"
        "Conversation history:\n{history}\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n"
        '"""\n'
    )
    chain.write_text(content[:start] + template + content[end + 4:], encoding="utf-8")


def prepare_embedding(source: Path, destination: Path, model: str) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid OVMS config: {source}")
    count = 0
    for key, entries in data.items():
        if key.endswith("_config_list"):
            if not isinstance(entries, list):
                raise ValueError(f"Expected list for {key}")
            data[key] = [entry for entry in entries if model.split("/")[-1] in json.dumps(entry)]
            count += len(data[key])
    if not count:
        raise RuntimeError(f"Embedding {model} not found in {source}")
    destination.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--ovms-dir", type=Path, required=True)
    parser.add_argument("--embedding-model", default="nomic-ai/nomic-embed-text-v1.5")
    args = parser.parse_args()
    prepare_chat(args.work_dir)
    models = args.ovms_dir / "models"
    prepare_embedding(models / "config_all.json", models / "config_embedding_only.json",
                      args.embedding_model)


if __name__ == "__main__":
    main()
