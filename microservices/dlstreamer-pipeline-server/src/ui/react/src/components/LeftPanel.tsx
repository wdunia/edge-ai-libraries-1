import { Button, Stack, Text, TextInput } from "@mantine/core";
import { bg, pipelineTypeConfig, type DeviceType } from "../styles/theme";

const devices: DeviceType[] = ["GPU", "NPU", "CPU"];

export function LeftPanel() {
    return (
        <Stack gap="md">
            <Text size="lg" fw={900} lts="0.08em">
                Add New Stream
            </Text>

            <Stack gap="sm">
                <StyledTextInput
                    label="Stream Name"
                    placeholder="CAM-ENTRANCE-01"
                />

                <StyledTextInput
                    label="Stream URL"
                    placeholder="webrtc://192.168.0.15/live"
                />
            </Stack>

            <Stack gap="xs" mt={4}>
                {devices.map((device) => (
                    <PipelineButton key={device} device={device} />
                ))}
            </Stack>
        </Stack>
    );
}

function StyledTextInput({
    label,
    placeholder,
}: {
    label: string;
    placeholder: string;
}) {
    return (
        <TextInput
            label={label}
            placeholder={placeholder}
            styles={{
                label: {
                    marginBottom: 5,
                    fontSize: 10,
                    textTransform: "uppercase",
                    letterSpacing: "0.13em",
                    color: "rgba(255,255,255,0.5)",
                },
                input: {
                    borderRadius: 4,
                    border: `1px solid ${bg.border}`,
                    background: bg.tile,
                    color: "white",
                    fontSize: 13,
                },
            }}
        />
    );
}

function PipelineButton({ device }: { device: DeviceType }) {
    const config = pipelineTypeConfig[device];

    return (
        <Button
            fullWidth
            radius={4}
            styles={{
                root: {
                    height: 38,
                    background: config.bg,
                    color: config.color,
                    border: `1px solid ${config.border}`,
                    fontSize: 12,
                    fontWeight: 900,
                    textTransform: "uppercase",
                    letterSpacing: "0.13em",
                },
            }}
        >
            Add pipeline ({device})
        </Button>
    );
}