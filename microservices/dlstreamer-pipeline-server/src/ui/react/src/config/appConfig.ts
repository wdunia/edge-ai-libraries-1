export const appConfig = {
  pipelineServerUrl: import.meta.env.VITE_PIPELINE_SERVER_URL,
  apiUrl: import.meta.env.VITE_API_URL,
  webrtcUrl: import.meta.env.VITE_WEBRTC_URL,
  prometheusUrl: import.meta.env.VITE_PROMETHEUS_URL,
  systemInfo: import.meta.env.VITE_SYSTEM_INFO ?? "",
  modelPath: import.meta.env.VITE_MODEL_PATH ?? "",
  defaultStreamUrl: import.meta.env.VITE_DEFAULT_STREAM_URL ?? "",
} as const;