import asyncio
import inspect
import json
import os
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
            bcs = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep gpu_engine_usage_usage{engine | grep bcs | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            ccs = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep gpu_engine_usage_usage{engine | grep ccs | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            rcs = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep gpu_engine_usage_usage{engine | grep rcs | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            vcs = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep gpu_engine_usage_usage{engine | grep vcs | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            vecs = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep gpu_engine_usage_usage{engine | grep vecs | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            return {"bcs": float(bcs), "ccs": float(ccs), "rcs": float(rcs), "vcs": float(vcs), "vecs": float(vecs)}
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return "N/A"
        
    def get_npu_usage(self):
        # try:
        result = subprocess.run('curl -s http://metrics-manager:9273/metrics | grep npu_utilization{ | cut -d" " -f2', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        return float(result)
        # except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        #     return "N/A"


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

