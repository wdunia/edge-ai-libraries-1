export const accent = {
  green: "#62CE58",
  orange: "#F3AD26",
  purple: "#C442CF",
  blue: "#00A3F6",
  red: "#E42222",
} as const;

export const bg = {
  base: "#070D2D",
  panel: "#0F1B43",
  tile: "#141F45",
  border: "#1E2A57",
} as const;

export type DeviceType = "GPU" | "NPU" | "CPU";

export const pipelineTypeConfig: Record<
  DeviceType,
  { color: string; bg: string; border: string }
> = {
  GPU: {
    color: accent.green,
    bg: "rgba(98,206,88,0.16)",
    border: "rgba(98,206,88,0.5)",
  },
  NPU: {
    color: accent.purple,
    bg: "rgba(196,66,207,0.16)",
    border: "rgba(196,66,207,0.5)",
  },
  CPU: {
    color: accent.blue,
    bg: "rgba(0,163,246,0.16)",
    border: "rgba(0,163,246,0.5)",
  },
};