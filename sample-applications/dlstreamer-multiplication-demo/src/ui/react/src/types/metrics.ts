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

export type RawRamMetrics = {
  percent: number;
  used_gb: number;
  total_gb: number;
};

export type RawMetricsEvent = {
  timestamp: string;
  cpu: number | "N/A";
  gpu: RawGpuMetrics;
  npu: number | "N/A";
  ram: RawRamMetrics;
};

export type RamMetrics = {
  percent: number | null;
  usedGb: number | null;
  totalGb: number | null;
};

export type MetricsSnapshot = {
  timestamp: string;
  cpu: number | null;
  gpu: GpuMetrics;
  npu: number | null;
  ram: RamMetrics;
};
