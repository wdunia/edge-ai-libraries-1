#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

url = os.environ.get("CHATQNA_URL", "http://127.0.0.1:8100").rstrip("/")
output = Path(os.environ.get("QUICK_RESULTS", "results/quick-comparison.jsonl"))
prompts = [
    ("greeting", "Hi"),
    ("packed_weights", "Answer directly without a thinking section or reasoning. "
     "In one sentence, explain why packed weights use less memory."),
    ("reasoning_limit", "Count from 1 to 50 in the format 1-one, 2-two and so on"),
]
model_response = subprocess.run(
    ["curl", "-fsS", "--max-time", "10", url + "/model"],
    check=True, capture_output=True, text=True,
)
model = json.loads(model_response.stdout)["llm_model"]
print(f"ChatQnA model: {model}", flush=True)
output.parent.mkdir(parents=True, exist_ok=True)

failed = False
for name, prompt in prompts:
    payload = json.dumps({
        "conversation_messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
    })
    command = [
        "curl", "-N", "-sS", "--max-time", "1800",
        "-w", "\n__HTTP_STATUS__:%{http_code}\n",
        url + "/chat", "-H", "Content-Type: application/json", "-d", payload,
    ]
    start = time.monotonic()
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, bufsize=1) as process:
        fragments = []
        first = completed = server_ms = http_status = error = None
        other_body = []
        for line in process.stdout:
            if line.startswith("__HTTP_STATUS__:"):
                http_status = int(line.split(":", 1)[1])
            elif line.startswith("data: "):
                message = line[6:].rstrip("\r\n")
                if not message.strip():
                    continue
                try:
                    event = json.loads(message)
                except json.JSONDecodeError:
                    event = message
                if isinstance(event, dict) and event.get("finished") is True:
                    completed = time.monotonic()
                    server_ms = event.get("response_time_ms")
                elif isinstance(event, dict) and "error" in event:
                    error = str(event["error"])
                elif isinstance(event, str):
                    fragments.append(event)
                    if first is None and event.strip():
                        first = time.monotonic()
            elif line.strip() and len(other_body) < 8:
                other_body.append(line.strip())
        stderr = process.stderr.read().strip()
        exit_code = process.wait()
    end = time.monotonic()
    if exit_code:
        error = f"curl exit {exit_code}: {stderr}" + (f"; {error}" if error else "")
    elif http_status != 200:
        error = f"HTTP {http_status}: {' '.join(other_body)}" + (f"; {error}" if error else "")
    elif error is None and completed is None:
        error = "ChatQnA response ended without a completion event"
    elif error is None and first is None:
        error = "ChatQnA returned no visible answer"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model, "prompt_id": name, "prompt": prompt, "max_tokens": 256,
        "http_status": http_status, "ttft_s": round(first - start, 3) if first else None,
        "total_s": round((completed or end) - start, 3),
        "server_response_ms": server_ms, "fragments": len(fragments),
        "incremental": len(fragments) >= 2 and first is not None and completed is not None,
        "answer": "".join(fragments), "error": error,
    }
    with output.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    ttft = f"{record['ttft_s']}s" if record["ttft_s"] is not None else "n/a"
    print(f"{name}: TTFT={ttft} total={record['total_s']}s "
          f"server={server_ms}ms fragments={record['fragments']} "
          f"incremental={record['incremental']} HTTP={http_status} "
          f"error={error or '-'}", flush=True)
    failed |= error is not None

print(f"Full answers and measurements: {output}")
latest = {}
for line in output.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    latest[(row["model"], row["prompt_id"])] = row
print("Latest saved measurements by model and prompt:")
for row in latest.values():
    ttft = f"{row['ttft_s']}s" if row["ttft_s"] is not None else "n/a"
    print(f"  {row['model']} | {row['prompt_id']} | TTFT={ttft} "
          f"total={row['total_s']}s | {'ERROR' if row['error'] else 'OK'}")
print("Compare matching prompt_id rows for the two models; a single run per model "
      "is an exploratory observation, not a benchmark.")
sys.exit(1 if failed else 0)
PY
