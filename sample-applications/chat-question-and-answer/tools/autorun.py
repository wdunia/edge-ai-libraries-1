import os
import time
import socket
from screeninfo import get_monitors
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from threading import Thread

browser_name = "Chrome"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

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
    print("Type 'exit' or 'quit' to close the prompt loop.")
    print()


def print_interrupt_hint():
    print()
    print(f"{YELLOW}CTRL+C ignored in prompt window. Use 'exit' or 'quit' to close the app loop.{RESET}")


def insert_prompt_gpt(driver, prompt: str):
    textbox = driver.find_element(By.CLASS_NAME, "placeholder")
    textbox.send_keys(prompt)
    textbox.send_keys(Keys.ENTER)
    
    
def insert_prompt_local(driver, prompt: str):
    # The local chatbot uses Mantine UI with CSS modules (hashed class names).
    # Try matching the promptInput CSS-module class first, then fall back to textarea tag.
    try:
        textbox = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='promptInput']"))
        )
    except Exception:
        textbox = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "textarea"))
        )
    textbox.click()
    textbox.send_keys(prompt)
    textbox.send_keys(Keys.ENTER)
    
    
def get_screen_resolution():
    try:
        for monitor_0 in get_monitors():
            width = monitor_0.width
            height = monitor_0.height
            return width, height
    except:
        return False
    
    
def set_window(driver, x: int, y: int, width: int, height: int):
    d = driver
    d.set_window_size(width, height)
    d.set_window_position(x, y)
    return d


def open_browser(url: str):
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("Wrong URL")
    
    try:
        os.environ["TMPDIR"] = "/tmp"
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        return driver
    except WebDriverException as e:
        print(e)
        return False
    
    
def main():
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

    clear_terminal()
    print_example_questions()

    try:
        while True:
            try:
                my_prompt = ask_prompt().strip()
            except KeyboardInterrupt:
                print_interrupt_hint()
                continue

            if not my_prompt:
                continue

            if my_prompt.lower() in {"exit", "quit"}:
                break

            try:
                gpt_thread = Thread(target=insert_prompt_gpt, args=(chatgpt, my_prompt))
                local_thread = Thread(target=insert_prompt_local, args=(localai, my_prompt))
                gpt_thread.start()
                local_thread.start()
                gpt_thread.join()
                local_thread.join()
            except KeyboardInterrupt:
                print_interrupt_hint()
                continue
    finally:
        if chatgpt:
            chatgpt.quit()
        if localai:
            localai.quit()
    
    
if __name__ == "__main__":
    main()
