import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


def start_gpu_pipelines(count: int, config: dict, host: str, timeout: int) -> None:
    opener = build_opener(ProxyHandler({}))

    def request(path: str, payload: list[dict] | None = None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(
            f"http://127.0.0.1:8888{path}",
            data=body,
            headers={"Content-Type": "application/json", "Host": f"{host}:8888"},
        )
        with opener.open(req, timeout=timeout) as response:
            return json.load(response)

    result = request("/pipeline/batch/add", [config.copy() for _ in range(count)])
    if not isinstance(result, dict) or result.get("status") != "Success":
        raise RuntimeError(f"GPU pipeline creation failed: {result}")
    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError(f"Invalid pipeline creation metadata: {metadata}")
    succeeded = metadata.get("succeeded")
    failed = metadata.get("failed")
    if not isinstance(succeeded, list) or not isinstance(failed, list):
        raise RuntimeError(f"Invalid pipeline creation results: {metadata}")
    if failed or len(succeeded) != count:
        raise RuntimeError(
            f"Created {len(succeeded)}/{count} GPU pipelines; failures: {failed}. "
            "Successfully created pipelines have been left running."
        )
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("stream_id"), str)
        or not item["stream_id"].strip()
        for item in succeeded
    ):
        raise RuntimeError(f"Invalid pipeline identifiers: {succeeded}")
    pipeline_ids = {item["stream_id"] for item in succeeded}
    if len(pipeline_ids) != count:
        raise RuntimeError(f"Expected {count} unique pipeline identifiers: {succeeded}")

    deadline = time.monotonic() + timeout
    while True:
        status = request("/pipeline/status")
        if not isinstance(status, dict) or status.get("status") != "Success":
            raise RuntimeError(f"Unable to check GPU pipeline status: {status}")
        pipelines = status.get("metadata")
        if not isinstance(pipelines, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not isinstance(item.get("state"), str)
            for item in pipelines
        ):
            raise RuntimeError(f"Invalid pipeline status metadata: {pipelines}")
        states = {
            item["id"]: item["state"]
            for item in pipelines
            if item["id"] in pipeline_ids
        }
        errors = {
            pipeline_id: state
            for pipeline_id, state in states.items()
            if state not in {"RUNNING", "QUEUED"}
        }
        if errors:
            raise RuntimeError(f"GPU pipelines failed to start: {errors}")
        if len(states) == count and all(state == "RUNNING" for state in states.values()):
            print(f"All {count} GPU pipelines are RUNNING.")
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Timed out waiting for {count} GPU pipelines to run. "
                f"Last states: {states}. Check the pipeline server logs."
            )
        time.sleep(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start GPU pipelines using the local demo API.")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--resolution", required=True)
    parser.add_argument("--inference-interval", type=int, required=True)
    parser.add_argument("--model-sharing", choices=("true", "false"), required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    args = parser.parse_args()
    if args.count < 1 or args.timeout < 1:
        parser.error("--count and --timeout must be positive integers")
    config = {
        "stream_path": args.source,
        "model_path": args.model,
        "target_device": "GPU",
        "resolution_preset": args.resolution,
        "inference_interval": args.inference_interval,
        "model_sharing": args.model_sharing == "true",
    }
    try:
        start_gpu_pipelines(args.count, config, args.host, args.timeout)
    except HTTPError as exc:
        print(
            f"GPU pipeline API returned HTTP {exc.code}: "
            f"{exc.read().decode('utf-8', errors='replace')}",
            file=sys.stderr,
        )
        return 1
    except (URLError, OSError, ValueError, RuntimeError) as exc:
        print(f"Unable to start GPU pipelines: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
