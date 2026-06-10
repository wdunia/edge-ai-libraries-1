import { ActionIcon, Badge, Box, Group, Text } from "@mantine/core";
import { bg, pipelineTypeConfig, type DeviceType, accent } from "../styles/theme";

export type StreamTile = {
    id: number;
    streamId?: string;
    name: string;
    type: DeviceType;
    fps: number;
    streamUrl?: string;
    status?: string;
};

type CameraTileProps = {
    stream: StreamTile;
    onDelete?: (stream: StreamTile) => void;
    onClone?: (stream: StreamTile) => void;
};

export function CameraTile({ stream, onDelete, onClone }: CameraTileProps) {
    const typeStyle = pipelineTypeConfig[stream.type];

    return (
        <Box
            style={{
                overflow: "hidden",
                borderRadius: 6,
                border: `1px solid ${bg.border}`,
                background: bg.tile,
                minHeight: 0,
            }}
        >
            <Group
                justify="space-between"
                px="sm"
                py={8}
                wrap="nowrap"
                style={{
                    borderBottom: `1px solid ${bg.border}`,
                }}
            >
                <Group gap="xs" wrap="nowrap">
                    <Text size="xs" fw={700} lts="0.14em">
                        {stream.name}
                    </Text>

                    <Badge
                        size="sm"
                        variant="outline"
                        color={typeStyle.color}
                        styles={{
                            root: {
                                background: typeStyle.bg,
                                borderColor: typeStyle.border,
                                color: typeStyle.color,
                            },
                        }}
                    >
                        {stream.type}
                    </Badge>
                </Group>

                <Group gap="xs" wrap="nowrap">
                    <Box
                        style={{
                            width: 8,
                            height: 8,
                            borderRadius: 999,
                            background: accent.green,
                            flexShrink: 0,
                        }}
                    />

                    <Text size="xs" fw={700} c={accent.green}>
                        LIVE
                    </Text>

                    <Text size="xs" fw={700} c={accent.blue}>
                        {stream.fps} FPS
                    </Text>
                </Group>
            </Group>

            <Box
                style={{
                    height: "calc(100% - 38px)",
                    margin: 12,
                    background: "#000",
                    position: "relative",
                    overflow: "hidden",
                }}
            >
                {stream.streamUrl ? (
                    <iframe
                        src={stream.streamUrl}
                        title={stream.name}
                        onLoad={() => console.log("[DLStreamer] iframe loaded:", stream.streamUrl)}
                        style={{
                            width: "100%",
                            height: "100%",
                            border: "none",
                            display: "block",
                        }}
                        allow="autoplay; fullscreen"
                    />
                ) : (
                    <Box
                        style={{
                            height: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <Text size="xs" fw={700} c="dimmed" lts="0.2em">
                            {stream.status === "QUEUED" ? "STREAM QUEUED" : "STREAM NOT READY"}
                        </Text>
                    </Box>
                )}

                <Group
                    gap="xs"
                    style={{
                        position: "absolute",
                        right: 8,
                        bottom: 8,
                        zIndex: 2,
                    }}
                >
                    <ActionIcon
                        size="md"
                        variant="light"
                        color="red"
                        onClick={() => onDelete?.(stream)}
                        aria-label={`Delete ${stream.name}`}
                    >
                        ✕
                    </ActionIcon>

                    <ActionIcon
                        size="md"
                        variant="light"
                        color="green"
                        onClick={() => onClone?.(stream)}
                        aria-label={`Clone ${stream.name}`}
                    >
                        ⧉
                    </ActionIcon>
                </Group>
            </Box>
        </Box>
    );
}