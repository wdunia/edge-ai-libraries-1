#!/usr/bin/env python3
"""Measure ChatQnA SSE after a model endpoint is explicitly connected."""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen


def load_questions(path: Path | None) -> list[str]:
    if path is None:
        demo_prompts = Path(__file__).resolve().parents[1] / "local-chat-bot-demo" / "tools" / "prompts.py"
        spec = importlib.util.spec_from_file_location("demo_example_prompts", demo_prompts)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load demo prompts from {demo_prompts}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        questions = list(module.EXAMPLE_PROMPTS)
    else:
        questions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions or not all(
        isinstance(q, str) and q.strip() for q in questions
    ):
        raise ValueError("Questions must be a nonempty list of nonempty strings")
    return questions


def run(url: str, question: str, max_tokens: int) -> dict:
    body = json.dumps({
        "conversation_messages": [{"role": "user", "content": question}],
        "max_tokens": max_tokens,
    }).encode()
    request = Request(url, body, {"Content-Type": "application/json"})
    start = time.perf_counter()
    fragments = []
    first = None
    completed = None
    server_ms = None
    error = None
    with urlopen(request, timeout=600) as response:
        if response.headers.get_content_type() != "text/event-stream":
            raise RuntimeError(f"Expected SSE, got {response.headers.get_content_type()}")
        for raw in response:
            if not raw.startswith(b"data: "):
                continue
            message = raw[6:].decode("utf-8").rstrip("\r\n")
            if not message.strip():
                continue
            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                event = message
            if isinstance(event, dict) and event.get("finished") is True:
                completed = time.perf_counter()
                server_ms = event.get("response_time_ms")
            elif isinstance(event, dict) and "error" in event:
                error = event["error"]
            elif isinstance(event, str):
                fragments.append(event)
                if first is None and event.strip():
                    first = time.perf_counter()
    if error:
        raise RuntimeError(f"ChatQnA streaming error: {error}")
    if completed is None or first is None:
        raise RuntimeError("Missing first fragment or completion marker in SSE response")
    return {
        "answer": "".join(fragments),
        "fragments": len(fragments),
        "ttft_s": round(first - start, 4),
        "total_s": round(completed - start, 4),
        "server_response_ms": server_ms,
        "incremental": len(fragments) >= 2 and first < completed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--questions", type=Path,
                        help="UTF-8 JSON array; default: the demo's exact example prompts")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    if args.warmups < 1 or args.repeats < 5:
        parser.error("Use at least one warmup and five repetitions")
    questions = load_questions(args.questions)
    with urlopen(args.url + "/model", timeout=10) as response:
        model = json.load(response)["llm_model"]
    records = []
    for question_index, question in enumerate(questions):
        for attempt in range(-args.warmups, args.repeats):
            try:
                result = run(args.url + "/chat", question, args.max_tokens)
            except Exception as exc:
                result = {"error": f"{type(exc).__name__}: {exc}"}
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": model,
                "question_index": question_index,
                "question": question,
                "attempt": attempt,
                "warmup": attempt < 0,
                "max_tokens": args.max_tokens,
                **result,
            }
            records.append(record)
            print(f"{model} question={question_index} run={attempt}: {result}", flush=True)
            with args.output.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
    for index in range(len(questions)):
        measured = [r for r in records if r["question_index"] == index
                    and not r["warmup"] and "error" not in r]
        if not measured:
            raise RuntimeError(f"No successful measurements for question {index}; see {args.output}")
        print(f"Question {index}: median TTFT={statistics.median(r['ttft_s'] for r in measured):.3f}s, "
              f"median total={statistics.median(r['total_s'] for r in measured):.3f}s; "
              f"success={len(measured)}/{args.repeats}; "
              f"incremental={sum(r['incremental'] for r in measured)}/{len(measured)}")


if __name__ == "__main__":
    main()
