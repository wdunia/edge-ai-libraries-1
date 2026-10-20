#!/usr/bin/env python3
"""Require real incremental tokens from the container-local Bonsai endpoint."""

import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

models = {
    "bonsai-1bit": "Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc",
    "bonsai-ternary": "Wondernutts/Bonsai-27B-INTERNARY-OpenVINO-Arc",
}
model = models[os.environ["BONSAI_VARIANT"]]
payload = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content":
                  "Answer directly without a thinking section or reasoning. "
                  "In one sentence, explain why packed weights use less memory."}],
    "stream": True,
    "max_tokens": 256,
    "temperature": 0.01,
}).encode()
request = Request("http://127.0.0.1:8000/v1/chat/completions",
                  payload, {"Content-Type": "application/json"})
started = time.perf_counter()
first = None
fragments = []
finished = False
try:
    response = urlopen(request, timeout=1800)
except HTTPError as exc:
    raise RuntimeError(f"Bonsai returned HTTP {exc.code}: "
                       f"{exc.read().decode('utf-8', errors='replace')}") from exc
with response:
    if response.headers.get_content_type() != "text/event-stream":
        raise RuntimeError(f"Expected SSE, got {response.headers.get_content_type()}")
    for line in response:
        if not line.startswith(b"data: "):
            continue
        data = line[6:].strip()
        if data == b"[DONE]":
            break
        event = json.loads(data)
        if "error" in event:
            raise RuntimeError(f"Generation failed: {event['error']}")
        choice = event["choices"][0]
        text = choice["delta"].get("content", "")
        if text:
            first = first or time.perf_counter()
            fragments.append(text)
        if choice["finish_reason"] is not None:
            if choice["finish_reason"] != "stop":
                raise RuntimeError(f"Generation ended with {choice['finish_reason']}")
            finished = True
if not finished or len(fragments) < 2 or not "".join(fragments).strip():
    raise RuntimeError("No complete, incremental answer was received")
print(json.dumps({"model": model, "fragments": len(fragments),
                  "ttft_s": round(first - started, 3),
                  "total_s": round(time.perf_counter() - started, 3),
                  "answer": "".join(fragments)}, ensure_ascii=False))
