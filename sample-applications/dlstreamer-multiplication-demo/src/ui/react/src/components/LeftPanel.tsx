import { useState } from "react";
import { Button, Select, Stack, Text, TextInput } from "@mantine/core";
import { accent, bg, pipelineTypeConfig, type DeviceType } from "../styles/theme";
import { appConfig } from "../config/appConfig";
import type { ResolutionPreset } from "../api/dlStreamerApi";

const devices: DeviceType[] = ["GPU", "NPU", "CPU"];
const resolutionOptions: Array<{ value: ResolutionPreset; label: string }> = [
    { value: "FULL", label: "1920x1080 (Full)" },
    { value: "2/3", label: "1280x720 (2/3)" },
    { value: "1/2", label: "960x540 (1/2)" },
    { value: "1/3", label: "640x360 (1/3)" },
];
const modelSharingOptions = [
    { value: "false", label: "Disabled" },
    { value: "true", label: "Enabled" },
];

type LeftPanelProps = {
    onAddPipeline: (data: {
        name: string;
        sourceUri: string;
        device: DeviceType;
        count: number;
        resolutionPreset: ResolutionPreset;
        inferenceInterval: number;
        modelSharing: boolean;
    }) => Promise<void>;

    onRemoveAllPipelines: () => Promise<void>;
};

export function LeftPanel({ onAddPipeline, onRemoveAllPipelines }: LeftPanelProps) {
    const [streamName, setStreamName] = useState(appConfig.defaultStreamName);
    const [streamUrl, setStreamUrl] = useState(appConfig.defaultStreamUrl);
    const [isAdding, setIsAdding] = useState(false);
    const [streamCount, setStreamCount] = useState(appConfig.defaultInstanceCount);
    const [resolutionPreset, setResolutionPreset] = useState<ResolutionPreset>(
        appConfig.defaultInferenceResolution as ResolutionPreset
    );
    const [inferenceInterval, setInferenceInterval] = useState(
        appConfig.defaultInferenceInterval
    );
    const [modelSharing, setModelSharing] = useState(
        String(appConfig.defaultModelSharing)
    );
    const [isRemovingAll, setIsRemovingAll] = useState(false);

    async function handleAddPipeline(device: DeviceType) {
        const count = Math.min(Math.max(Number(streamCount) || 1, 1), 50);
        const parsedInferenceInterval = Math.min(
            Math.max(Number(inferenceInterval) || 1, 1),
            120
        );
        setIsAdding(true);

        try {
            await onAddPipeline({
                name: streamName,
                sourceUri: streamUrl,
                device,
                count: count,
                resolutionPreset,
                inferenceInterval: parsedInferenceInterval,
                modelSharing: modelSharing === "true",
            });
        } finally {
            setIsAdding(false);
        }
    }

    async function handleRemoveAllPipelines() {
        setIsRemovingAll(true);

        try {
            await onRemoveAllPipelines();
        } finally {
            setIsRemovingAll(false);
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
                    placeholder={appConfig.defaultStreamUrl}
                    value={streamUrl}
                    onChange={setStreamUrl}
                />
            </Stack>

            <Stack gap="xs" mt={4}>
                <StyledTextInput
                    label="Instances to add (1-50)"
                    placeholder="1"
                    value={streamCount}
                    onChange={setStreamCount}
                />

                <StyledSelect
                    label="Inference resolution"
                    data={resolutionOptions}
                    value={resolutionPreset}
                    onChange={(value) => setResolutionPreset((value as ResolutionPreset) ?? "2/3")}
                />

                <StyledTextInput
                    label="Inference interval (every Nth frame)"
                    placeholder="1"
                    value={inferenceInterval}
                    onChange={setInferenceInterval}
                />

                <StyledSelect
                    label="Model sharing"
                    data={modelSharingOptions}
                    value={modelSharing}
                    onChange={(value) => setModelSharing(value ?? "false")}
                />
                {devices.map((device) => (
                    <PipelineButton
                        key={device}
                        device={device}
                        loading={isAdding}
                        onClick={() => handleAddPipeline(device)}
                    />
                ))}

                <Button
                    fullWidth
                    radius={4}
                    loading={isRemovingAll}
                    disabled={isAdding}
                    onClick={handleRemoveAllPipelines}
                    styles={{
                        root: {
                            height: 38,
                            marginTop: 8,
                            background: "rgba(228,34,34,0.14)",
                            color: accent.red,
                            border: "1px solid rgba(228,34,34,0.45)",
                            fontSize: 12,
                            fontWeight: 900,
                            textTransform: "uppercase",
                            letterSpacing: "0.13em",
                        },
                    }}
                >
                    Remove all pipelines
                </Button>
            </Stack>
        </Stack>
    );
}

function inputStyles() {
    return {
        label: {
            marginBottom: 5,
            fontSize: 10,
            textTransform: "uppercase" as const,
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
    };
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
            styles={inputStyles()}
        />
    );
}

function StyledSelect({
    label,
    data,
    value,
    onChange,
}: {
    label: string;
    data: Array<{ value: string; label: string }>;
    value: string;
    onChange: (value: string | null) => void;
}) {
    return (
        <Select
            label={label}
            data={data}
            value={value}
            onChange={onChange}
            allowDeselect={false}
            styles={inputStyles()}
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
