# Local Chat Bot demo

Standalone demo built **on top of** the ChatQnA sample application
(`sample-applications/chat-question-and-answer`).

The sample application is never modified. On every run it is copied into
`.work/chat-question-and-answer` and the demo delta is applied there:

| Layer         | What it contains                                        | Why |
|---------------|---------------------------------------------------------|-----|
| `overlay/`    | full demo-owned files (metrics UI, navbar, chat styling) | new or fully rewritten files |
| `patches/`    | `git apply --3way` diffs (`server.py`, `chain.py`, …)    | files the upstream keeps evolving |
| `generators/` | idempotent tweaks (`setup.sh`, Dockerfiles, `.env`, deps) | survive upstream changes without conflicts |
| `docker/`     | compose override (demo image tags, `HOST_IP`, metrics URL) | no edits to `docker-compose.yaml` |

## Quick start (Linux)

```bash
cd sample-applications/local-chat-bot-demo
chmod +x scripts/*.sh generators/*.sh
./scripts/run_local_chat_bot.sh --force-restart
```

You will be asked for a Hugging Face token
([how to get one](https://huggingface.co/docs/hub/security-tokens)) and a target
device (`CPU` or `GPU`; NPU is not supported by the sample application).

When it is up:

- UI: <http://localhost:8101>
- Backend health: <http://localhost:8100/health>

The first run downloads and converts a 20B model - expect up to ~20 minutes
before the health check passes. Converted models are cached in `.cache/ovms`
**outside** the working copy, so every later start (including `--clean`) reuses
them.

Everything runs as background Docker containers:

```bash
./scripts/logs.sh                  # follow the ChatQnA stack
./scripts/logs.sh model-download   # follow a supporting container
./scripts/stop_local_chat_bot.sh   # stop the demo, keep the models
```

<details>
<summary>Options</summary>

```bash
./scripts/run_local_chat_bot.sh \
  --device GPU \            # skip the device prompt
  --hf-token <token> \      # skip the token prompt
  --no-restart \            # keep running containers (default: restart them)
  --clean \                 # rebuild the working copy (models are kept)
  --strict \                # fail when upstream drifted from the baseline
  --skip-install \          # do not touch host packages
  --skip-prepare \          # reuse the working copy as-is
  --no-autorun              # do not start the prompt submission CLI
```

Defaults live in [`scripts/demo.env`](scripts/demo.env) and can be overridden by
exporting the matching variable (models, images, ports, `MAX_WAIT_SECONDS`,
`SYSTEM_INFO_TEXT`, `OVMS_MODELS_DIR`, `MODEL_DOWNLOAD_*`, …).

</details>

<details>
<summary>Restarting after a timeout</summary>

A timeout only means the health check gave up - nothing is lost. Just run the
demo again:

```bash
./scripts/run_local_chat_bot.sh --device GPU --hf-token <token>
```

The launcher stops leftover containers and reuses:

- `.cache/ovms` - converted OVMS models (skipped by the patched `setup.sh`)
- `$HOME/host_path` - model-download working directory
- `.work/chat-question-and-answer` - the prepared working copy

Only `./scripts/stop_local_chat_bot.sh --purge-models` deletes the model cache.

</details>

<details>
<summary>Scripts</summary>

| Script | Purpose |
|--------|---------|
| `scripts/install_prereqs.sh`   | Docker, Chrome, base packages (conditional) |
| `scripts/prepare_workspace.sh` | build the working copy: copy → overlay → patches → generators |
| `scripts/build_demo_images.sh` | build `local-chat-bot-be:local` and `local-chat-bot-ui:local` |
| `scripts/run_local_chat_bot.sh`| full demo launch (metrics-manager, model-download, stack, autorun) |
| `scripts/stop_local_chat_bot.sh`| stop the demo (`--purge-models` to drop the cache) |
| `scripts/logs.sh`              | follow stack or container logs |
| `scripts/make_patches.sh`      | regenerate `patches/`, `overlay/`, `overlay/MANIFEST.sha256` |

</details>

<details>
<summary>Changing the demo</summary>

```bash
./scripts/prepare_workspace.sh --clean
# edit files inside .work/chat-question-and-answer
git -C .work/chat-question-and-answer diff HEAD   # review the demo delta
./scripts/make_patches.sh --refresh-overlay --refresh-manifest
```

`make_patches.sh` also reports working-copy changes that are not covered by
`patches/`, `overlay/` or `generators/`, so nothing can silently drift back into
the sample application.

</details>

<details>
<summary>Upstream updates</summary>

`scripts/demo.env` pins `UPSTREAM_REF` - the baseline the patches and the
overlay manifest were generated from.

- A patch that no longer applies stops `prepare_workspace.sh` with a clear error.
- An overlay file whose baseline changed produces a drift warning (`--strict`
  turns it into an error).

Both cases are fixed the same way: refresh the working copy, redo the change,
run `make_patches.sh`. The sample application itself is never edited, so merging
upstream updates into this branch does not create conflicts.

</details>

<details>
<summary>Troubleshooting</summary>

- Logs: `./scripts/logs.sh`, `./scripts/logs.sh model-download`,
  `./scripts/logs.sh metrics-manager`
- Container overview: `docker ps -a --filter label=com.docker.compose.project=local-chat-bot`
- Slow network or a busy machine may need a longer timeout:
  `export MAX_WAIT_SECONDS=3600`
- Model conversion may fail on low-memory hosts; increase swap and re-run
  (already converted models are reused from `.cache/ovms`).
- The prompt submission tool opens two browser windows and requires an Xorg
  (X11) session - check with `echo "$XDG_SESSION_TYPE"`; if it prints `wayland`,
  log out and pick **Ubuntu on Xorg** (gear icon on the login screen).
- The tool types into ChatGPT only when that window is logged in and the
  composer is visible. If it reports `ChatGPT prompt box not found`, log in in
  the opened window and resend the prompt; the local chatbot is unaffected
  because both submissions are independent.
- The demo does not configure proxies or firewall rules on the host.

</details>

<details>
<summary>Not covered by this demo</summary>

The Helm chart of the sample application is out of scope - the demo runs on
Docker Compose only.

</details>


