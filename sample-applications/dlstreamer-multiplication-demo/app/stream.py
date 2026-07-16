import concurrent.futures
import logging
import os
import threading
import time
import urllib.parse
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Timeout for HTTP requests to the pipeline server (seconds)
REQUEST_TIMEOUT = int(os.environ.get("PIPELINE_SERVER_TIMEOUT", "30"))
DELETE_TIMEOUT = int(os.environ.get("PIPELINE_DELETE_TIMEOUT", "8"))
DELETE_WAIT_TIMEOUT = int(os.environ.get("PIPELINE_STOP_WAIT_TIMEOUT", str(DELETE_TIMEOUT)))
DELETE_POLL_INTERVAL = float(os.environ.get("PIPELINE_STOP_POLL_INTERVAL", "0.5"))

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


def _get_optional_bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None

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
    def _resolve_model_sharing(
        target_device: str, model_sharing: bool | None = None
    ) -> bool:
        device = Stream._normalize_target_device(target_device)

        if device == "CPU":
            return False

        if model_sharing is not None:
            return model_sharing

        global_model_sharing = _get_optional_bool_env("DLSPS_SHARE_MODEL_INSTANCE")
        if global_model_sharing is not None:
            return global_model_sharing

        if device == "GPU":
            return _get_bool_env("DLSPS_GPU_SHARE_MODEL_INSTANCE", False)

        return _get_bool_env("DLSPS_NPU_SHARE_MODEL_INSTANCE", False)

    @staticmethod
    def _resolve_model_instance_id(
        target_device: str, stream_suffix: str, model_sharing: bool | None = None
    ) -> str | None:
        device = Stream._normalize_target_device(target_device)
        base_model_instance_id = Stream._build_model_instance_id(device)

        if device == "CPU":
            return base_model_instance_id

        if Stream._resolve_model_sharing(device, model_sharing):
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
        model_sharing: bool | None = None,
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

        resolved_model_sharing = self._resolve_model_sharing(target_device, model_sharing)
        resolved_model_instance_id = self._resolve_model_instance_id(
            target_device, hex_v, resolved_model_sharing
        )
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
            f"model_sharing={resolved_model_sharing}, "
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
            "model_sharing": str(resolved_model_sharing).lower(),
        }

    def add_streams_parallel(
        self,
        pipeline_configs: list[dict],
        max_workers: int = 3,
    ) -> dict:
        """
        Add multiple streams in parallel using concurrent requests.
        
        Args:
            pipeline_configs: List of dicts with keys:
                - stream_path: str
                - model_path: str
                - target_device: str
                - resolution_preset: str (optional)
                - inference_interval: int (optional)
            max_workers: Maximum number of concurrent add operations (default: 3)
        
        Returns:
            {"succeeded": [...], "failed": [...]}
        """
        succeeded = []
        failed = []

        def add_one(config: dict) -> tuple[bool, dict | dict[str, str]]:
            try:
                result = self.add_stream(
                    stream_path=config["stream_path"],
                    model_path=config["model_path"],
                    target_device=config["target_device"],
                    resolution_preset=config.get("resolution_preset"),
                    inference_interval=config.get("inference_interval"),
                    model_sharing=config.get("model_sharing"),
                )
                return True, result
            except Exception as e:
                logger.warning(f"Failed to add pipeline: {e}")
                return False, {"error": str(e)}

        # Use ThreadPoolExecutor with controlled concurrency to avoid CPU spike
        effective_max_workers = min(max_workers, len(pipeline_configs))
        with concurrent.futures.ThreadPoolExecutor(max_workers=effective_max_workers) as executor:
            futures = [executor.submit(add_one, cfg) for cfg in pipeline_configs]
            for future in concurrent.futures.as_completed(futures):
                success, result = future.result()
                if success:
                    succeeded.append(result)
                else:
                    failed.append(result)

        logger.info(
            f"Parallel add completed: {len(succeeded)} succeeded, {len(failed)} failed"
        )
        return {
            "message": f"Added {len(succeeded)} pipeline(s), {len(failed)} failed.",
            "succeeded": succeeded,
            "failed": failed,
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

    def _get_pipeline_state(self, stream_id: str) -> str | None:
        url = f"{self._base_url}/pipelines/status"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            return None

        for pipeline in payload:
            if isinstance(pipeline, dict) and pipeline.get("id") == stream_id:
                state = pipeline.get("state")
                return str(state).upper() if state is not None else None

        return None

    def _wait_for_pipeline_stop(self, stream_id: str) -> str | None:
        deadline = time.monotonic() + max(DELETE_WAIT_TIMEOUT, 1)
        active_states = {"RUNNING", "QUEUED", "RECONNECTING", "BACKOFF_WAIT"}

        while time.monotonic() < deadline:
            state = self._get_pipeline_state(stream_id)
            if state is None or state not in active_states:
                return state
            time.sleep(max(DELETE_POLL_INTERVAL, 0.1))

        raise TimeoutError(
            f"Timed out waiting for pipeline {stream_id} to stop on the pipeline server."
        )

    def delete_stream(self, stream_id: str) -> dict:
        url = f"{self._base_url}/pipelines/{stream_id}"
        response = requests.delete(url, timeout=DELETE_TIMEOUT)
        response.raise_for_status()
        final_state = self._wait_for_pipeline_stop(stream_id)

        with self._lock:
            self.streaminfo.pop(stream_id, None)

        logger.info(
            "Pipeline delete acknowledged: %s (final_state=%s)",
            stream_id,
            final_state or "removed",
        )
        return {"message": f"Stream {stream_id} deleted successfully."}

    def delete_streams_parallel(self, stream_ids: list[str]) -> dict:
        """
        Delete multiple streams in parallel using concurrent requests.
        Returns summary of deletions (succeeded and failed).
        """
        succeeded = []
        failed = []

        def delete_one(stream_id: str) -> tuple[str, bool, str]:
            try:
                self.delete_stream(stream_id)
                return stream_id, True, ""
            except Exception as e:
                logger.warning(f"Failed to delete pipeline {stream_id}: {e}")
                return stream_id, False, str(e)

        # Use ThreadPoolExecutor with limited concurrency to avoid overwhelming the server
        max_workers = min(5, len(stream_ids))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(delete_one, sid) for sid in stream_ids]
            for future in concurrent.futures.as_completed(futures):
                stream_id, success, error = future.result()
                if success:
                    succeeded.append(stream_id)
                else:
                    failed.append({"stream_id": stream_id, "error": error})

        logger.info(
            f"Parallel delete completed: {len(succeeded)} succeeded, {len(failed)} failed"
        )
        return {
            "message": f"Deleted {len(succeeded)} pipeline(s), {len(failed)} failed.",
            "succeeded": succeeded,
            "failed": failed,
        }

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
