function resolveEnvValue(value: string | undefined, placeholder: string, fallback: string) {
  if (!value || value === placeholder) {
    return fallback;
  }
  return value;
}

const defaultStreamUrlFile = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_STREAM_URL_FILE,
  "VITE_DEFAULT_STREAM_URL_FILE",
  "file:///home/pipeline-server/resources/videos/warehouse.avi"
);

const defaultStreamUrlRtsp = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_STREAM_URL_RTSP,
  "VITE_DEFAULT_STREAM_URL_RTSP",
  "rtsp://host.docker.internal:8554/camera0"
);

const defaultSourceModeRaw = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_SOURCE_MODE,
  "VITE_DEFAULT_SOURCE_MODE",
  "file"
).toLowerCase();

const defaultSourceMode =
  defaultSourceModeRaw === "rtsp" || defaultSourceModeRaw === "file"
    ? defaultSourceModeRaw
    : "file";

const defaultInferenceResolutionRaw = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_INFERENCE_RESOLUTION,
  "VITE_DEFAULT_INFERENCE_RESOLUTION",
  "2/3"
);

const defaultInferenceResolution =
  defaultInferenceResolutionRaw === "FULL" ||
  defaultInferenceResolutionRaw === "2/3" ||
  defaultInferenceResolutionRaw === "1/2" ||
  defaultInferenceResolutionRaw === "1/3"
    ? defaultInferenceResolutionRaw
    : "2/3";

const defaultInstanceCountRaw = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_INSTANCE_COUNT,
  "VITE_DEFAULT_INSTANCE_COUNT",
  "1"
);

const defaultInferenceIntervalRaw = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_INFERENCE_INTERVAL,
  "VITE_DEFAULT_INFERENCE_INTERVAL",
  "1"
);

const defaultModelSharingRaw = resolveEnvValue(
  import.meta.env.VITE_DEFAULT_MODEL_SHARING,
  "VITE_DEFAULT_MODEL_SHARING",
  "false"
).toLowerCase();

export const appConfig = {
  pipelineServerUrl:
    import.meta.env.VITE_PIPELINE_SERVER_URL === "VITE_PIPELINE_SERVER_URL"
      ? "http://127.0.0.1:8080"
      : import.meta.env.VITE_PIPELINE_SERVER_URL,
  apiUrl:
    import.meta.env.VITE_API_URL === "VITE_API_URL"
      ? "http://127.0.0.1:8888"
      : import.meta.env.VITE_API_URL,
  webrtcUrl:
    import.meta.env.VITE_WEBRTC_URL === "VITE_WEBRTC_URL"
      ? "http://127.0.0.1:8889"
      : import.meta.env.VITE_WEBRTC_URL,
  prometheusUrl: import.meta.env.VITE_PROMETHEUS_URL,
  systemInfo:
    import.meta.env.VITE_SYSTEM_INFO === "VITE_SYSTEM_INFO"
      ? ""
      : (import.meta.env.VITE_SYSTEM_INFO ?? ""),
  modelPath:
    import.meta.env.VITE_MODEL_PATH === "VITE_MODEL_PATH"
      ? "/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml"
      : (import.meta.env.VITE_MODEL_PATH ??
        "/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml"),
  defaultStreamName: resolveEnvValue(
    import.meta.env.VITE_DEFAULT_STREAM_NAME,
    "VITE_DEFAULT_STREAM_NAME",
    "CAM-01"
  ),
  defaultSourceMode,
  defaultStreamUrlFile,
  defaultStreamUrlRtsp,
  defaultStreamUrl:
    defaultSourceMode === "rtsp" ? defaultStreamUrlRtsp : defaultStreamUrlFile,
  defaultInstanceCount: defaultInstanceCountRaw,
  defaultInferenceInterval: defaultInferenceIntervalRaw,
  defaultInferenceResolution,
  defaultModelSharing:
    defaultModelSharingRaw === "true" || defaultModelSharingRaw === "1",
} as const;
