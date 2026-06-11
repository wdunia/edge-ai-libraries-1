export type GpuMetrics = {
  bcs: number | null;
  ccs: number | null;
  rcs: number | null;
  vcs: number | null;
  vecs: number | null;
};

export type RawGpuMetrics = {
  bcs: number | "N/A";
  ccs: number | "N/A";
  rcs: number | "N/A";
  vcs: number | "N/A";
  vecs: number | "N/A";
};

export type RawMetricsEvent = {
  timestamp: string;
  cpu: number | "N/A";
  gpu: RawGpuMetrics;
  npu: number | "N/A";
  ram: number | "N/A";
};

export type MetricsSnapshot = {
  timestamp: string;
  cpu: number | null;
  gpu: GpuMetrics;
  npu: number | null;
  ram: number | null;
};