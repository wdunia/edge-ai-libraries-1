import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from queue import Queue
import runpy
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
                             "OTHER = 42\n", encoding="utf-8")
            prepare.prepare_chat(root)
            updated = chain.read_text(encoding="utf-8")
            self.assertIn("OTHER = 42", updated)
            self.assertNotIn("<|start|>", updated)
            self.assertIn("answer from general knowledge", updated)
            source, target = root / "all.json", root / "embedding.json"
            source.write_text('{"model_config_list": [{"name": "gpt-oss-20b"}, '
                              '{"name": "nomic-embed-text-v1.5"}]}', encoding="utf-8")
            prepare.prepare_embedding(source, target, "nomic-ai/nomic-embed-text-v1.5")
            self.assertEqual(len(json.loads(target.read_text())["model_config_list"]), 1)

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

    def test_server_streams_real_chunks_through_openai_endpoint(self):
        class Pipeline:
            def finish_chat(self):
                pass

            def generate(self, prompt, generation_config, streamer):
                self.prompt = prompt
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
