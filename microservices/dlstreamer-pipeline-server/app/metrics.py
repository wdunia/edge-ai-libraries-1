import asyncio
import inspect
import json
import os
import random
import time
import psutil
import subprocess
from functools import wraps
from datetime import datetime
from collections import deque
from typing import Dict, List, AsyncGenerator, Any


class SystemMonitor:
    def __init__(self):
        self.timestamp = deque(maxlen=100)
        self.cpu_usage_history = deque(maxlen=100)
        self.ram_usage_history = deque(maxlen=100)
        self.gpu_usage_history = deque(maxlen=100)
        self.npu_usage_history = deque(maxlen=100)

    def get_cpu_usage(self):
        usage = psutil.cpu_percent(interval=1)
        return float(usage)


    def get_ram_usage_in_percent(self):
        mem = psutil.virtual_memory()
        usage = mem.percent
        return float(usage)
    
    def get_ram_usage_in_gb(self):
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        return f"{used_gb:.2f}/{total_gb:.2f})"


    def get_gpu_usage(self):
        try:
            # result = subprocess.run(['intel-gpu-top', '-l', '1', '-s', '1'], capture_output=True, text=True, timeout=5)
            # lines = result.stdout.split('\n')
            # for line in lines:
            #     if 'Render/3D' in line:
            #         parts = line.split()
            #         usage = float(parts[-1].strip('%'))
            #         return float(usage)
            # return "N/A"
            number = random.randint(0, 100)
            return f"{number:.1f}"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return "N/A"
        
    def get_npu_usage(self):
        try:
            # cwd = os.getcwd()
            # path =f"{cwd}/../../../tools/npu-monitor-tool/npu-monitor-tool.py"
            # result = subprocess.run(f"sudo Python3 {path} -i 1000 | grep 'utilization'",  shell=True, capture_output=True, text=True, timeout=5)
            # lines = result.stdout.split('\n')
            # for line in lines:
            #     if 'utilization' in line:
            #         parts = line.split()
            #         usage = float(parts[-1].strip('%'))
            #         return float(usage)
            # return "N/A"
            number = random.randint(0, 100)
            return f"{number:.1f}"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return "N/A"


    async def return_all(self, ram_type: str = "percent"):
        while True:
            timestamp_n = datetime.now().isoformat()
            cpu = self.get_cpu_usage()
            gpu = self.get_gpu_usage()
            npu = self.get_npu_usage()

            if ram_type == "gb":
                ram = self.get_ram_usage_in_gb()
            else:         
                ram = self.get_ram_usage_in_percent()
            
            data = {"timestamp": timestamp_n, "cpu": cpu, "gpu": gpu, "npu": npu, "ram": ram}
            yield f"data: {json.dumps(data)}\n\n"  # SSE format
            await asyncio.sleep(1)

