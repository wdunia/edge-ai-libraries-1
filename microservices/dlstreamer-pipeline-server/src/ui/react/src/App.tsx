import { AppShell, Group, Text, Box, Grid, Paper, Button } from "@mantine/core";
import { LeftPanel } from "./components/LeftPanel";
import { accent, bg } from "./styles/theme";
import { CameraGrid } from "./components/CameraGrid";
import { useEffect, useState } from "react";
import { checkHealth, type HealthStatus } from "./api/dlStreamerApi";
import { MetricsPanel } from "./components/MetricsPanel";

type LayoutMode = 1 | 4 | 9 | 16 | 25 | 36;
const layoutModes: LayoutMode[] = [1, 4, 9, 16, 25, 36];

function App() {

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(9);

  useEffect(() => {
    checkHealth().then(setHealth);
  }, []);

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
                    742
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
                    9
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
              <LeftPanel />
            </Paper>
          </Grid.Col>

          {/* Right Grid */}
          <Grid.Col span={10}>
            <Paper p="md" h={480} radius="md" bg={bg.panel}>
              <CameraGrid layoutMode={layoutMode} />
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