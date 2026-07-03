import logging
import os
import threading
import time
import urllib.parse

import requests

logger = logging.getLogger(__name__)

# Timeout for HTTP requests to the pipeline server (seconds)
REQUEST_TIMEOUT = int(os.environ.get("PIPELINE_SERVER_TIMEOUT", "30"))


class Stream:
    def __init__(self):
        # Internal Docker hostname for backend-to-backend calls (same docker network)
        self.pipeline_server_host = os.environ.get(
            "PIPELINE_SERVER_HOST", "dlstreamer-pipeline-server"
        )
        # External host IP for URLs that reach the browser (WebRTC)
        self.external_ip = os.environ.get("HOST_IP", os.environ.get("ip", "localhost"))
        self._lock = threading.Lock()
        self.streaminfo: dict[str, str] = {}

    @property
    def _base_url(self) -> str:
        return f"http://{self.pipeline_server_host}:8080"

    def add_stream(self, stream_path: str, model_path: str, target_device: str) -> str:
        hex_v = os.urandom(8).hex()
        payload = {
            "source": {
                "uri": stream_path,
                "type": "uri",
            },
            "destination": {
                "metadata": {
                    "type": "file",
                    "path": "/tmp/results.jsonl",
                    "format": "json-lines",
                },
                "frame": {
                    "type": "webrtc",
                    "peer-id": f"pallet-defect-detection-{hex_v}",
                },
            },
            "parameters": {
                "detection-properties": {
                    "model": model_path,
                    "device": target_device,
                }
            },
        }

        url = f"{self._base_url}/pipelines/user_defined_pipelines/pallet_defect_detection"
        logger.info(f"Creating pipeline: device={target_device}, source={stream_path}")

        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        stream_id = response.text.replace('"', '').strip()
        with self._lock:
            self.streaminfo[stream_id] = target_device

        logger.info(f"Pipeline created: {stream_id}")
        return response.text

    def view_metadata(self, file_path: str) -> str:
        encoded_path = urllib.parse.quote(file_path)
        url = f"{self._base_url}/metadata/{encoded_path}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        return response.text

    def view_pipeline(self) -> str:
        url = f"{self._base_url}/pipelines/status"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        return response.text

    def delete_stream(self, stream_id: str) -> dict:
        url = f"{self._base_url}/pipelines/{stream_id}"
        response = requests.delete(url, timeout=REQUEST_TIMEOUT)

        with self._lock:
            self.streaminfo.pop(stream_id, None)

        logger.info(f"Pipeline deleted: {stream_id}")
        return {"message": f"Stream {stream_id} deleted successfully."}

    def view_stream(self, stream_id: str) -> dict:
        url = f"{self._base_url}/stream/{stream_id}"

        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            stream_path = response.text.replace('"', '').strip()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Stream not ready for {stream_id}: {e}")
            stream_path = None

        if stream_path:
            stream_url = f"http://{self.external_ip}:8889/{stream_path}/"
        else:
            stream_url = None

        with self._lock:
            target_device = self.streaminfo.get(stream_id)

        return {
            stream_id: {
                "target_device": target_device or "unknown",
                "url": stream_url or "",
            }
        }
