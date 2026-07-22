# DL Streamer Multiplication Demo

Standalone demo for launching multiple DL Streamer pipelines from one UI and
comparing their behavior on CPU, GPU, and NPU.

## ⏱️ Before you start

- **Time needed:** a few steps; first-time setup duration depends on package downloads and Docker image builds
- **Main flow:** **3 steps**
- **One-time setup:** run once per machine

## ✅ Prerequisites

- Linux host
- this repository checked out with
  `microservices/dlstreamer-pipeline-server/resources` available
- support for the device(s) you want to test: CPU, GPU, NPU

> `scripts/install_dlStreamer.sh` installs the usual host-side dependencies
> automatically, so in the normal flow you usually do not need extra manual
> setup.

## 🚀 Quick start

### 1️⃣ Clone only the folders needed for this demo

```bash
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-libraries.git edge-ai-libraries
cd edge-ai-libraries
git sparse-checkout set \
  sample-applications/dlstreamer-multiplication-demo \
  microservices/dlstreamer-pipeline-server/resources
cd sample-applications/dlstreamer-multiplication-demo
chmod +x scripts/*.sh
```

### 2️⃣ Run one-time setup

```bash
./scripts/install_dlStreamer.sh
```

Run this once per machine, or again only if you want to refresh the local setup.

### 3️⃣ Start the demo

```bash
./scripts/run_dlStreamer.sh
```

When the stack is ready:

- the browser should open automatically
- UI: http://localhost:8101

---

<details>
<summary>⚙️ What the scripts do automatically</summary>

`./scripts/install_dlStreamer.sh`:

- installs/configures the typical host dependencies,
- prepares Docker access,
- builds the local demo images once.

`./scripts/run_dlStreamer.sh`:

- creates `docker/.env` on first run,
- fills runtime values automatically,
- rebuilds demo images only if they are missing,
- restarts existing demo containers by default,
- opens the browser automatically by default.

This means you normally do **not** need to run `--force-restart` or
`./scripts/build_demo_images.sh` manually.

</details>

<details>
<summary>🔧 Common launcher options</summary>

```bash
./scripts/run_dlStreamer.sh --no-open-browser
./scripts/run_dlStreamer.sh --source-mode rtsp
./scripts/run_dlStreamer.sh --compose-down
./scripts/run_dlStreamer.sh --no-force-restart
./scripts/run_dlStreamer.sh --system-info-text "CPU/GPU/NPU telemetry"
```

- `--no-open-browser` disables automatic browser launch
- `--source-mode file|rtsp` selects the default source in the UI
- `--compose-down` runs `docker compose down --remove-orphans` first
- `--no-force-restart` skips the default restart step
- `--system-info-text <text>` changes the header text in the UI

</details>

<details>
<summary>⚠️ If something is missing or you skip the install script</summary>

If you do not use `scripts/install_dlStreamer.sh`, make sure at least these are
already available:

- `docker`
- `curl`
- `python3`

The install script is intended for Ubuntu/Debian-like systems and uses tools
such as `apt`, `dpkg`, and `sudo`.

</details>

<details>
<summary>🐛 Troubleshooting</summary>

- View logs:

  ```bash
  docker compose --env-file docker/.env -f docker/docker-compose.images.yml logs -f
  ```

- If startup takes longer than 10 minutes:

  ```bash
  export MAX_WAIT_SECONDS=3600
  ./scripts/run_dlStreamer.sh
  ```

- If automatic browser opening does not work, make sure you are using an Xorg
  (X11) session rather than Wayland.

- If `install_dlStreamer.sh` added your user to the `docker` or `video` group,
  log out and back in before starting the demo.

</details>

<details>
<summary>📚 Learn more</summary>

For more details about the underlying pipeline service, see
`microservices/dlstreamer-pipeline-server/README.md`.

</details>

