import { useEffect, useState } from "react";
import { Box, SimpleGrid, Text } from "@mantine/core";
import { subscribeToMetrics } from "../api/metricsApi";
import type { MetricsSnapshot } from "../types/metrics";
import { accent, bg } from "../styles/theme";
import { getPipelineStatus } from "../api/pipelineStatusApi";


type AreaChartProps = {
    values: number[];
    color: string;
    gradientId: string;
    minValue?: number;
    maxValue?: number;
};

function AreaChart({ values, color, gradientId, minValue, maxValue }: AreaChartProps) {
    const safeValues = values.length > 1 ? values : [0, 0];

    const min = minValue ?? Math.min(...safeValues);
    const max = maxValue ?? Math.max(...safeValues);
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
    titleColor = "dimmed",
    chartMin,
    chartMax,
}: {
    title: string;
    value: string;
    color: string;
    values: number[];
    titleColor?: string;
    chartMin?: number;
    chartMax?: number;
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
            <AreaChart
                values={values}
                color={color}
                gradientId={`area-${title}`}
                minValue={chartMin}
                maxValue={chartMax}
            />

            <Box style={{ position: "absolute", left: 16, top: 12, zIndex: 1 }}>
                <Text size="xs" fw={700} tt="uppercase" lts="0.22em" c={titleColor}>
                    {title}
                </Text>

                <Text mt={4} size="xl" fw={900} c={color}>
                    {value}
                </Text>
            </Box>
        </Box>
    );
}

export function MetricsPanel() {
    const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
    const [history, setHistory] = useState({
        gpu: [0],
        cpu: [0],
        npu: [0],
        fps: [0],
    });

    useEffect(() => {
        let isMounted = true;

        async function refreshFps() {
            try {
                const pipelines = await getPipelineStatus();

                if (!isMounted) {
                    return;
                }

                const runningPipelines = pipelines.filter(
                    (pipeline) => pipeline.state === "RUNNING"
                );

                const totalFps = runningPipelines.reduce(
                    (sum, pipeline) => sum + (pipeline.frame_fps ?? 0),
                    0
                );

                setHistory((previous) => ({
                    ...previous,
                    fps: [...previous.fps, totalFps].slice(-30),
                }));
            } catch (error) {
                console.error(error);
            }
        }

        refreshFps();

        const intervalId = window.setInterval(refreshFps, 1000);

        return () => {
            isMounted = false;
            window.clearInterval(intervalId);
        };
    }, []);

    useEffect(() => {
        return subscribeToMetrics((nextMetrics) => {
            setMetrics(nextMetrics);

            setHistory((previous) => ({
                gpu: [...previous.gpu, nextMetrics.gpu ?? 0].slice(-30),
                cpu: [...previous.cpu, nextMetrics.cpu ?? 0].slice(-30),
                npu: [...previous.npu, nextMetrics.npu ?? 0].slice(-30),
                fps: previous.fps,
            }));
        }, console.error);
    }, []);

    const formatPercent = (value: number | null | undefined) =>
        value == null ? "N/A" : `${value.toFixed(1)}%`;

    const gpuValue = formatPercent(metrics?.gpu);
    const cpuValue = formatPercent(metrics?.cpu);
    const npuValue = formatPercent(metrics?.npu);
    const fpsValue =
        history.fps.length > 0
            ? Math.round(history.fps.at(-1) ?? 0).toString()
            : "N/A";

    return (
        <Box style={{ height: "100%", minHeight: 0 }}>
            <SimpleGrid cols={4} spacing="md">
                <MetricTile
                    title="GPU"
                    value={gpuValue}
                    color={accent.green}
                    values={history.gpu}
                    titleColor="white"
                    chartMin={0}
                    chartMax={100}
                />
                <MetricTile
                    title="NPU"
                    value={npuValue}
                    color={accent.purple}
                    values={history.npu}
                    titleColor="white"
                    chartMin={0}
                    chartMax={100}
                />
                <MetricTile
                    title="CPU"
                    value={cpuValue}
                    color={accent.blue}
                    values={history.cpu}
                    titleColor="white"
                    chartMin={0}
                    chartMax={100}
                />
                <MetricTile title="FPS" value={fpsValue} color={accent.green} values={history.fps} />
            </SimpleGrid>
        </Box>
    );
}

