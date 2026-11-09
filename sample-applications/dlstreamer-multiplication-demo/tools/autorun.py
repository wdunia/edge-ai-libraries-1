import os
import shutil
import subprocess
import sys
import webbrowser


def has_graphical_session() -> bool:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return any(
        os.environ.get(variable)
        for variable in ("DISPLAY", "WAYLAND_DISPLAY")
    ) or session_type in {"x11", "wayland"}


def open_browser(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        raise ValueError("Wrong URL")

    # Use the installed browser directly: WebDriver setup may require the internet.
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        browser = shutil.which(name)
        if browser:
            subprocess.Popen([browser, "--new-window", "--start-maximized", url])
            return True

    return webbrowser.open(url, new=1)


def main() -> int:
    host = os.environ.get("EXTERNAL_HOST") or os.environ.get("HOST_IP") or "127.0.0.1"
    port = os.environ.get("UI_PORT") or "8103"
    url = f"http://{host}:{port}"

    if not has_graphical_session():
        print(f"No graphical session detected. Open the UI manually: {url}")
        return 0

    try:
        if open_browser(url):
            return 0
    except (OSError, webbrowser.Error) as exc:
        print(f"Unable to launch browser: {exc}", file=sys.stderr)

    print(f"Automatic browser launch failed. Open the UI manually: {url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
