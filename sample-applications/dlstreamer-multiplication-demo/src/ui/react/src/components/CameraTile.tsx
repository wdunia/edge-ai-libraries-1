import { ActionIcon, Badge, Box, Group, Text } from "@mantine/core";
import { bg, pipelineTypeConfig, type DeviceType, accent } from "../styles/theme";

export const STREAM_PREVIEW_ASPECT_RATIO = 16 / 9;
export const CAMERA_TILE_CHROME_HEIGHT_PX = 66;

export type StreamTile = {
    id: number;
    streamId?: string;
    name: string;
    type: DeviceType;
    fps: number;
    streamUrl?: string;
    status?: string;
    aspectRatio?: number;
};

type CameraTileProps = {
    stream: StreamTile;
    onDelete?: (stream: StreamTile) => void;
};

export function CameraTile({ stream, onDelete }: CameraTileProps) {
    const typeStyle = pipelineTypeConfig[stream.type];
    const previewAspectRatio = stream.aspectRatio ?? STREAM_PREVIEW_ASPECT_RATIO;

    return (
        <Box
            style={{
                display: "flex",
                flexDirection: "column",
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

                    <ActionIcon
                        size="md"
                        variant="light"
                        color="red"
                        onClick={() => onDelete?.(stream)}
                        aria-label={`Delete ${stream.name}`}
                    >
                        ✕
                    </ActionIcon>
                </Group>
            </Group>

            <Box
                style={{
                    padding: 12,
                }}
            >
                <Box
                    style={{
                        width: "100%",
                        aspectRatio: previewAspectRatio,
                        background: "#000",
                        position: "relative",
                        overflow: "hidden",
                        minWidth: 0,
                    }}
                >
                    {stream.streamUrl ? (
                        <iframe
                            src={stream.streamUrl}
                            title={stream.name}
                            style={{
                                width: "100%",
                                height: "100%",
                                border: "none",
                                display: "block",
                                minWidth: 0,
                                minHeight: 0,
                            }}
                            allow="autoplay; fullscreen"
                            scrolling="no"
                        />
                    ) : (
                        <Box
                            style={{
                                height: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                textAlign: "center",
                                paddingInline: 12,
                            }}
                        >
                            <Text size="xs" fw={700} c="dimmed" lts="0.2em">
                                {stream.status === "QUEUED"
                                    ? "INITIALIZING PIPELINE..."
                                    : stream.status === "ERROR"
                                        ? "PIPELINE ERROR"
                                        : stream.status === "COMPLETED"
                                            ? "PIPELINE COMPLETED"
                                            : "WAITING FOR VIDEO CONNECTION..."}
                            </Text>
                        </Box>
                    )}
                </Box>
            </Box>
        </Box>
    );
}
