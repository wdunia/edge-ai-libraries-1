import asyncio
import json
import os
import re
import psutil
import requests
from datetime import datetime
from collections import deque
from typing import TypeAlias


METRICS_ENDPOINT = os.environ.get("METRICS_ENDPOINT", "http://metrics-manager:9273/metrics")
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("METRICS_TIMEOUT_SECONDS", "2"))

GPU_METRIC_PATTERN = re.compile(
    r'^gpu_engine_usage_usage\{(?P<labels>[^}]*)}\s+(?P<value>[-+]?\d+(?:\.\d+)?)'
)
NPU_METRIC_PATTERN = re.compile(
    r'^npu_utilization\{(?P<labels>[^}]*)}\s+(?P<value>[-+]?\d+(?:\.\d+)?)'
)
LABEL_PATTERN = re.compile(r'(\w+)="([^"]*)"')


GpuUsageSnapshot: TypeAlias = dict[str, float | str]


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

    def _fetch_metrics_text(self):
        response = requests.get(METRICS_ENDPOINT, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_labels(labels_text: str):
        return {key: value for key, value in LABEL_PATTERN.findall(labels_text)}


    def get_gpu_usage(self):
        try:
            metrics_text = self._fetch_metrics_text()
            gpu_usage: GpuUsageSnapshot = {
                "bcs": "N/A",
                "ccs": "N/A",
                "rcs": "N/A",
                "vcs": "N/A",
                "vecs": "N/A",
            }

            engine_aliases = {
                "bcs": "bcs",
                "blitter": "bcs",
                "copy": "bcs",
                "ccs": "ccs",
                "compute": "ccs",
                "rcs": "rcs",
                "render": "rcs",
                "vcs": "vcs",
                "video": "vcs",
                "vecs": "vecs",
                "videoenhance": "vecs",
            }

            for line in metrics_text.splitlines():
                match = GPU_METRIC_PATTERN.match(line.strip())
                if not match:
                    continue

                labels = self._parse_labels(match.group("labels"))
                raw_engine = labels.get("engine", "").lower()
                engine = engine_aliases.get(raw_engine)
                if not engine:
                    continue

                gpu_usage[engine] = float(match.group("value"))

            return gpu_usage
        except (requests.RequestException, ValueError):
            return {
                "bcs": "N/A",
                "ccs": "N/A",
                "rcs": "N/A",
                "vcs": "N/A",
                "vecs": "N/A",
            }
        
    def get_npu_usage(self):
        try:
            metrics_text = self._fetch_metrics_text()

            for line in metrics_text.splitlines():
                match = NPU_METRIC_PATTERN.match(line.strip())
                if match:
                    return float(match.group("value"))

            return "N/A"
        except (requests.RequestException, ValueError):
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

