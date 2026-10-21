import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Queue
import runpy
import subprocess
from threading import Thread
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import benchmark
import prepare
import server
import verify_bonsai


class ExperimentTests(unittest.TestCase):
    def test_experiment_does_not_wire_bonsai_into_default_demo(self):
        demo = Path(__file__).resolve().parents[1] / "local-chat-bot-demo"
        for path in (
            demo / "scripts/run_local_chat_bot.sh",
            demo / "scripts/prepare_workspace.sh",
            demo / "scripts/demo.env",
            demo / "generators/gen_setup_sh.py",
            demo / "docker/docker-compose.demo.yaml",
        ):
            self.assertNotIn("bonsai", path.read_text(encoding="utf-8").lower(), str(path))

    def test_preflight_has_no_gpu_network_or_published_port(self):
        compose = (Path(__file__).parent / "compose.yaml").read_text(encoding="utf-8")
        for entry in ("network_mode: none", "read_only: true", "cap_drop: [ALL]"):
            self.assertIn(entry, compose)
        for entry in ("devices:", "ports:", "privileged:"):
            self.assertNotIn(entry, compose)

    def test_comparison_service_is_separate_and_not_public(self):
        compose = (Path(__file__).parent / "compose.demo.yaml").read_text(encoding="utf-8")
        self.assertIn("bonsai-service:", compose)
        self.assertIn("config_embedding_only.json", compose)
        self.assertIn("ovms-bonsai:8000/v1", compose)
        self.assertNotIn("ports:", compose)

    def test_prepare_changes_only_disposable_prompt_and_embedding_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "app"
            app.mkdir()
            chain = app / "chain.py"
            chain.write_text('template = """\n<|start|>system<|message|>gpt\n"""\n'
                             "OTHER = 42\n            max_tokens=max_tokens\n", encoding="utf-8")
            prepare.prepare_chat(root)
            updated = chain.read_text(encoding="utf-8")
            self.assertIn("OTHER = 42", updated)
            self.assertNotIn("<|start|>", updated)
            self.assertIn("answer from general knowledge", updated)
            self.assertIn("request_timeout=1800", updated)
            source, target = root / "all.json", root / "embedding.json"
            source.write_text('{"model_config_list": [{"name": "gpt-oss-20b"}, '
                              '{"name": "nomic-embed-text-v1.5"}]}', encoding="utf-8")
            prepare.prepare_embedding(source, target, "nomic-ai/nomic-embed-text-v1.5")
            self.assertEqual(len(json.loads(target.read_text())["model_config_list"]), 1)
            ui = root / "ui" / "react"
            ui.mkdir(parents=True)
            env = ui / ".env"
            env.write_text("VITE_MAX_TOKENS=32768\nOTHER=kept\n", encoding="utf-8")
            prepare.prepare_ui(root)
            self.assertEqual(env.read_text(encoding="utf-8"),
                             "VITE_MAX_TOKENS=256\nOTHER=kept\n")
            prepare.prepare_ui(root)
            self.assertEqual(env.read_text(encoding="utf-8"),
                             "VITE_MAX_TOKENS=256\nOTHER=kept\n")

    def test_benchmark_reuses_the_demo_example_prompts(self):
        demo = Path(__file__).resolve().parents[1] / "local-chat-bot-demo" / "tools" / "prompts.py"
        self.assertEqual(
            benchmark.load_questions(None),
            list(runpy.run_path(str(demo))["EXAMPLE_PROMPTS"]),
        )
        self.assertEqual(len(benchmark.load_questions(None)), 5)

    def test_reasoning_does_not_stream_as_visible_answer(self):
        answer = server.VisibleAnswer()
        self.assertEqual([answer.feed(piece) for piece in
                          ("<thi", "nk>private</thi", "nk>Hello", " world")],
                         ["", "", "Hello", " world"])
        answer.finish()
        unfinished = server.VisibleAnswer()
        unfinished.feed("<think>unfinished")
        with self.assertRaises(RuntimeError):
            unfinished.finish()

    def test_bonsai_requires_selected_visible_gpu(self):
        core = SimpleNamespace(available_devices=["CPU", "GPU.0"])
        server.require_gpu(core, "GPU.0")
        for device in ("CPU", "GPU.1"):
            with self.assertRaisesRegex(RuntimeError, "available GPU"):
                server.require_gpu(core, device)
        class UnavailableCore:
            @property
            def available_devices(self):
                raise RuntimeError("plugin failed")
        with self.assertRaisesRegex(RuntimeError, "cannot enumerate OpenVINO devices"):
            server.require_gpu(UnavailableCore(), "GPU.0")

    def test_server_streams_real_chunks_through_openai_endpoint(self):
        class Pipeline:
            def finish_chat(self):
                pass

            def generate(self, prompt, generation_config, streamer):
                self.prompt = prompt
                self.generation_config = generation_config
                streamer("<think>hidden</think>")
                streamer("Hello")
                streamer(" world")
                throughput = SimpleNamespace(mean=12.0)
                metrics = SimpleNamespace(
                    get_num_input_tokens=lambda: 4,
                    get_num_generated_tokens=lambda: 3,
                    get_throughput=lambda: throughput,
                )
                return SimpleNamespace(perf_metrics=metrics)

        pipeline = Pipeline()
        tokenizer = SimpleNamespace(apply_chat_template=lambda *args, **kwargs: "prompt")
        runtime = SimpleNamespace(result_text=lambda *args: "Hello world")
        genai = SimpleNamespace(GenerationConfig=lambda: SimpleNamespace())
        ready = Queue()
        worker = Thread(target=server.serve, args=(
            pipeline, tokenizer, runtime, genai, "test-model", "127.0.0.1", 0, ready.put
        ))
        worker.start()
        httpd = ready.get(timeout=5)
        try:
            body = json.dumps({"model": "test-model", "stream": True,
                               "messages": [{"role": "user", "content": "Question?"}]}).encode()
            request = Request(f"http://127.0.0.1:{httpd.server_port}/v1/chat/completions",
                              body, {"Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                events = [line[6:].strip() for line in response if line.startswith(b"data: ")]
            self.assertEqual(events[-1], b"[DONE]")
            self.assertEqual(pipeline.generation_config.max_new_tokens, 1280)
            chunks = [json.loads(event) for event in events[:-1]]
            self.assertEqual([chunk["choices"][0]["delta"].get("content") for chunk in chunks],
                             ["Hello", " world", None])
            self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "stop")
        finally:
            httpd.shutdown()
            httpd.server_close()
            worker.join(timeout=5)

    def test_manifest_verification_fails_for_modified_or_extra_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                verify_bonsai.PLUGIN_FILE: b"plugin",
                verify_bonsai.RUNTIME_FILES["bonsai-1bit"]: b"runtime",
                "runtime/install_plugin.py": b"installer",
                "openvino_language_model.xml": b"model xml",
                "openvino_language_model.bin": b"model weights",
            }
            lines = []
            for name, data in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                lines.append(f"{hashlib.sha256(data).hexdigest()}  ./{name}")
            (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest_hash = verify_bonsai.sha256(root / "CHECKSUMS.sha256")
            with patch.dict(verify_bonsai.MANIFEST_SHA256, {"bonsai-1bit": manifest_hash}), \
                 patch.dict(verify_bonsai.PLUGIN_SHA256, {
                     "bonsai-1bit": hashlib.sha256(b"plugin").hexdigest()
                 }):
                verify_bonsai.verify(root, "bonsai-1bit")
                (root / "openvino_language_model.bin").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "modified"):
                    verify_bonsai.verify(root, "bonsai-1bit")
                (root / "openvino_language_model.bin").write_bytes(b"model weights")
                (root / "runtime" / "unlisted.py").write_bytes(b"extra")
                with self.assertRaisesRegex(ValueError, "Unlisted"):
                    verify_bonsai.verify(root, "bonsai-1bit")

    def test_pinned_repository_readme_is_the_only_manifest_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                verify_bonsai.PLUGIN_FILE: b"plugin",
                verify_bonsai.RUNTIME_FILES["bonsai-1bit"]: b"runtime",
                "runtime/install_plugin.py": b"installer",
                "openvino_language_model.xml": b"model xml",
                "openvino_language_model.bin": b"model weights",
                "README.md": b"repository readme",
            }
            for name, data in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            lines = [
                f"{hashlib.sha256(data if name != 'README.md' else b'stale readme').hexdigest()}  ./{name}"
                for name, data in files.items()
            ]
            (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
            with patch.dict(verify_bonsai.MANIFEST_SHA256, {
                "bonsai-1bit": verify_bonsai.sha256(root / "CHECKSUMS.sha256")
            }), patch.dict(verify_bonsai.PLUGIN_SHA256, {
                "bonsai-1bit": hashlib.sha256(b"plugin").hexdigest()
            }), patch.dict(verify_bonsai.README_SHA256, {
                "bonsai-1bit": hashlib.sha256(b"repository readme").hexdigest()
            }):
                verify_bonsai.verify(root, "bonsai-1bit")
                (root / "README.md").write_bytes(b"tampered readme")
                with self.assertRaisesRegex(ValueError, "README.md"):
                    verify_bonsai.verify(root, "bonsai-1bit")
                (root / "README.md").write_bytes(b"repository readme")
                (root / "openvino_language_model.bin").write_bytes(b"tampered weights")
                with self.assertRaisesRegex(ValueError, "openvino_language_model.bin"):
                    verify_bonsai.verify(root, "bonsai-1bit")

    def test_quick_comparison_records_answers_and_reasoning_failure(self):
        class Handler(BaseHTTPRequestHandler):
            model = "Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc"
            token_limits = []

            def do_GET(self):
                body = json.dumps({"llm_model": self.model}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.token_limits.append(request["max_tokens"])
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if request["conversation_messages"][0]["content"].startswith("Count from"):
                    events = ['data: {"error": "Generation stopped inside reasoning"}\n\n']
                else:
                    events = ["data: Hello\n\n", "data:  world\n\n",
                              'data: {"finished": true, "response_time_ms": 25}\n\n']
                for event in events:
                    self.wfile.write(event.encode())
                    self.wfile.flush()
                self.close_connection = True

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            script = (Path(__file__).parent / "quick_compare.sh").read_text(encoding="utf-8")
            code = script.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "quick.jsonl"
                env = {**os.environ, "CHATQNA_URL": f"http://127.0.0.1:{server.server_port}",
                       "QUICK_RESULTS": str(output)}
                for model in (Handler.model, "OpenVINO/gpt-oss-20b-int4-ov"):
                    Handler.model = model
                    result = subprocess.run(
                        [os.sys.executable, "-B", "-c", code], env=env,
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(f"ChatQnA model: {model}", result.stdout)
                    self.assertIn("reasoning_limit: TTFT=n/a", result.stdout)
                self.assertIn("OpenVINO/gpt-oss-20b-int4-ov | greeting", result.stdout)
                self.assertIn("Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc | greeting",
                              result.stdout)
                records = [json.loads(line) for line in output.read_text().splitlines()]
                self.assertEqual(len(records), 6)
                self.assertEqual(Handler.token_limits, [1024] * 6)
                for index in (0, 3):
                    self.assertEqual(records[index]["max_tokens"], 1024)
                    self.assertEqual(records[index]["answer"], "Hello world")
                    self.assertIsNotNone(records[index]["ttft_s"])
                    self.assertIsNotNone(records[index]["total_s"])
                    self.assertEqual(records[index]["fragments"], 2)
                    self.assertEqual(records[index]["server_response_ms"], 25)
                    self.assertTrue(records[index]["incremental"])
                    self.assertIsNone(records[index]["error"])
                    self.assertEqual(records[index + 2]["prompt_id"], "reasoning_limit")
                    self.assertIn("Generation stopped inside reasoning",
                                  records[index + 2]["error"])
                    self.assertIsNone(records[index + 2]["ttft_s"])
                self.assertNotEqual(records[0]["model"], records[3]["model"])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_benchmark_requires_incremental_sse(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for event in ("data: First\n\n", "data:  second\n\n",
                              'data: {"finished": true, "response_time_ms": 30}\n\n'):
                    self.wfile.write(event.encode())
                    self.wfile.flush()
                    time.sleep(0.01)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            result = benchmark.run(f"http://127.0.0.1:{server.server_port}/chat", "Question?", 64)
            self.assertEqual(result["answer"], "First second")
            self.assertTrue(result["incremental"])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == "__main__":
    unittest.main()
