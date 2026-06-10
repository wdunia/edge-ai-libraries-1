import { useState } from "react";
import { Button, Stack, Text, TextInput } from "@mantine/core";
import { bg, pipelineTypeConfig, type DeviceType } from "../styles/theme";

const devices: DeviceType[] = ["GPU", "NPU", "CPU"];

type LeftPanelProps = {
    onAddPipeline: (data: {
        name: string;
        sourceUri: string;
        device: DeviceType;
        count: number;
    }) => Promise<void>;
};

export function LeftPanel({ onAddPipeline }: LeftPanelProps) {
    const [streamName, setStreamName] = useState("CAM-01");
    const [streamUrl, setStreamUrl] = useState("");
    const [isAdding, setIsAdding] = useState(false);
    const [streamCount, setStreamCount] = useState("1");

    async function handleAddPipeline(device: DeviceType) {
        const count = Math.min(Math.max(Number(streamCount) || 1, 1), 50);
        setIsAdding(true);

        try {
            await onAddPipeline({
                name: streamName,
                sourceUri: streamUrl,
                device,
                count: count,
            });
        } finally {
            setIsAdding(false);
        }
    }

    return (
        <Stack gap="md">
            <Text size="lg" fw={900} lts="0.08em">
                Add New Stream
            </Text>

            <Stack gap="sm">
                <StyledTextInput
                    label="Stream Name"
                    placeholder="CAM-ENTRANCE-01"
                    value={streamName}
                    onChange={setStreamName}
                />

                <StyledTextInput
                    label="Stream URL"
                    placeholder=""
                    value={streamUrl}
                    onChange={setStreamUrl}
                />
            </Stack>

            <Stack gap="xs" mt={4}>
                <StyledTextInput
                    label="Instances (1-50)"
                    placeholder="1"
                    value={streamCount}
                    onChange={setStreamCount}
                />
                {devices.map((device) => (
                    <PipelineButton
                        key={device}
                        device={device}
                        loading={isAdding}
                        onClick={() => handleAddPipeline(device)}
                    />
                ))}
            </Stack>
        </Stack>
    );
}

function StyledTextInput({
    label,
    placeholder,
    value,
    onChange,
}: {
    label: string;
    placeholder: string;
    value: string;
    onChange: (value: string) => void;
}) {
    return (
        <TextInput
            label={label}
            placeholder={placeholder}
            value={value}
            onChange={(event) => onChange(event.currentTarget.value)}
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

function PipelineButton({
    device,
    loading,
    onClick,
}: {
    device: DeviceType;
    loading: boolean;
    onClick: () => void;
}) {
    const config = pipelineTypeConfig[device];

    return (

        <Button
            fullWidth
            radius={4}
            loading={loading}
            onClick={onClick}
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