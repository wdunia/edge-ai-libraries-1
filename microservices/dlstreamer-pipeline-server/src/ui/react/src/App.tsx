import { AppShell, Group, Text, Grid, Paper } from "@mantine/core";
import { LeftPanel } from "./components/LeftPanel";
import { bg } from "./styles/theme";
import { CameraGrid } from "./components/CameraGrid";

function App() {
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
            Layout: 1 4 9 16 25 36
            FPS: 742
            Streams: 9
          </Group>
        </Group>

        <Grid rowGap="md" columnGap="md">
          <Grid.Col span={2}>
            <Paper p="md" h={700} radius="md" bg={bg.panel}>
              <LeftPanel />
            </Paper>
          </Grid.Col>

          <Grid.Col span={10}>
            <Paper p="md" h={700} radius="md" bg={bg.panel}>
              <CameraGrid layoutMode={25} />
            </Paper>
          </Grid.Col>

          <Grid.Col span={12}>
            <Paper p="md" h={260} radius="md" bg={bg.panel}>
              Metrics
            </Paper>
          </Grid.Col>
        </Grid>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;