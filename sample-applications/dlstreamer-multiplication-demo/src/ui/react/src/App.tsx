import { AppShell, Group, Text, Box, Paper, Button } from "@mantine/core";
import { LeftPanel } from "./components/LeftPanel";
import { accent, bg, type DeviceType } from "./styles/theme";
import { CameraGrid } from "./components/CameraGrid";
import { useEffect, useRef, useState } from "react";
import { MetricsPanel } from "./components/MetricsPanel";
import type { StreamTile } from "./components/CameraTile";
import {
  checkHealth,
  createCameraPipeline,
  createCameraPipelinesParallel,
  deletePipeline,
  getPipelineStatus,
  getStreamInfo,
  type HealthStatus,
  type ResolutionPreset,
} from "./api/dlStreamerApi";
import { deleteAllPipelines } from "./api/dlStreamerApi";
import { subscribeToMetrics } from "./api/metricsApi";
import { appConfig } from "./config/appConfig";

type LayoutMode = "auto" | 1 | 2 | 3 | 4 | 5 | 6 | 7;


const layoutModes: LayoutMode[] = ["auto", 1, 2, 3, 4, 5, 6, 7];

function App() {

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("auto");
  const [streams, setStreams] = useState<StreamTile[]>([]);
  const [hostRamSummary, setHostRamSummary] = useState<string>("N/A");
  const streamsRef = useRef<StreamTile[]>([]);
  const hiddenPipelineIdsRef = useRef<Set<string>>(new Set());

  async function handleAddPipeline(data: {
    name: string;
    sourceUri: string;
    device: DeviceType;
    count: number;
    resolutionPreset: ResolutionPreset;
    inferenceInterval: number;
    modelSharing: boolean;
  }) {
    const createdPipelines: StreamTile[] = [];

    // Use parallel creation for multiple pipelines, sequential for single
    const created =
      data.count === 1
        ? [
            await createCameraPipeline(
              data.device,
              data.sourceUri,
              {
                resolutionPreset: data.resolutionPreset,
                inferenceInterval: data.inferenceInterval,
                modelSharing: data.modelSharing,
              }
            ),
          ]
        : await createCameraPipelinesParallel(
            Array.from({ length: data.count }, () => ({
              device: data.device,
              sourceUri: data.sourceUri,
              options: {
                resolutionPreset: data.resolutionPreset,
                inferenceInterval: data.inferenceInterval,
                modelSharing: data.modelSharing,
              },
            }))
          );

    created.forEach((pipeline, index) => {
      createdPipelines.push({
        id: Date.now() + index,
        streamId: pipeline.streamId,
        name:
          data.count === 1
            ? data.name
            : `${data.name}-${String(index + 1).padStart(2, "0")}`,
        type: data.device,
        fps: -1,
        streamUrl: pipeline.streamUrl,
        status: "QUEUED",
      });
    });

    setStreams((previous) => [...previous, ...createdPipelines]);
  }

  useEffect(() => {
    checkHealth().then(setHealth);
  }, []);

  useEffect(() => {
    streamsRef.current = streams;
  }, [streams]);

  useEffect(() => {
    return subscribeToMetrics(
      (metrics) => {
        if (metrics.ram.usedGb != null && metrics.ram.totalGb != null) {
          setHostRamSummary(
            `${Math.round(metrics.ram.usedGb)}/${Math.round(metrics.ram.totalGb)} GB`
          );
          return;
        }

        setHostRamSummary("N/A");
      },
      console.error
    );
  }, []);

  async function loadRunningStreams() {
    const pipelineStatuses = await getPipelineStatus();

    const visiblePipelines = pipelineStatuses.filter(
      (pipeline) =>
        (pipeline.state === "RUNNING" || pipeline.state === "QUEUED") &&
        !hiddenPipelineIdsRef.current.has(pipeline.id)
    );

    const restoredStreams = await Promise.all(
      visiblePipelines.map(async (pipeline, index) => {
        const streamInfo =
          pipeline.state === "RUNNING"
            ? await getStreamInfo(pipeline.id)
            : { streamUrl: null, device: null };

        return {
          id: index + 1,
          streamId: pipeline.id,
          name: `CAM-${String(index + 1).padStart(2, "0")}`,
          type: streamInfo.device ?? "CPU",
          fps: Math.round(pipeline.frame_fps ?? pipeline.avg_fps ?? 0),
          streamUrl: streamInfo.streamUrl ?? undefined,
          status: pipeline.state,
        };
      })
    );

    setStreams(restoredStreams);
  }

  useEffect(() => {
    loadRunningStreams().catch(console.error);
  }, []);

  useEffect(() => {
    async function refreshStreamFps() {
      try {
        const pipelineStatuses = await getPipelineStatus();
        const streamIdsNeedingUrl = streamsRef.current
          .filter(
            (stream) =>
              !stream.streamUrl &&
              !!stream.streamId &&
              !hiddenPipelineIdsRef.current.has(stream.streamId)
          )
          .filter((stream) => {
            const status = pipelineStatuses.find(
              (pipeline) => pipeline.id === stream.streamId
            );

            return status?.state === "RUNNING";
          })
          .map((stream) => stream.streamId as string);

        setStreams((previous) =>
          previous.map((stream) => {
            if (!stream.streamId) {
              return stream;
            }

            const status = pipelineStatuses.find(
              (pipeline) => pipeline.id === stream.streamId
            );

            if (hiddenPipelineIdsRef.current.has(stream.streamId)) {
              return stream;
            }

            if (!status) {
              return stream;
            }

            return {
              ...stream,
              fps: Math.round(status.frame_fps ?? status.avg_fps ?? 0),
              status: status.state,
              streamUrl:
                status.state === "RUNNING" || status.state === "QUEUED"
                  ? stream.streamUrl
                  : undefined,
            };
          })
        );

        if (streamIdsNeedingUrl.length > 0) {
          const uniqueStreamIds = [...new Set(streamIdsNeedingUrl)];
          const streamInfoEntries = await Promise.all(
            uniqueStreamIds.map(async (streamId) => {
              const streamInfo = await getStreamInfo(streamId);
              return [streamId, streamInfo] as const;
            })
          );

          const streamInfoMap = new Map(streamInfoEntries);

          setStreams((previous) =>
            previous.map((stream) => {
              if (!stream.streamId || stream.streamUrl) {
                return stream;
              }

              const streamInfo = streamInfoMap.get(stream.streamId);
              if (!streamInfo?.streamUrl) {
                return stream;
              }

              return {
                ...stream,
                streamUrl: streamInfo.streamUrl,
                type: streamInfo.device ?? stream.type,
              };
            })
          );
        }
      } catch (error) {
        console.error(error);
      }
    }

    refreshStreamFps();

    const intervalId = window.setInterval(refreshStreamFps, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  async function handleDeleteStream(stream: StreamTile) {
    const previousStreams = streamsRef.current;
    if (stream.streamId) {
      hiddenPipelineIdsRef.current.add(stream.streamId);
    }
    setStreams((previous) => previous.filter((item) => item.id !== stream.id));

    if (!stream.streamId) {
      return;
    }

    try {
      await deletePipeline(stream.streamId);
    } catch (error) {
      console.error(error);
      hiddenPipelineIdsRef.current.delete(stream.streamId);
      setStreams(previousStreams);
      return;
    }

    hiddenPipelineIdsRef.current.delete(stream.streamId);
  }

  const totalFps = streams.reduce((sum, stream) => sum + stream.fps, 0);

  async function handleRemoveAllPipelines() {
    const previousStreams = streamsRef.current;
    const visiblePipelineIds = previousStreams
      .map((stream) => stream.streamId)
      .filter((streamId): streamId is string => Boolean(streamId));

    for (const pipelineId of visiblePipelineIds) {
      hiddenPipelineIdsRef.current.add(pipelineId);
    }

    setStreams([]);

    let pipelineIdsToDelete = visiblePipelineIds;

    if (pipelineIdsToDelete.length === 0) {
      const pipelineStatuses = await getPipelineStatus();
      pipelineIdsToDelete = pipelineStatuses
        .filter(
          (pipeline) =>
            pipeline.state === "RUNNING" ||
            pipeline.state === "QUEUED"
        )
        .map((pipeline) => pipeline.id);

      for (const pipelineId of pipelineIdsToDelete) {
        hiddenPipelineIdsRef.current.add(pipelineId);
      }
    }

    try {
      await deleteAllPipelines(pipelineIdsToDelete);
    } catch (error) {
      console.error(error);
    } finally {
      hiddenPipelineIdsRef.current.clear();
      await loadRunningStreams().catch((loadError) => {
        console.error(loadError);
        setStreams(previousStreams);
      });
    }
  }

  return (
    <AppShell
      padding="md"
      styles={{
        main: {
          background: bg.base,
          minHeight: "100vh",
          color: "white",
        },
      }}
    >
      <AppShell.Main
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: "calc(100vh - 2 * var(--mantine-spacing-md))",
        }}
      >
        {/* Header */}
        <Group justify="space-between" align="stretch" mb="md" wrap="nowrap">
          <Paper
            px="md"
            py="sm"
            radius="md"
            bg={bg.panel}
            withBorder
            style={{
              borderColor: bg.border,
              height: 62,
              display: "flex",
              alignItems: "center",
            }}
          >
            <Group gap="sm" wrap="nowrap">
              <Box
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 6,
                  background: "rgba(0,163,246,0.15)",
                  border: `1px solid ${bg.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: accent.blue,
                  fontWeight: 900,
                  fontSize: 22,
                }}
              >
                ≋
              </Box>

              <div>
                <Text size="xl" fw={900} lts="0.08em" lh={1}>
                  Deep Learning Streamer
                </Text>

                <Text size="xs" c="dimmed" lts="0.16em" mt={4}>
                  VIDEO PIPELINE MULTIPLICATION DEMO
                </Text>
              </div>
            </Group>
          </Paper>

          <Paper
            px="md"
            py="sm"
            radius="md"
            bg={bg.panel}
            withBorder
            style={{
              borderColor: bg.border,
              height: 62,
              display: "flex",
              alignItems: "center",
            }}
          >
            <Text
              size="xs"
              c="white"
              mt={2}
            >
              {appConfig.systemInfo}
            </Text>
          </Paper>

          <Group gap="md" align="stretch" wrap="nowrap">
            <Paper
              px="md"
              py="sm"
              radius="md"
              bg={bg.panel}
              withBorder
              style={{
                borderColor: bg.border,
                height: 62,
                display: "flex",
                alignItems: "center",
              }}
            >
              <Group gap="sm" wrap="nowrap">
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.18em">
                  Layout
                </Text>

                <Group gap={8} wrap="nowrap">
                  {layoutModes.map((mode) => (
                    <Button
                      key={String(mode)}
                      size="xs"
                      variant={layoutMode === mode ? "filled" : "outline"}
                      color="blue"
                      onClick={() => setLayoutMode(mode)}
                      styles={{
                        root: {
                          height: 34,
                          minWidth: 38,
                          paddingInline: 10,
                          fontWeight: 900,
                        },
                      }}
                    >
                      {mode === "auto" ? "Auto" : mode}
                    </Button>
                  ))}
                </Group>
              </Group>
            </Paper>

            <Paper
              px="md"
              py="sm"
              radius="md"
              bg={bg.panel}
              withBorder
              style={{
                borderColor: bg.border,
                height: 62,
                display: "flex",
                alignItems: "center",
              }}
            >
              <Group gap="lg" wrap="nowrap">
                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.18em">
                    Total FPS
                  </Text>

                  <Text size="xl" fw={900} c={accent.green} lh={1.1}>
                    {totalFps}
                  </Text>
                </div>

                <Box
                  style={{
                    width: 1,
                    height: 38,
                    background: bg.border,
                  }}
                />

                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.18em">
                    Streams
                  </Text>

                  <Text size="xl" fw={900} c={accent.blue} lh={1.1}>
                    {streams.length}
                  </Text>
                </div>

                <Box
                  style={{
                    width: 1,
                    height: 38,
                    background: bg.border,
                  }}
                />

                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.18em">
                    Host RAM
                  </Text>

                  <Text size="xl" fw={900} c={accent.orange} lh={1.1}>
                    {hostRamSummary}
                  </Text>
                </div>

                <Box
                  style={{
                    width: 1,
                    height: 38,
                    background: bg.border,
                  }}
                />

                <div>
                  <Text size="xs" fw={700} c="dimmed" tt="uppercase" lts="0.18em">
                    API
                  </Text>

                  <Text
                    size="sm"
                    fw={900}
                    c={health?.ok ? accent.green : accent.red}
                    lh={1.2}
                  >
                    {health === null ? "CHECKING" : health.ok ? "HEALTHY" : "DOWN"}
                  </Text>
                </div>
              </Group>
            </Paper>
          </Group>
        </Group>

        {/* Body content */}
        <Box
          style={{
            flex: "1 1 0",
            minHeight: 0,
            display: "grid",
            gridTemplateRows: "minmax(0, 1fr) auto",
            gap: "var(--mantine-spacing-md)",
          }}
        >
          <Box
            style={{
              minHeight: 0,
              display: "grid",
              gridTemplateColumns: "minmax(220px, 2fr) minmax(0, 10fr)",
              gap: "var(--mantine-spacing-md)",
            }}
          >
            {/* Left Panel */}
            <Paper p="md" radius="md" bg={bg.panel} style={{ minHeight: 0, overflow: "auto" }}>
              <LeftPanel onAddPipeline={handleAddPipeline}
                onRemoveAllPipelines={handleRemoveAllPipelines} />
            </Paper>

            {/* Right Grid */}
            <Paper p="md" radius="md" bg={bg.panel} style={{ minHeight: 0, overflow: "hidden" }}>
              <CameraGrid layoutMode={layoutMode}
                streams={streams}
                onDeleteStream={handleDeleteStream}
              />
            </Paper>
          </Box>

          {/* Metrics Grid */}
          <Paper p="md" radius="md" bg={bg.panel}>
            <MetricsPanel />
          </Paper>
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;
