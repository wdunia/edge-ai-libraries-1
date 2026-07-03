import os
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

def get_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        return local_ip
    
    
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
    dlstreamer = open_browser(f"http://{local_ip}:8101")
    print(f"window: {browser_name}, x=0, y=0, width={width}, height={height}")
    set_window(driver=dlstreamer, x=0, y=0, width=width, height=height)
    input("is ok?")
    time.sleep(999)
    
    
if __name__ == "__main__":
    main()
