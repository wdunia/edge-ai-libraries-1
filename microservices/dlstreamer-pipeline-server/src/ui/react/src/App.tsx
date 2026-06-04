import { AppShell, Group, Text, Badge, Grid, Paper } from "@mantine/core";
import { LeftPanel } from "./components/LeftPanel";
import { bg } from "./styles/theme";
import { CameraGrid } from "./components/CameraGrid";
import { useEffect, useState } from "react";
import { checkHealth, type HealthStatus } from "./api/dlStreamerApi";
import { MetricsPanel } from "./components/MetricsPanel";

function App() {

  const [health, setHealth] = useState<HealthStatus | null>(null);

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
        <Group justify="space-between" mb="md">
          <Group>
            <Text size="xl" fw={700}>
              Deep Learning Streamer
            </Text>
            <Text size="sm" fw={200}>
              VIDEO PIPELINE MULTIPLICATION DEMO
            </Text>
          </Group>
          <Group>
            <Badge color={health?.ok ? "green" : "red"} variant="light">
              API: {health === null ? "checking..." : health.ok ? "healthy" : "down"}
            </Badge>

            Layout: 1 4 9 16 25 36
            FPS: 742
            Streams: 9
          </Group>
        </Group>

        <Grid rowGap="md" columnGap="md">
          <Grid.Col span={2}>
            <Paper p="md" h={480} radius="md" bg={bg.panel}>
              <LeftPanel />
            </Paper>
          </Grid.Col>

          <Grid.Col span={10}>
            <Paper p="md" h={480} radius="md" bg={bg.panel}>
              <CameraGrid layoutMode={4} />
            </Paper>
          </Grid.Col>

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