import os
import time
import socket
import importlib

browser_name = "Chrome"
ui_host = os.environ.get("EXTERNAL_HOST") or os.environ.get("HOST_IP") or None
ui_port = os.environ.get("UI_PORT") or "8103"


def has_graphical_session() -> bool:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    return any(
        os.environ.get(variable)
        for variable in ("DISPLAY", "WAYLAND_DISPLAY")
    ) or session_type in {"x11", "wayland"}


def load_get_monitors():
    try:
        module = importlib.import_module("screeninfo")
    except ImportError:
        print("screeninfo is not installed. Skipping automatic browser launch.")
        return None

    return getattr(module, "get_monitors", None)


def load_browser_automation():
    try:
        selenium = importlib.import_module("selenium")
        selenium_exceptions = importlib.import_module("selenium.common.exceptions")
        selenium_service = importlib.import_module("selenium.webdriver.chrome.service")
        webdriver_manager = importlib.import_module("webdriver_manager.chrome")
    except ImportError:
        print("Browser automation dependencies are not installed. Skipping automatic browser launch.")
        return None

    return {
        "webdriver": getattr(selenium, "webdriver"),
        "web_driver_exception": getattr(selenium_exceptions, "WebDriverException"),
        "service": getattr(selenium_service, "Service"),
        "chrome_driver_manager": getattr(webdriver_manager, "ChromeDriverManager"),
    }

def get_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except OSError:
        return "127.0.0.1"
    
    
def get_screen_resolution():
    get_monitors = load_get_monitors()
    if get_monitors is None:
        return None

    try:
        for monitor_0 in get_monitors():
            width = monitor_0.width
            height = monitor_0.height
            return width, height

        return None
    except Exception as exc:
        print(f"Unable to detect screen resolution: {exc}")
        return None
    
    
def set_window(driver, x: int, y: int, width: int, height: int):
    d = driver
    d.set_window_size(width, height)
    d.set_window_position(x, y)
    return d


def open_browser(url: str):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("Wrong URL")

    if not has_graphical_session():
        print("No graphical session detected. Skipping automatic browser launch.")
        return None

    browser_automation = load_browser_automation()
    if browser_automation is None:
        return None

    webdriver = browser_automation["webdriver"]
    web_driver_exception = browser_automation["web_driver_exception"]
    service = browser_automation["service"]
    chrome_driver_manager = browser_automation["chrome_driver_manager"]
    
    try:
        os.environ["TMPDIR"] = "/tmp"
        driver = webdriver.Chrome(service=service(chrome_driver_manager().install()))
        driver.get(url)
        return driver
    except web_driver_exception as e:
        print(e)
        return None
    
    
def main():
    local_ip = ui_host or get_ip()

    if not has_graphical_session():
        print(f"No graphical session detected. Open the UI manually: http://{local_ip}:{ui_port}")
        return

    resolution = get_screen_resolution()
    if resolution is None:
        print(f"Screen resolution unavailable. Open the UI manually: http://{local_ip}:{ui_port}")
        return

    width, height = resolution
    dlstreamer = open_browser(f"http://{local_ip}:{ui_port}")
    if dlstreamer is None:
        print(f"Automatic browser launch failed. Open the UI manually: http://{local_ip}:{ui_port}")
        return

    print(f"window: {browser_name}, x=0, y=0, width={width}, height={height}")
    set_window(driver=dlstreamer, x=0, y=0, width=width, height=height)
    input("is ok?")
    time.sleep(999)
    
    
if __name__ == "__main__":
    main()
