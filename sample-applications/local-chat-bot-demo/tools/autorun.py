"""Side-by-side demo driver.

Opens ChatGPT and the local chat bot next to each other and submits the same
prompt to both. Prompts come either from the browser console served by
console_server (default) or from the terminal loop (--cli).
"""

import argparse
import os
import shutil
import signal
import socket
import threading
import time
from pathlib import Path

from screeninfo import get_monitors
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

import console_server
from console_server import ConsoleServer, PromptBus
from prompts import EXAMPLE_PROMPTS

CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

DEMO_ROOT = Path(__file__).resolve().parent.parent

CHATGPT_URL = "https://chatgpt.com/"
LOCAL_UI_PORT = int(os.environ.get("LOCAL_UI_PORT", "8101"))
CONSOLE_PORT = int(os.environ.get("PROMPT_CONSOLE_PORT", "8102"))
CONSOLE_HEIGHT_PCT = int(os.environ.get("PROMPT_CONSOLE_HEIGHT_PCT", "22"))
CHATGPT_PROFILE_DIR = Path(
    os.environ.get("CHATGPT_PROFILE_DIR", DEMO_ROOT / ".cache" / "chrome-gpt")
)

CONSOLE_MIN_HEIGHT = 180
CONSOLE_MAX_HEIGHT = 320
CONSOLE_WATCHDOG_INTERVAL = 2.0

# Ordered by priority: the first selector that matches a visible element wins.
# A single "a, b, c" selector cannot be used here, because CSS lists return the
# first match in DOM order, which may well be a hidden mirror of the composer.
GPT_PROMPT_SELECTORS = (
    'textarea[aria-label*="ChatGPT"]',
    "#prompt-textarea",
    'div[contenteditable="true"]',
)
# Local chatbot: Mantine CSS modules produce hashed class names.
LOCAL_PROMPT_SELECTORS = (
    "[class*='promptInput']",
    "textarea",
)
LOCAL_NEW_CHAT_SELECTOR = "[class*='newChatButton']"


def get_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def get_screen_resolution():
    try:
        for monitor in get_monitors():
            return monitor.width, monitor.height
    except Exception:  # noqa: BLE001 - screeninfo raises backend-specific errors
        pass
    print(f"{YELLOW}Could not detect screen resolution, falling back to 1920x1080.{RESET}")
    return 1920, 1080


def compute_layout(width: int, height: int, with_console: bool):
    """Chats share the top of the screen, the console spans the bottom strip."""
    chat_width = width // 2
    if not with_console:
        return {
            "chatgpt": (0, 0, chat_width, height),
            "local": (chat_width, 0, width - chat_width, height),
        }

    console_height = round(height * CONSOLE_HEIGHT_PCT / 100)
    console_height = max(CONSOLE_MIN_HEIGHT, min(console_height, CONSOLE_MAX_HEIGHT, height // 2))
    chat_height = height - console_height
    return {
        "chatgpt": (0, 0, chat_width, chat_height),
        "local": (chat_width, 0, width - chat_width, chat_height),
        "console": (0, chat_height, width, console_height),
    }


def prepare_profile_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)  # holds the ChatGPT session cookies
    # Chrome refuses to reuse a profile when locks from a previous crash are left behind.
    for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        (path / lock).unlink(missing_ok=True)


_chromedriver_path = None


def chromedriver_path() -> str:
    global _chromedriver_path
    if _chromedriver_path is None:
        _chromedriver_path = ChromeDriverManager().install()
    return _chromedriver_path


def restore_window_state(driver):
    """set_window_rect is ignored while a window is maximised or full screen."""
    try:
        window_id = driver.execute_cdp_cmd("Browser.getWindowForTarget", {})["windowId"]
        driver.execute_cdp_cmd(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "normal"}},
        )
    except (WebDriverException, KeyError):
        pass


class ManagedWindow:
    """A Chrome window whose geometry and lifetime the demo owns."""

    def __init__(self, key, label, url, profile_dir=None, app_mode=False):
        self.key = key
        self.label = label
        self.url = url
        self.profile_dir = profile_dir
        self.app_mode = app_mode
        self.rect = (0, 0, 1280, 800)
        self.driver = None
        # Per-window lock, so a prompt still reaches both chatbots in parallel.
        self.lock = threading.Lock()

    def _start(self, app_mode: bool):
        options = webdriver.ChromeOptions()
        x, y, width, height = self.rect
        options.add_argument(f"--window-position={x},{y}")
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        if self.profile_dir is not None:
            options.add_argument(f"--user-data-dir={self.profile_dir}")
        if app_mode:
            options.add_argument(f"--app={self.url}")

        driver = webdriver.Chrome(service=Service(chromedriver_path()), options=options)
        if not app_mode:
            driver.get(self.url)
        return driver

    def open(self):
        self.close()
        if self.profile_dir is not None:
            prepare_profile_dir(self.profile_dir)

        os.environ["TMPDIR"] = "/tmp"
        previous_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            try:
                self.driver = self._start(self.app_mode)
            except WebDriverException as exc:
                if not self.app_mode:
                    raise
                print(f"{YELLOW}[{self.label}] --app window failed ({exc}); using a normal window.{RESET}")
                self.driver = self._start(app_mode=False)
        finally:
            signal.signal(signal.SIGINT, previous_sigint_handler)

        self.apply_rect()

    def close(self):
        if self.driver is None:
            return
        try:
            self.driver.quit()
        except WebDriverException:
            pass
        finally:
            self.driver = None

    def is_alive(self) -> bool:
        if self.driver is None:
            return False
        try:
            return bool(self.driver.window_handles)
        except WebDriverException:
            return False

    def apply_rect(self):
        x, y, width, height = self.rect
        restore_window_state(self.driver)
        self.driver.set_window_rect(x=x, y=y, width=width, height=height)


def find_composer(driver, selectors, label: str, timeout: int = 20):
    """Return the first visible and enabled element matching the selectors, in order."""
    deadline = time.monotonic() + timeout
    while True:
        for selector in selectors:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed() and element.is_enabled():
                    return element
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"{label}: no visible prompt field found, tried: {', '.join(selectors)}"
            )
        time.sleep(0.5)


def composer_text(element) -> str:
    return (element.get_attribute("value") or element.text or "").strip()


def submit_prompt(driver, selectors, label: str, prompt: str):
    textbox = find_composer(driver, selectors, label)
    # Focused via JS instead of click(): the composer is often covered by other
    # elements, which makes a native click fail with "element click intercepted".
    driver.execute_script("arguments[0].focus();", textbox)
    textbox.send_keys(prompt)
    if not composer_text(textbox):
        raise RuntimeError(f"{label}: <{textbox.tag_name}> did not accept the text")
    textbox.send_keys(Keys.ENTER)


def click_new_chat(driver) -> bool:
    for element in driver.find_elements(By.CSS_SELECTOR, LOCAL_NEW_CHAT_SELECTOR):
        if element.is_displayed() and element.is_enabled():
            driver.execute_script("arguments[0].click();", element)
            return True
    return False


def inspect_composers(driver, label: str):
    """Print every input-like element, so selectors can be verified against the real page."""
    probes = ("textarea", "div[contenteditable='true']", "[id*='prompt']", "[data-testid*='prompt']")
    print(f"\n=== {label} ===")
    for probe in probes:
        for element in driver.find_elements(By.CSS_SELECTOR, probe):
            print(
                f"  match={probe:<28} tag={element.tag_name:<9} "
                f"displayed={str(element.is_displayed()):<5} "
                f"id={element.get_attribute('id')!r} "
                f"aria-label={element.get_attribute('aria-label')!r} "
                f"data-testid={element.get_attribute('data-testid')!r}"
            )


def print_example_prompts():
    print("Example prompts:")
    for index, prompt in enumerate(EXAMPLE_PROMPTS, start=1):
        print(f"{index}. {prompt}")
    print("CTRL+C is disabled in this prompt window to prevent accidental app interruption.")
    print("Type 'layout' to rearrange the browser windows.")
    print("Type 'exit' or 'quit' to close the prompt loop.")
    print()


class Demo:
    def __init__(self, use_console: bool):
        self.use_console = use_console
        self.bus = PromptBus()
        self.server = None
        self.console = None
        self.chatgpt = ManagedWindow(
            "chatgpt", "ChatGPT", CHATGPT_URL, profile_dir=CHATGPT_PROFILE_DIR
        )
        self.local = ManagedWindow(
            "local", "Local Chat Bot", f"http://{get_ip()}:{LOCAL_UI_PORT}"
        )
        self.selectors = {"chatgpt": GPT_PROMPT_SELECTORS, "local": LOCAL_PROMPT_SELECTORS}
        self._watchdog_stop = threading.Event()
        self._watchdog = None

    @property
    def chats(self):
        return (self.chatgpt, self.local)

    @property
    def windows(self):
        return self.chats if self.console is None else self.chats + (self.console,)

    # --- lifecycle -----------------------------------------------------------

    def start(self):
        if self.use_console:
            self.server = ConsoleServer(self.bus, port=CONSOLE_PORT)
            self.server.start()
            self.console = ManagedWindow(
                "console", "Prompt console", self.server.url, app_mode=True
            )

        self._assign_rects()
        for window in self.windows:
            window.open()

        if self.console is not None:
            self._watchdog = threading.Thread(target=self._watch_console, daemon=True)
            self._watchdog.start()

    def stop(self):
        self._watchdog_stop.set()
        if self._watchdog is not None:
            self._watchdog.join(timeout=CONSOLE_WATCHDOG_INTERVAL * 2)
        for window in self.windows:
            window.close()
        if self.server is not None:
            self.server.stop()

    def _watch_console(self):
        """The console owns every control, so a closed console window must come back."""
        while not self._watchdog_stop.wait(CONSOLE_WATCHDOG_INTERVAL):
            with self.console.lock:
                if self.console.is_alive():
                    continue
                try:
                    self.console.open()
                except WebDriverException as exc:
                    print(f"{YELLOW}Could not reopen the prompt console: {exc}{RESET}")
                    print(f"{YELLOW}Open it manually: {self.server.url}{RESET}")
                    return

    # --- layout --------------------------------------------------------------

    def _assign_rects(self):
        width, height = get_screen_resolution()
        layout = compute_layout(width, height, with_console=self.console is not None)
        for window in self.windows:
            window.rect = layout[window.key]
        return width, height

    def relayout(self) -> str:
        """Restore the window arrangement without touching the conversations."""
        width, height = self._assign_rects()
        reopened = []
        for window in self.windows:
            with window.lock:
                if window.is_alive():
                    window.apply_rect()
                else:
                    window.open()
                    reopened.append(window.label)

        detail = f"Windows rearranged for {width}x{height}"
        if reopened:
            detail += f"; reopened: {', '.join(reopened)}"
        return detail

    # --- commands ------------------------------------------------------------

    def _run_on_chats(self, action):
        threads = [
            threading.Thread(target=action, args=(window,), daemon=True)
            for window in self.chats
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _report(self, window, action: str, work):
        self.bus.publish(window.key, "sending")
        try:
            work()
        except Exception as exc:  # noqa: BLE001 - one chatbot must not break the other
            message = f"[{window.label}] {action} failed: {exc}"
            print(f"{YELLOW}{message}{RESET}")
            self.bus.publish(window.key, "error", message)
        else:
            self.bus.publish(window.key, "ok")

    def send_prompt(self, prompt: str):
        def submit(window):
            def work():
                with window.lock:
                    submit_prompt(window.driver, self.selectors[window.key], window.label, prompt)

            self._report(window, "prompt submission", work)

        self._run_on_chats(submit)

    def new_conversation(self):
        def reset(window):
            def work():
                with window.lock:
                    if window is self.local and click_new_chat(window.driver):
                        return
                    window.driver.get(window.url)

            self._report(window, "new conversation", work)

        self._run_on_chats(reset)

    def rearrange(self):
        try:
            detail = self.relayout()
        except WebDriverException as exc:
            message = f"Rearranging windows failed: {exc}"
            print(f"{YELLOW}{message}{RESET}")
            self.bus.publish("layout", "error", message)
        else:
            print(detail)
            self.bus.publish("layout", "ok", detail)

    # --- loops ---------------------------------------------------------------

    def run_console_loop(self):
        print(f"{CYAN}Prompt console:{RESET} {self.server.url}")
        print("Use the console window at the bottom of the screen to drive the demo.")
        while True:
            command = self.bus.next_command()
            if command is None:
                continue
            kind = command["kind"]
            if kind == console_server.SHUTDOWN:
                break
            if kind == console_server.PROMPT:
                self.send_prompt(command["text"])
            elif kind == console_server.RESET:
                self.new_conversation()
            elif kind == console_server.RELAYOUT:
                self.rearrange()

    def run_cli_loop(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        os.system("clear")
        print_example_prompts()
        while True:
            print(f"{CYAN}Enter prompt for both chatbots:{RESET} ", end="")
            prompt = input().strip()
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit"}:
                break
            if prompt.lower() == "layout":
                self.rearrange()
                continue
            self.send_prompt(prompt)


def parse_args():
    parser = argparse.ArgumentParser(description="Local Chat Bot side-by-side demo driver.")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Read prompts from the terminal instead of the browser console.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="List candidate prompt fields before starting the loop.",
    )
    parser.add_argument(
        "--reset-chatgpt-profile",
        action="store_true",
        help="Delete the persistent ChatGPT browser profile before starting.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.reset_chatgpt_profile:
        shutil.rmtree(CHATGPT_PROFILE_DIR, ignore_errors=True)
        print(f"Removed ChatGPT profile: {CHATGPT_PROFILE_DIR}")

    demo = Demo(use_console=not args.cli)
    demo.start()
    try:
        time.sleep(5)
        demo.rearrange()

        if args.inspect:
            input("Log in to ChatGPT if needed, then press Enter to list the page elements...")
            inspect_composers(demo.chatgpt.driver, "ChatGPT")
            inspect_composers(demo.local.driver, "Local Chat Bot")
            input("\nPress Enter to continue to the prompt loop...")

        if args.cli:
            demo.run_cli_loop()
        else:
            demo.run_console_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        demo.stop()


if __name__ == "__main__":
    main()
