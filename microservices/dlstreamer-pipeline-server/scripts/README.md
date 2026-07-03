# DL Streamer Pipeline Server helper scripts

These scripts are intended to run the DL Streamer Pipeline Server demo with predefined values.

## Scripts

- `install_dlStreamer.sh` - one-time host provisioning for dependencies such as Docker, tmux, Python tooling, and Google Chrome.
- `run_dlStreamer.sh` - runtime launcher for the demo environment.

## Usage

```sh
chmod +x ./install_dlStreamer.sh ./run_dlStreamer.sh
./install_dlStreamer.sh
./run_dlStreamer.sh
```

Follow the instructions in the terminal.

The runtime script will ask whether the detected `model.xml` path is correct:
- If `Y`, the script continues.
- If `N`, provide the full path to `model.xml`.

## Startup behavior

- The runtime script waits for the UI backend on port `8888` and the main pipeline server on port `8080`.
- Waiting is limited by `MAX_WAIT_SECONDS` (default: `1800`).
- If startup takes too long, the script exits with a timeout message instead of retrying forever.

If you need a different timeout, export it before running the script:

```sh
export MAX_WAIT_SECONDS=3600
./run_dlStreamer.sh
```

## Environment handling

The runtime script temporarily updates:
- `docker/.env`
- `src/ui/react/.env`

Those files are automatically restored when the script exits, so the repository is not left with permanent local changes.

## Logs and tmux sessions

The script starts long-running commands in tmux sessions. If something appears stuck, attach to the session to inspect logs:

```sh
tmux attach-session -t dlstreamer
tmux attach-session -t metrics-manager
tmux attach-session -t ffmpeg-rtsp
```

> Attention! These scripts do not configure proxy or firewall settings on the target system.

## Display session requirement

The browser automation step is intended for Xorg (X11), not Wayland.

To check your current session type:

```sh
echo "$XDG_SESSION_TYPE"
```

If the output is `wayland`:
1. Log out.
2. Click your username.
3. Use the gear icon in the bottom-right corner.
4. Select **Ubuntu on Xorg**.
5. Log in again.
