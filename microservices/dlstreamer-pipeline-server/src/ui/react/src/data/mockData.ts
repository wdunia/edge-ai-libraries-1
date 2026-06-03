import type { DeviceType } from "../styles/theme";
import type { StreamItem } from "../types/stream";

export const chartData = [
  { cpu: 42, npu: 28, fps: 250 },
  { cpu: 45, npu: 32, fps: 260 },
  { cpu: 43, npu: 30, fps: 270 },
  { cpu: 48, npu: 34, fps: 275 },
  { cpu: 46, npu: 35, fps: 280 },
  { cpu: 50, npu: 38, fps: 290 },
  { cpu: 49, npu: 40, fps: 300 },
];

export const gpuData = [
  { bcs: 72, rcs: 81, ccs: 68, vcs: 55, vecs: 64 },
  { bcs: 75, rcs: 84, ccs: 71, vcs: 58, vecs: 67 },
  { bcs: 78, rcs: 86, ccs: 73, vcs: 60, vecs: 70 },
  { bcs: 76, rcs: 88, ccs: 75, vcs: 62, vecs: 72 },
  { bcs: 80, rcs: 90, ccs: 77, vcs: 64, vecs: 74 },
  { bcs: 82, rcs: 91, ccs: 79, vcs: 66, vecs: 76 },
  { bcs: 84, rcs: 93, ccs: 81, vcs: 69, vecs: 78 },
];

export function createMockStreams(count: number): StreamItem[] {
  return Array.from({ length: count }, (_, i) => {
    const type = ["GPU", "NPU", "CPU"][i % 3] as DeviceType;

    return {
      id: i + 1,
      name: `CAM-${String(i + 1).padStart(2, "0")}`,
      type,
      fps: 29 + Math.floor(Math.random() * 4),
      objects: Math.floor(Math.random() * 8),
    };
  });
}