import { useEffect, useState } from "react";
import { Box, Group, SimpleGrid, Stack, Text } from "@mantine/core";
import { subscribeToMetrics } from "../api/metricsApi";
import type { MetricsSnapshot } from "../types/metrics";
import { accent, bg } from "../styles/theme";

const chartData = [
    { cpu: 42, npu: 28, fps: 250, ram: 44 },
    { cpu: 45, npu: 32, fps: 260, ram: 48 },
    { cpu: 43, npu: 30, fps: 270, ram: 47 },
    { cpu: 48, npu: 34, fps: 275, ram: 52 },
    { cpu: 46, npu: 35, fps: 280, ram: 51 },
    { cpu: 50, npu: 38, fps: 290, ram: 55 },
    { cpu: 58, npu: 44, fps: 300, ram: 57 },
];

const gpuData = [
    { bcs: 72, rcs: 81, ccs: 68, vcs: 55, vecs: 64 },
    { bcs: 75, rcs: 84, ccs: 71, vcs: 58, vecs: 67 },
    { bcs: 78, rcs: 86, ccs: 73, vcs: 60, vecs: 70 },
    { bcs: 76, rcs: 88, ccs: 75, vcs: 62, vecs: 72 },
    { bcs: 80, rcs: 90, ccs: 77, vcs: 64, vecs: 74 },
    { bcs: 82, rcs: 91, ccs: 79, vcs: 66, vecs: 76 },
    { bcs: 84, rcs: 93, ccs: 81, vcs: 69, vecs: 78 },
];

type AreaChartProps = {
    values: number[];
    color: string;
    gradientId: string;
};

function AreaChart({ values, color, gradientId }: AreaChartProps) {
    const safeValues = values.length > 1 ? values : [0, 0];

    const min = Math.min(...safeValues);
    const max = Math.max(...safeValues);
    const range = max - min || 1;

    const points = safeValues.map((value, index) => {
        const x = (index / (safeValues.length - 1)) * 300;
        const y = 8 + (1 - (value - min) / range) * 110;

        return [x, y];
    });

    const linePath = points
        .map(([x, y], index) => {
            if (index === 0) {
                return `M${x},${y}`;
            }

            const [previousX, previousY] = points[index - 1];
            const controlX = (previousX + x) / 2;

            return `C${controlX},${previousY} ${controlX},${y} ${x},${y}`;
        })
        .join(" ");

    const areaPath = `${linePath} L300,130 L0,130 Z`;

    return (
        <svg
            viewBox="0 0 300 130"
            preserveAspectRatio="none"
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
            <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.65" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>

            <path d={areaPath} fill={`url(#${gradientId})`} />
            <path
                d={linePath}
                fill="none"
                stroke={color}
                strokeWidth="2.5"
                strokeLinecap="round"
            />
        </svg>
    );
}

function MetricTile({
    title,
    value,
    color,
    values,
}: {
    title: string;
    value: string;
    color: string;
    values: number[];
}) {
    return (
        <Box
            style={{
                position: "relative",
                height: 130,
                overflow: "hidden",
                borderRadius: 6,
                border: `1px solid ${bg.border}`,
                background: bg.tile,
            }}
        >
            <AreaChart values={values} color={color} gradientId={`area-${title}`} />

            <Box style={{ position: "absolute", left: 16, top: 12, zIndex: 1 }}>
                <Text size="xs" fw={700} tt="uppercase" lts="0.22em" c="dimmed">
                    {title}
                </Text>

                <Text mt={4} size="xl" fw={900} c={color}>
                    {value}
                </Text>
            </Box>
        </Box>
    );
}

function GpuEnginesChart() {
    const lines = [
        { key: "bcs", label: "BCS", color: accent.green },
        { key: "rcs", label: "RCS", color: accent.blue },
        { key: "ccs", label: "CCS", color: accent.purple },
        { key: "vcs", label: "VCS", color: accent.orange },
        { key: "vecs", label: "VECS", color: accent.red },
    ] as const;

    const allValues = lines.flatMap((line) =>
        gpuData.map((item) => item[line.key])
    );

    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const range = max - min || 1;

    return (
        <Box
            style={{
                position: "relative",
                height: 170,
                overflow: "hidden",
                borderRadius: 6,
                border: `1px solid ${bg.border}`,
                background: bg.tile,
            }}
        >
            <svg
                viewBox="0 0 800 170"
                preserveAspectRatio="none"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            >
                {lines.map((line) => {
                    const points = gpuData.map((item, index) => {
                        const x = 8 + (index / (gpuData.length - 1)) * 784;
                        const y = 44 + (1 - (item[line.key] - min) / range) * 118;

                        return [x, y];
                    });

                    const path = points
                        .map(([x, y], index) => {
                            if (index === 0) {
                                return `M${x},${y}`;
                            }

                            const [previousX, previousY] = points[index - 1];
                            const controlX = (previousX + x) / 2;

                            return `C${controlX},${previousY} ${controlX},${y} ${x},${y}`;
                        })
                        .join(" ");

                    return (
                        <path
                            key={line.key}
                            d={path}
                            fill="none"
                            stroke={line.color}
                            strokeWidth="2.5"
                            strokeLinecap="round"
                        />
                    );
                })}
            </svg>

            <Box style={{ position: "absolute", left: 16, top: 12, zIndex: 1 }}>
                <Text size="xs" fw={700} tt="uppercase" lts="0.22em" c="dimmed">
                    GPU Engines
                </Text>

                <Text mt={4} size="xl" fw={900} c={accent.purple}>
                    93%
                </Text>
            </Box>

            <Group gap="md"
                style={{ position: "absolute", right: 16, top: 16, zIndex: 1 }}>
                {lines.map((line) => (
                    <Text
                        key={line.key}
                        size="xs"
                        fw={800}
                        tt="uppercase"
                        lts="0.16em"
                        c={line.color}
                    >
                        {line.label}
                    </Text>
                ))}
            </Group>
        </Box>
    );
}

export function MetricsPanel() {
    const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
    const [history, setHistory] = useState({
        cpu: [0],
        npu: [0],
        fps: [0],
        ram: [0],
    });

    useEffect(() => {
        return subscribeToMetrics((nextMetrics) => {
            setMetrics(nextMetrics);

            setHistory((previous) => ({
                cpu: [...previous.cpu, nextMetrics.cpu].slice(-30),
                npu: previous.npu,
                fps: previous.fps,
                ram: [...previous.ram, nextMetrics.ram].slice(-30),
            }));
        }, console.error);
    }, []);

    const cpuValue = metrics ? `${metrics.cpu.toFixed(1)}%` : "N/A";
    const npuValue = metrics?.npu === null || !metrics ? "N/A" : `${metrics.npu.toFixed(1)}%`;
    const ramValue = metrics ? `${metrics.ram.toFixed(1)}%` : "N/A";

    return (
        <Stack gap="xs">
            <SimpleGrid cols={4} spacing="md">
                <MetricTile title="CPU" value={cpuValue} color={accent.blue} values={history.cpu} />
                <MetricTile title="NPU" value={npuValue} color={accent.purple} values={history.npu} />
                <MetricTile title="FPS" value="N/A" color={accent.green} values={history.fps} />
                <MetricTile title="RAM" value={ramValue} color={accent.orange} values={history.ram} />
            </SimpleGrid>

            <GpuEnginesChart />
        </Stack>
    );
}