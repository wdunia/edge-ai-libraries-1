import { Button, Stack, Text, TextInput } from "@mantine/core";
import { accent } from "../styles/theme";

export function LeftPanel() {
  return (
    <Stack gap="md">
      <div>
        <Text size="lg" fw={900} tt="uppercase" lts="0.08em">
          Add new stream
        </Text>
      </div>

      <Stack gap="sm">
        <TextInput
          label="Stream name"
          placeholder="CAM-ENTRANCE-01"
        />

        <TextInput
          label="Stream URL"
          placeholder="webrtc://192.168.0.15/live"
        />
      </Stack>

      <Stack gap="xs" mt="xs">
        <Button fullWidth color={accent.green}>
          Add pipeline GPU
        </Button>

        <Button fullWidth color={accent.purple}>
          Add pipeline NPU
        </Button>

        <Button fullWidth color={accent.blue}>
          Add pipeline CPU
        </Button>
      </Stack>
    </Stack>
  );
}