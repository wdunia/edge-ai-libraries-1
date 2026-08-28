import os
import signal
import sys
import time
import socket
from screeninfo import get_monitors
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from threading import Thread

browser_name = "Chrome"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

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


def get_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        local_ip=s.getsockname()[0]
        return local_ip
    

def ask_prompt():
    print(f"{CYAN}Enter prompt for both chatbots:{RESET} ", end="")
    prompt = input()
    return prompt


def clear_terminal():
    os.system("clear")


def print_example_questions():
    print("Example prompts:")
    print("1. List the logical steps to determine if a number is prime. Be concise, max 5 steps.")
    print("2. Write a Python function that reverses a string without using built-in reverse methods. Include one usage example.")
    print("3. Explain the difference between TCP and UDP protocols. Use exactly 3 bullet points.")
    print("4. Solve step by step: A train travels 120 km in 1.5 hours. What is its average speed in m/s? Write in plain text.")
    print("5. A farmer needs to cross a river with a fox, a chicken, and a bag of grain. The boat fits only the farmer and one item. The fox eats the chicken if left alone, the chicken eats the grain if left alone. Provide the exact sequence of crossings to get everything safely across. Use bullet list.")
    print("CTRL+C is disabled in this prompt window to prevent accidental app interruption.")
    print("Type 'exit' or 'quit' to close the prompt loop.")
    print()


def insert_prompt_gpt(driver, prompt: str):
    submit_prompt(driver, GPT_PROMPT_SELECTORS, "ChatGPT", prompt)


def insert_prompt_local(driver, prompt: str):
    submit_prompt(driver, LOCAL_PROMPT_SELECTORS, "Local Chat Bot", prompt)


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
    
    
def run_safely(label: str, func, *args):
    try:
        func(*args)
    except Exception as exc:  # noqa: BLE001 - one chatbot must not break the other
        print(f"{YELLOW}[{label}] prompt submission failed: {exc}{RESET}")


def get_screen_resolution():
    try:
        for monitor_0 in get_monitors():
            width = monitor_0.width
            height = monitor_0.height
            return width, height
    except Exception:
        pass
    print(f"{YELLOW}Could not detect screen resolution, falling back to 1920x1080.{RESET}")
    return 1920, 1080
    
    
def set_window(driver, x: int, y: int, width: int, height: int):
    d = driver
    d.set_window_size(width, height)
    d.set_window_position(x, y)
    return d


def open_browser(url: str):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("Wrong URL")
    
    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        os.environ["TMPDIR"] = "/tmp"
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        return driver
    except WebDriverException as e:
        print(e)
        return False
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)
    
    
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


def main():
    inspect_mode = "--inspect" in sys.argv
    width, height = get_screen_resolution()
    local_ip = get_ip()
    chatgpt = open_browser("https://chatgpt.com")
    localai = open_browser(f"http://{local_ip}:8101")
    half_width = width //2
    print(f"window: {browser_name}, x=0, y=0, width={half_width}, height={height}")
    set_window(driver=chatgpt, x=0, y=0, width=half_width, height=height)
    print(f"Window: {browser_name}, x={half_width}, y=0, width={half_width}, height={height}")
    set_window(driver=localai, x=int(half_width)+1, y=0, width=half_width, height=height)
    time.sleep(5)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    if inspect_mode:
        input("Log in to ChatGPT if needed, then press Enter to list the page elements...")
        inspect_composers(chatgpt, "ChatGPT")
        inspect_composers(localai, "Local Chat Bot")
        input("\nPress Enter to continue to the prompt loop...")

    clear_terminal()
    print_example_questions()

    try:
        while True:
            my_prompt = ask_prompt().strip()
            if not my_prompt:
                continue

            if my_prompt.lower() in {"exit", "quit"}:
                break

            gpt_thread = Thread(target=run_safely, args=("ChatGPT", insert_prompt_gpt, chatgpt, my_prompt))
            local_thread = Thread(target=run_safely, args=("Local Chat Bot", insert_prompt_local, localai, my_prompt))
            gpt_thread.start()
            local_thread.start()
            gpt_thread.join()
            local_thread.join()
    finally:
        if chatgpt:
            chatgpt.quit()
        if localai:
            localai.quit()
    
    
if __name__ == "__main__":
    main()
