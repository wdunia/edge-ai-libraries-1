# DL Streamer Multiplication Demo

Standalone DL Streamer demo (backend + UI + supporting services).

## Quick start (Linux)

```bash
cd sample-applications/dlstreamer-multiplication-demo
chmod +x scripts/*.sh
./scripts/install_dlStreamer.sh
./scripts/run_dlStreamer.sh --force-restart
```

When it's up:
- UI: http://localhost:8101

---

<details>
<summary>Optional flags</summary>

```bash
./scripts/run_dlStreamer.sh --open-browser
```

</details>

<details>
<summary>What is included</summary>

- `app/` - demo backend source
- `src/ui/react/` - demo frontend source
- `scripts/` - host-side install/launcher scripts
- `tools/` - browser automation
- `nginx_config/` - nginx proxy config used by demo
- `docker/docker-compose.images.yml` - standalone compose using only prebuilt images
- `docker/.env.example` - tracked template for stack env
- `docker/.env` - generated locally on first run

</details>

<details>
<summary>Building the demo images manually</summary>

Two images (`DLSTREAMER_DEMO_BE_IMAGE`, `DLSTREAMER_DEMO_UI_IMAGE`) are built
automatically the first time you run the scripts above. If you want to build
or rebuild them yourself:

```bash
./scripts/build_demo_images.sh
```

</details>

<details>
<summary>Troubleshooting</summary>

- View logs:

  ```bash
  docker compose --env-file docker/.env -f docker/docker-compose.images.yml logs -f
  ```

- If startup takes longer than 10 minutes, increase the wait timeout:

  ```bash
  export MAX_WAIT_SECONDS=3600
  ./scripts/run_dlStreamer.sh
  ```

- `--open-browser` requires an Xorg (X11) session, not Wayland. Check with
  `echo "$XDG_SESSION_TYPE"`. If it prints `wayland`, log out, click your
  username, use the gear icon, and select **Ubuntu on Xorg** before logging
  back in.

</details>
