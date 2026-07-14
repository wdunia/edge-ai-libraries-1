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
  defaultStreamUrl:
    import.meta.env.VITE_DEFAULT_STREAM_URL === "VITE_DEFAULT_STREAM_URL"
      ? "file:///home/pipeline-server/resources/videos/warehouse.avi"
      : (import.meta.env.VITE_DEFAULT_STREAM_URL ??
        "file:///home/pipeline-server/resources/videos/warehouse.avi"),
} as const;
