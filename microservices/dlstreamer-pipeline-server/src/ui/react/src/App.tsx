import { AppShell, Group, Text, Box, Grid, Paper, Button } from "@mantine/core";
import { LeftPanel } from "./components/LeftPanel";
import { accent, bg, type DeviceType } from "./styles/theme";
import { CameraGrid } from "./components/CameraGrid";
import { useEffect, useState } from "react";
import { MetricsPanel } from "./components/MetricsPanel";
import type { StreamTile } from "./components/CameraTile";
import {
  checkHealth,
  createCameraPipeline,
  deletePipeline,
  getPipelineStatus,
  getStreamInfo,
  type HealthStatus,
} from "./api/dlStreamerApi";
import { deleteAllPipelines } from "./api/dlStreamerApi";
import { appConfig } from "./config/appConfig";

type LayoutMode = 1 | 4 | 9 | 16 | 25 | 36;


const layoutModes: LayoutMode[] = [1, 4, 9, 16, 25, 36];

function App() {

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(9);
  const [streams, setStreams] = useState<StreamTile[]>([]);

  async function handleAddPipeline(data: {
    name: string;
    sourceUri: string;
    device: DeviceType;
    count: number;
  }) {
    const createdPipelines = await Promise.all(
      Array.from({ length: data.count }, async (_, index) => {
        const created = await createCameraPipeline(data.device, data.sourceUri, index);

        return {
          id: Date.now() + index,
          streamId: created.streamId,
          name:
            data.count === 1
              ? data.name
              : `${data.name}-${String(index + 1).padStart(2, "0")}`,
          type: data.device,
          fps: -1, // just an indicator to show incorrect value by default
          streamUrl: created.streamUrl,
          status: "RUNNING",
        } satisfies StreamTile;
      })
    );

    setStreams((previous) => [...previous, ...createdPipelines]);
  }

  useEffect(() => {
    checkHealth().then(setHealth);
  }, []);

  async function loadRunningStreams() {
    const pipelineStatuses = await getPipelineStatus();

    const visiblePipelines = pipelineStatuses.filter(
      (pipeline) => pipeline.state === "RUNNING" || pipeline.state === "QUEUED"
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

        setStreams((previous) =>
          previous.map((stream) => {
            if (!stream.streamId) {
              return stream;
            }

            const status = pipelineStatuses.find(
              (pipeline) => pipeline.id === stream.streamId
            );

            if (!status) {
              return stream;
            }

            return {
              ...stream,
              fps: Math.round(status.frame_fps ?? status.avg_fps ?? 0),
              status: status.state,
            };
          })
        );
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
    if (!stream.streamId) {
      setStreams((previous) => previous.filter((item) => item.id !== stream.id));
      return;
    }

    await deletePipeline(stream.streamId);

    setStreams((previous) => previous.filter((item) => item.id !== stream.id));
  }

  const totalFps = streams.reduce((sum, stream) => sum + stream.fps, 0);

  async function handleRemoveAllPipelines() {
    const pipelineStatuses = await getPipelineStatus();

    const runningPipelineIds = pipelineStatuses
      .filter(
        (pipeline) =>
          pipeline.state === "RUNNING" ||
          pipeline.state === "QUEUED"
      )
      .map((pipeline) => pipeline.id);

    await deleteAllPipelines(runningPipelineIds);

    setStreams([]);
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
      <AppShell.Main>
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
                      key={mode}
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
                      {mode}
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
        <Grid rowGap="md" columnGap="md">

          {/* Left Panel */}
          <Grid.Col span={2}>
            <Paper p="md" h={480} radius="md" bg={bg.panel}>
              <LeftPanel onAddPipeline={handleAddPipeline}
                onRemoveAllPipelines={handleRemoveAllPipelines} />
            </Paper>
          </Grid.Col>

          {/* Right Grid */}
          <Grid.Col span={10}>
            <Paper p="md" h={480} radius="md" bg={bg.panel}>
              <CameraGrid layoutMode={layoutMode}
                streams={streams}
                onDeleteStream={handleDeleteStream}
              />
            </Paper>
          </Grid.Col>

          {/* Metrics Grid */}
          <Grid.Col span={12}>
            <Paper p="md" h={350} radius="md" bg={bg.panel}>
              <MetricsPanel />
            </Paper>
          </Grid.Col>
        </Grid>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;