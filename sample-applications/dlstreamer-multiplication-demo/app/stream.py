import logging
import os
import threading
import urllib.parse
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Timeout for HTTP requests to the pipeline server (seconds)
REQUEST_TIMEOUT = int(os.environ.get("PIPELINE_SERVER_TIMEOUT", "30"))
DELETE_TIMEOUT = int(os.environ.get("PIPELINE_DELETE_TIMEOUT", "8"))

FULL_HD_WIDTH = 1920
FULL_HD_HEIGHT = 1080

RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "FULL": (FULL_HD_WIDTH, FULL_HD_HEIGHT),
    "2/3": (1280, 720),
    "1/2": (960, 540),
    "1/3": (640, 360),
}


def _get_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r, using default %s", name, value, default)
        return default


def _get_float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %s", name, value, default)
        return default


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


class Stream:
    def __init__(self):
        # Internal Docker hostname for backend-to-backend calls (same docker network)
        self.pipeline_server_host = os.environ.get(
            "PIPELINE_SERVER_HOST", "dlstreamer-pipeline-server"
        )
        # External host IP for URLs that reach the browser (WebRTC)
        self.external_ip = os.environ.get("HOST_IP", os.environ.get("ip", "localhost"))
        self._lock = threading.Lock()
        self.streaminfo: dict[str, dict[str, str]] = {}

    @property
    def _base_url(self) -> str:
        return f"http://{self.pipeline_server_host}:8080"

    def _build_stream_url(self, peer_id: str) -> str:
        return f"http://{self.external_ip}:8889/{peer_id}"

    @staticmethod
    def _build_model_instance_id(target_device: str) -> str:
        return f"pallet_defect_detection_{target_device.lower()}_inst0"

    @staticmethod
    def _normalize_target_device(target_device: str) -> str:
        return (target_device or "CPU").upper()

    @staticmethod
    def _select_pipeline_version(target_device: str, is_file_source: bool) -> str:
        device = Stream._normalize_target_device(target_device)

        if is_file_source and device == "GPU":
            return "pallet_defect_detection_file_loop_gpu"
        if is_file_source and device == "NPU":
            return "pallet_defect_detection_file_loop_npu"
        if is_file_source:
            return "pallet_defect_detection_file_loop"
        if device == "GPU":
            return "pallet_defect_detection_gpu"
        if device == "NPU":
            return "pallet_defect_detection_npu"
        return "pallet_defect_detection"

    @staticmethod
    def _build_detection_properties(model_path: str, target_device: str) -> dict[str, Any]:
        device = Stream._normalize_target_device(target_device)
        detection_properties: dict[str, Any] = {
            "model": model_path,
            "device": device,
            "model-instance-id": Stream._build_model_instance_id(device),
        }

        if device == "GPU":
            detection_properties.update(
                {
                    "pre-process-backend": os.environ.get(
                        "DLSPS_GPU_PRE_PROCESS_BACKEND", "va-surface-sharing"
                    ),
                    "inference-region": os.environ.get(
                        "DLSPS_GPU_INFERENCE_REGION", "full-frame"
                    ),
                    "inference-interval": _get_int_env(
                        "DLSPS_GPU_INFERENCE_INTERVAL", 1
                    ),
                    "batch-size": _get_int_env("DLSPS_GPU_BATCH_SIZE", 1),
                    "nireq": _get_int_env("DLSPS_GPU_NIREQ", 1),
                    "ie-config": os.environ.get(
                        "DLSPS_GPU_IE_CONFIG", "GPU_THROUGHPUT_STREAMS=1"
                    ),
                    "threshold": _get_float_env("DLSPS_GPU_THRESHOLD", 0.7),
                }
            )
        elif device == "NPU":
            detection_properties.update(
                {
                    "pre-process-backend": os.environ.get(
                        "DLSPS_NPU_PRE_PROCESS_BACKEND", "va"
                    ),
                    "batch-size": _get_int_env("DLSPS_NPU_BATCH_SIZE", 1),
                    "nireq": _get_int_env("DLSPS_NPU_NIREQ", 1),
                }
            )

        return detection_properties

    @staticmethod
    def _resolve_model_instance_id(target_device: str, stream_suffix: str) -> str | None:
        device = Stream._normalize_target_device(target_device)
        base_model_instance_id = Stream._build_model_instance_id(device)

        if device == "CPU":
            return base_model_instance_id

        if device == "GPU":
            if _get_bool_env("DLSPS_GPU_SHARE_MODEL_INSTANCE", True):
                return base_model_instance_id
            return f"{base_model_instance_id}_{stream_suffix}"

        if _get_bool_env("DLSPS_NPU_SHARE_MODEL_INSTANCE", True):
            return base_model_instance_id

        return f"{base_model_instance_id}_{stream_suffix}"

    @staticmethod
    def _resolve_resolution(resolution_preset: str | None) -> tuple[str, int, int]:
        preset = (resolution_preset or "2/3").strip().upper()

        aliases = {
            "FULL": "FULL",
            "2/3": "2/3",
            "1/2": "1/2",
            "1/3": "1/3",
            "1920X1080": "FULL",
            "1280X720": "2/3",
            "960X540": "1/2",
            "640X360": "1/3",
        }

        normalized = aliases.get(preset)
        if not normalized:
            raise ValueError(
                "Unsupported resolution preset. Allowed values: Full, 2/3, 1/2, 1/3"
            )

        width, height = RESOLUTION_PRESETS[normalized]
        return normalized, width, height

    @staticmethod
    def _resolve_inference_interval(
        target_device: str, inference_interval: int | None
    ) -> int:
        device = Stream._normalize_target_device(target_device)

        if inference_interval is None:
            if device == "GPU":
                return _get_int_env("DLSPS_GPU_INFERENCE_INTERVAL", 1)
            if device == "NPU":
                return _get_int_env("DLSPS_NPU_INFERENCE_INTERVAL", 1)
            return _get_int_env("DLSPS_CPU_INFERENCE_INTERVAL", 1)

        return _clamp_int(int(inference_interval), 1, 120)

    def _load_stream_info_from_pipeline(self, stream_id: str) -> dict[str, str] | None:
        url = f"{self._base_url}/pipelines/{stream_id}"

        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            summary = response.json()
        except requests.RequestException as e:
            logger.warning(f"Unable to load pipeline summary for {stream_id}: {e}")
            return None

        request = summary.get("request", {}) if isinstance(summary, dict) else {}
        destination = request.get("destination", {}) if isinstance(request, dict) else {}
        frame = destination.get("frame", {}) if isinstance(destination, dict) else {}
        parameters = request.get("parameters", {}) if isinstance(request, dict) else {}
        detection_properties = (
            parameters.get("detection-properties", {})
            if isinstance(parameters, dict)
            else {}
        )

        peer_id = frame.get("peer-id") if isinstance(frame, dict) else None
        target_device = (
            detection_properties.get("device")
            if isinstance(detection_properties, dict)
            else None
        )

        if not isinstance(peer_id, str) or not peer_id:
            logger.warning(f"Pipeline summary for {stream_id} does not contain peer-id")
            return None

        stream_info = {
            "peer_id": peer_id,
            "target_device": target_device if isinstance(target_device, str) else "unknown",
        }

        with self._lock:
            self.streaminfo[stream_id] = stream_info

        return stream_info

    def add_stream(
        self,
        stream_path: str,
        model_path: str,
        target_device: str,
        resolution_preset: str | None = None,
        inference_interval: int | None = None,
    ) -> dict[str, str]:
        hex_v = os.urandom(8).hex()
        peer_id = f"pallet_defect_detection_{hex_v}"
        target_device = self._normalize_target_device(target_device)
        source_scheme = urlparse(stream_path).scheme.lower()
        is_file_source = source_scheme == "file"
        pipeline_version = self._select_pipeline_version(target_device, is_file_source)
        resolved_preset, input_width, input_height = self._resolve_resolution(
            resolution_preset
        )
        resolved_inference_interval = self._resolve_inference_interval(
            target_device, inference_interval
        )

        source: dict[str, Any]
        if is_file_source:
            source_path = urllib.parse.unquote(urlparse(stream_path).path)
            source = {
                "element": "multifilesrc",
                "type": "gst",
                "properties": {
                    "location": source_path,
                    "loop": True,
                    "stop-index": -1,
                },
            }
        else:
            source = {
                "uri": stream_path,
                "type": "uri",
            }

        payload: dict[str, Any] = {
            "source": source,
            "destination": {
                "metadata": {
                    "type": "file",
                    "path": "/tmp/results.jsonl",
                    "format": "json-lines",
                },
                "frame": {
                    "type": "webrtc",
                    "peer-id": peer_id,
                },
            },
            "parameters": {
                "input_width": input_width,
                "input_height": input_height,
                "detection-properties": self._build_detection_properties(
                    model_path, target_device
                )
            },
        }

        resolved_model_instance_id = self._resolve_model_instance_id(target_device, hex_v)
        if resolved_model_instance_id:
            payload["parameters"]["detection-properties"][
                "model-instance-id"
            ] = resolved_model_instance_id

        if target_device != "NPU":
            payload["parameters"]["detection-properties"][
                "inference-interval"
            ] = resolved_inference_interval

        url = f"{self._base_url}/pipelines/user_defined_pipelines/{pipeline_version}"
        logger.info(
            f"Creating pipeline: version={pipeline_version}, "
            f"device={target_device}, source={stream_path}, "
            f"resolution={resolved_preset} ({input_width}x{input_height}), "
            f"inference_interval={resolved_inference_interval}, "
            f"model_instance_id={resolved_model_instance_id}"
        )

        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        stream_id = response.text.replace('"', '').strip()
        with self._lock:
            self.streaminfo[stream_id] = {
                "target_device": target_device,
                "peer_id": peer_id,
            }

        logger.info(f"Pipeline created: {stream_id}")
        return {
            "stream_id": stream_id,
            "peer_id": peer_id,
            "stream_url": self._build_stream_url(peer_id),
            "resolution_preset": resolved_preset,
            "resolution": f"{input_width}x{input_height}",
            "inference_interval": str(resolved_inference_interval),
        }

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
        response = requests.delete(url, timeout=DELETE_TIMEOUT)
        response.raise_for_status()

        with self._lock:
            self.streaminfo.pop(stream_id, None)

        logger.info(f"Pipeline deleted: {stream_id}")
        return {"message": f"Stream {stream_id} deleted successfully."}

    def view_stream(self, stream_id: str) -> dict:
        with self._lock:
            stream_info = self.streaminfo.get(stream_id)

        if not stream_info:
            stream_info = self._load_stream_info_from_pipeline(stream_id)

        if stream_info and stream_info.get("peer_id"):
            stream_url = self._build_stream_url(stream_info["peer_id"])
            target_device = stream_info.get("target_device", "unknown")
        else:
            logger.warning(f"Stream metadata not found for {stream_id}")
            stream_url = None
            target_device = "unknown"

        return {
            stream_id: {
                "target_device": target_device,
                "url": stream_url or "",
            }
        }
