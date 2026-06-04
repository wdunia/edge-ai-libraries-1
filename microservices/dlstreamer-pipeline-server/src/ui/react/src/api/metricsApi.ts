import { appConfig } from "../config/appConfig";
import type { MetricsSnapshot, RawMetricsEvent } from "../types/metrics";

function normalizeMetricValue(value: number | "N/A"): number | null {
  return value === "N/A" ? null : value;
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
      cpu: raw.cpu,
      gpu: normalizeMetricValue(raw.gpu),
      npu: normalizeMetricValue(raw.npu),
      ram: raw.ram,
    });
  };

  eventSource.onerror = (error) => {
    onError?.(error);
  };

  return () => {
    eventSource.close();
  };
}