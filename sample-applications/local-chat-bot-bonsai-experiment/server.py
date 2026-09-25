#!/usr/bin/env python3
"""Internal streaming endpoint for a verified Bonsai artifact in a disposable container."""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Queue
import shutil
import sys
import time

from verify_bonsai import PLUGIN_FILE, PLUGIN_SHA256, sha256, verify

MODELS = {
    "bonsai-1bit": ("intbit_runtime", "Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc"),
    "bonsai-ternary": ("internary_runtime", "Wondernutts/Bonsai-27B-INTERNARY-OpenVINO-Arc"),
}


class VisibleAnswer:
    def __init__(self):
        self.pending = ""
        self.reasoning = False
        self.decided = False
        self.emitted = False

    def feed(self, fragment: str) -> str:
        self.pending += fragment
        if not self.decided:
            prefix = self.pending.lstrip().lower()
            markers = ("<think>", "here's a thinking process:", "here is a thinking process:")
            if not prefix or any(marker.startswith(prefix) for marker in markers):
                return ""
            self.reasoning = prefix.startswith(markers)
            self.decided = True
        if self.reasoning:
            if "</think>" not in self.pending:
                return ""
            self.pending = self.pending.rsplit("</think>", 1)[1]
            self.reasoning = False
        output, self.pending = self.pending, ""
        self.emitted |= bool(output.strip())
        return output

    def finish(self) -> None:
        if self.reasoning or not self.emitted:
            raise RuntimeError("Bonsai did not complete a visible answer")


def serve(pipeline, tokenizer, runtime, genai, model_name: str,
          host: str = "0.0.0.0", port: int = 8000, ready=None) -> None:
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bonsai-gpu")

    def generate(request: dict, events: Queue) -> None:
        try:
            messages = request["messages"]
            if not isinstance(messages, list) or not messages:
                raise ValueError("messages must be a nonempty list")
            prompt = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True,
                extra_context={"enable_thinking": False},
            )
            config = genai.GenerationConfig()
            answer_tokens = int(request.get("max_tokens") or 256)
            if not 1 <= answer_tokens <= 32768:
                raise ValueError("max_tokens must be between 1 and 32768")
            config.max_new_tokens = answer_tokens + 256
            temperature = float(request.get("temperature", 0.7))
            config.do_sample = temperature > 0
            if config.do_sample:
                config.temperature = temperature
                config.top_p = float(request.get("top_p", 0.95))
                config.top_k = 20
            answer = VisibleAnswer()

            def stream(fragment: str) -> bool:
                visible = answer.feed(fragment)
                if visible:
                    events.put(("text", visible))
                return False

            pipeline.finish_chat()
            result = pipeline.generate(prompt, generation_config=config, streamer=stream)
            pipeline.finish_chat()
            runtime.result_text(result, tokenizer)
            answer.finish()
            metrics = result.perf_metrics
            finish_reason = ("length" if metrics.get_num_generated_tokens() >= config.max_new_tokens
                             else "stop")
            events.put(("done", (metrics, finish_reason)))
        except Exception as exc:
            print(f"Generation failed: {exc}", file=sys.stderr, flush=True)
            events.put(("error", str(exc)))

    class Handler(BaseHTTPRequestHandler):
        def json_response(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/v2/health/ready":
                self.json_response({"status": "ready"})
            elif self.path == "/v1/models":
                self.json_response({"object": "list", "data": [{"id": model_name, "object": "model"}]})
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 1024 * 1024:
                    raise ValueError("Request body must be smaller than 1 MiB")
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("Request must be a JSON object")
                if request.get("model") != model_name or request.get("stream") is not True:
                    raise ValueError(f"Expected stream=true and model={model_name}")
            except (ValueError, TypeError) as exc:
                self.json_response({"error": {"message": str(exc)}}, 400)
                return
            events: Queue = Queue()
            worker.submit(generate, request, events)
            first = events.get()
            if first[0] == "error":
                self.json_response({"error": {"message": first[1]}}, 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            response_id = f"chatcmpl-{time.time_ns()}"

            def send(value: dict | str) -> None:
                body = value if isinstance(value, str) else json.dumps(value)
                self.wfile.write(f"data: {body}\n\n".encode())
                self.wfile.flush()

            event = first
            while True:
                kind, value = event
                if kind == "error":
                    send({"error": {"message": value}})
                    return
                send({"id": response_id, "object": "chat.completion.chunk", "model": model_name,
                      "choices": [{"index": 0, "delta": {"content": value} if kind == "text" else {},
                                   "finish_reason": value[1] if kind == "done" else None}]})
                if kind == "done":
                    metrics = value[0]
                    print(json.dumps({
                        "model": model_name,
                        "input_tokens": int(metrics.get_num_input_tokens()),
                        "generated_tokens": int(metrics.get_num_generated_tokens()),
                        "decode_tps": metrics.get_throughput().mean,
                        "finish_reason": value[1],
                    }), flush=True)
                    send("[DONE]")
                    return
                event = events.get()

    httpd = ThreadingHTTPServer((host, port), Handler)
    if ready is not None:
        ready(httpd)
    httpd.serve_forever()


def main() -> None:
    variant = os.environ["BONSAI_VARIANT"]
    if variant not in MODELS:
        raise ValueError(f"Unsupported Bonsai variant: {variant}")
    verify(Path("/model"), variant)
    import openvino as ov

    if not ov.get_version().startswith("2026.2."):
        raise RuntimeError(f"OpenVINO 2026.2 required; found {ov.get_version()}")
    plugin = Path("/model") / PLUGIN_FILE
    installed = Path(ov.__file__).resolve().parent / "libs" / plugin.name
    isolated_env = Path("/opt/bonsai-venv")
    if Path(sys.prefix).resolve() != isolated_env or isolated_env not in installed.parents:
        raise RuntimeError("Refusing to change any OpenVINO installation outside the isolated container venv")
    if not installed.is_file():
        raise FileNotFoundError(installed)
    shutil.copyfile(plugin, installed)
    if sha256(installed) != PLUGIN_SHA256[variant]:
        raise RuntimeError("Container-local plugin checksum mismatch")

    import openvino_genai as genai
    runtime_name, model_name = MODELS[variant]
    sys.path.insert(0, "/model/runtime")
    runtime = __import__(runtime_name)
    pipeline = runtime.create_pipeline("/model", os.environ["BONSAI_GPU_DEVICE"], "/cache")
    serve(pipeline, pipeline.get_tokenizer(), runtime, genai, model_name)


if __name__ == "__main__":
    main()
