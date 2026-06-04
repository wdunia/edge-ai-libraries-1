export type RawMetricsEvent = {
  timestamp: string;
  cpu: number;
  gpu: number | "N/A";
  npu: number | "N/A";
  ram: number;
};

export type MetricsSnapshot = {
  timestamp: string;
  cpu: number;
  gpu: number | null;
  npu: number | null;
  ram: number;
};
