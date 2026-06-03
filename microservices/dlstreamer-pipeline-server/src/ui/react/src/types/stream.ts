import type { DeviceType } from "../styles/theme";

export type StreamItem = {
  id: number;
  name: string;
  type: DeviceType;
  fps: number;
  objects: number;
};