# Bonsai model comparison experiment

This is an **opt-in comparison using the actual ChatQnA UI**, separate from
the default [`local-chat-bot-demo`](../local-chat-bot-demo/). Its launcher
and Compose remain unchanged and still use gpt-oss. The experiment makes
its own disposable working copy, replaces the gpt-specific prompt there,
loads only the OVMS embedding model, and connects the app to a separate
Bonsai OpenVINO GenAI streaming service. The Wondernutts builds are
experimental third-party artifacts, not Intel-certified products. They
have **not yet been tested here on Intel Arc B390**.

There are three different checks: `verify_bonsai.py` checks file integrity,
`smoke.py` generates a real answer directly from Bonsai and checks streaming,
and `benchmark.py` records answers from the **same ChatQnA application** for
comparison. Integrity verification is not an evaluation of model quality.

## Files in this experiment

| File | Purpose |
| --- | --- |
| [`compose.yaml`](compose.yaml) | Offline, read-only artifact verification (no GPU or published ports) |
| [`compose.demo.yaml`](compose.demo.yaml), [`Dockerfile`](Dockerfile) | Opt-in Bonsai service and demo override; no change to default Compose |
| [`run.sh`](run.sh), [`stop.sh`](stop.sh), [`prepare.py`](prepare.py) | Build the isolated app copy, switch OVMS to embeddings only, start/stop one model |
| [`server.py`](server.py), [`smoke.py`](smoke.py) | Stream real model responses; require incremental output in a container-local smoke test |
| [`verify_bonsai.py`](verify_bonsai.py) | Check publisher checksums before any model code is executed |
| [`benchmark.py`](benchmark.py) | Repeats the demo's exact example prompts against the ChatQnA SSE endpoint |
| [`test_experiment.py`](test_experiment.py) | Tests that do not require the target GPU |
| [`.gitignore`](.gitignore) | Excludes downloads, working copies, caches and results |

The published model files, including `runtime/*.py`, the GPU plugin `.so`,
the graph and `CHECKSUMS.sha256`, are downloaded into the ignored `models/`
directory; none are checked into this repository. `verify_bonsai` is our
module, not a package supplied by OpenVINO or the model publisher.

## Run and test (Linux / Arc B390)

Work on a dedicated test machine without secrets or private documents. Run
these commands from this directory. Docker Compose, Python 3 and the
Python `venv` module must already be installed. Step 2 installs the Hugging
Face `hf` CLI locally in an ignored virtual environment.

1. **Prepare the existing gpt-oss baseline**, and make sure both the gpt-oss
   and embedding OVMS models are cached in the demo's `.cache/ovms`.
   Otherwise its launcher asks for a Hugging Face token: prepare the cache
   on a separate machine if the test machine must remain free of secrets.

   ```bash
   cd ../local-chat-bot-demo
   ./scripts/run_local_chat_bot.sh --device GPU --no-autorun
   # Check the UI at http://localhost:8101 and record a baseline response.
   ./scripts/stop_local_chat_bot.sh
   cd ../local-chat-bot-bonsai-experiment
   ```

2. **Download the exact published builds** (1-bit first, then ternary).
   Allow enough free disk space. Avoid credentials for these public
   repositories. Create a dedicated virtual environment and use an isolated
   Hugging Face home so a login cached on the host is not used. On Debian or
   Ubuntu, install `python3-venv` first if `python3 -m venv` is unavailable.

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install huggingface_hub
   .venv/bin/hf --help
   unset HF_TOKEN HUGGINGFACEHUB_API_TOKEN
   export HF_HOME="$PWD/.cache/hf-home"
   .venv/bin/hf download Wondernutts/Bonsai-27B-INTBIT-OpenVINO-Arc \
     --revision 0f1c8234ef1c874f62a8d88df9b9a8b26e3c911c \
     --local-dir models/bonsai-1bit
   .venv/bin/hf download Wondernutts/Bonsai-27B-INTERNARY-OpenVINO-Arc \
     --revision 3a9e2f4ddcff5af2b370451b9a04e2117ef94c2a \
     --local-dir models/bonsai-ternary
   ```

   Later steps use system `python3` for standard-library-only scripts; the
   virtual environment is needed only for `hf` and need not be activated.

3. **Verify each download without running the models**. These jobs have
   no network, GPU device or published ports. A checksum failure stops
   verification; do not bypass it.

   ```bash
   BONSAI_MODEL_DIR="$PWD/models/bonsai-1bit" BONSAI_VARIANT=bonsai-1bit \
     docker compose -f compose.yaml run --rm verify
   BONSAI_MODEL_DIR="$PWD/models/bonsai-ternary" BONSAI_VARIANT=bonsai-ternary \
     docker compose -f compose.yaml run --rm verify
   python3 -m unittest discover -s . -p 'test_experiment.py'
   ```

   Without Docker, use `python3 verify_bonsai.py models/bonsai-1bit bonsai-1bit`
   and the corresponding command with `models/bonsai-ternary bonsai-ternary`.
   The publisher's pinned `CHECKSUMS.sha256` does not match the `README.md`
   served at either pinned repository revision. The verifier checks that
   document against its separately pinned repository hash; it still requires
   every model file, runtime script and GPU plugin to match the manifest.
   Any other missing or modified file is a failure: inspect the path reported
   by the error instead of bypassing verification. These publisher-sourced
   hashes are not an independent security audit of the native plugin.

4. **Start the 1-bit model and request a real streamed answer.** Run the
   experiment on a disposable Linux machine with GPU drivers, Docker and
   the demo prerequisites already installed. The script starts the demo in
   a *separate working copy*, stops its gpt-oss OVMS process, creates an
   embedding-only OVMS config, then starts Bonsai and reconnects ChatQnA.
   The experiment sets the UI answer limit to 256 tokens in its disposable
   copy. This first launch also builds the container image and compiles the model.
   The Bonsai image installs pinned Intel OpenCL and Level Zero userspace
   release packages from GitHub, verifying their SHA-256 hashes before
   installation **inside the container only**; the Intel graphics APT
   repository may deny access to its package index. This does not install
   a host GPU driver or a host OpenVINO plugin. The
   publisher validated compute runtime 26.22 on B70; this container uses
   official Intel release 26.27, which is not that validated configuration
   and does not establish compatibility with B390.

   ```bash
   unset HF_TOKEN HUGGINGFACEHUB_API_TOKEN
   export BONSAI_GPU_DEVICE=GPU.0  # choose the correct GPU ID for your machine
   bash run.sh bonsai-1bit
   docker exec bonsai-service python /opt/bonsai/smoke.py
   # Open http://localhost:8101, ask a question, observe incremental text.
   ```

   A successful smoke test prints the actual generated answer and requires
   **at least two content fragments before completion**. The model can spend
   substantial time generating hidden reasoning even with thinking disabled
   in the chat template. Following the publisher's guidance, the experiment
   allows up to 1024 extra reasoning tokens; the disposable ChatQnA client
   allows up to 30 minutes before timing out as well. The smoke test waits
   up to 30 minutes and reports the server's error body if generation fails. A ready
   server alone does not prove it can produce an answer. Verify the response
   in the UI as well. Failure to load on B390, a failed smoke test or a
   stalled UI is a feasibility failure, **not a benchmark result**. The
   launcher now fails immediately with Bonsai logs if that container exits.
   The logs list GPUs visible to OpenVINO and the selected `BONSAI_GPU_DEVICE`;
   if that device is absent, choose a reported GPU ID and retry. If the
   correct device is visible but pipeline creation still fails, do not assume
   that installing the plugin on the host will fix it. Inspect
   `docker logs bonsai-service` and the demo logs. `server.py` copies the
   verified native plugin **only into the newly built container's own
   OpenVINO installation**; it does not modify the host's OpenVINO package
   or other system files. The publisher's non-streaming example server and
   plugin installer are not used.

5. **Measure answers, then repeat for ternary.** No document upload is
   required. By default, `benchmark.py` reads the same five prompts used by
   the demo's Example prompts control from
   [`../local-chat-bot-demo/tools/prompts.py`](../local-chat-bot-demo/tools/prompts.py):
   prime-number steps, a Python string-reversal function, TCP versus UDP,
   train speed and the river-crossing puzzle. Each repetition is a fresh
   one-question conversation sent to the same ChatQnA `/chat` endpoint.
   Use the same token limit and repeat count for every model.

   ```bash
   mkdir -p results
   python3 benchmark.py \
     --output results/bonsai-1bit.jsonl --warmups 1 --repeats 5 --max-tokens 256
   bash stop.sh
   bash run.sh bonsai-ternary
   docker exec bonsai-service python /opt/bonsai/smoke.py
   python3 benchmark.py \
     --output results/bonsai-ternary.jsonl --warmups 1 --repeats 5 --max-tokens 256
   bash stop.sh
   ```

   Re-run the unchanged demo for the gpt-oss baseline and measure the same
   five prompts without uploading documents:

   ```bash
   cd ../local-chat-bot-demo
   ./scripts/run_local_chat_bot.sh --device GPU --no-autorun
   cd ../local-chat-bot-bonsai-experiment
   python3 benchmark.py \
     --output results/gpt-oss.jsonl --warmups 1 --repeats 5 --max-tokens 256
   cd ../local-chat-bot-demo
   ./scripts/stop_local_chat_bot.sh
   ```

   To use a different fixed set later, pass `--questions your-questions.json`
   (a JSON array of strings) for **every** model. `benchmark.py` records the full answers, time
   to first fragment, total time, errors and whether streaming was
   incremental. Container logs include Bonsai token counts and throughput.
   Report medians and variability; five repetitions are insufficient for a
   meaningful p95. The default demo's gpt-oss prompt and the experiment's
   neutral Bonsai prompt are not identical system instructions, which must
   be noted when judging answer quality.

**Important limits:** The target GPU driver and custom plugin have not been
validated on B390. The container's Intel GPU userspace runtime may need
adaptation to the installed host driver; do not claim success until the
model loads and the smoke and UI tests pass. Default demo services publish
host ports, so run on an isolated machine with inbound access blocked.
Native GPU code inside a container is not a complete security boundary.
Publisher checksums do not establish independent safety or reproducibility.

These builds are packed 1-bit and ternary OpenVINO representations. A future
conversion from the Prism ML source model, or a regular INT4 conversion,
would be a different experiment.
