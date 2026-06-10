import { appConfig } from "../config/appConfig";
import type { MetricsSnapshot, RawMetricsEvent, RawGpuMetrics } from "../types/metrics";

function normalizeMetricValue(value: number | "N/A"): number | null {
  return value === "N/A" ? null : value;
}

function normalizeGpuMetrics(gpu: RawGpuMetrics) {
  return {
    bcs: normalizeMetricValue(gpu.bcs),
    ccs: normalizeMetricValue(gpu.ccs),
    rcs: normalizeMetricValue(gpu.rcs),
    vcs: normalizeMetricValue(gpu.vcs),
    vecs: normalizeMetricValue(gpu.vecs),
  };
}

export function subscribeToMetrics(
  onMetrics: (metrics: MetricsSnapshot) => void,
  onError?: (error: Event) => void
) {
  const eventSource = new EventSource(`${appConfig.apiUrl}/metrics`);

  eventSource.onmessage = (event) => {
    const raw = JSON.parse(event.data) as RawMetricsEvent;

    onMetrics({
      timestamp: raw.timestamp,
      cpu: normalizeMetricValue(raw.cpu),
      gpu: normalizeGpuMetrics(raw.gpu),
      npu: normalizeMetricValue(raw.npu),
      ram: normalizeMetricValue(raw.ram),
    });
  };

  eventSource.onerror = (error) => {
    onError?.(error);
  };

  return () => {
    eventSource.close();
  };
}