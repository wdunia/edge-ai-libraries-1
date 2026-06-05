import { Badge, Box, Group, SimpleGrid, Text } from "@mantine/core";
import { bg, pipelineTypeConfig, type DeviceType } from "../styles/theme";

type StreamTile = {
    id: number;
    name: string;
    type: DeviceType;
    fps: number;
    streamUrl?: string;
};

type CameraGridProps = {
    layoutMode: 1 | 4 | 9 | 16 | 25 | 36;
};

const streams: StreamTile[] = Array.from({ length: 12 }, (_, index) => {
    const type = (["GPU", "NPU", "CPU"] as const)[index % 3];

    return {
        id: index + 1,
        name: `CAM-${String(index + 1).padStart(2, "0")}`,
        type,
        fps: 29 + (index % 4),
        streamUrl:
            index === 0
                ? "http://10.91.157.75:8889/pallet_defect_detection"
                : undefined,
    };
});

export function CameraGrid({ layoutMode }: CameraGridProps) {
    const columns = Math.sqrt(layoutMode);
    const rows = Math.sqrt(layoutMode);

    return (
        <Box
            style={{
                height: "100%",
                overflowY: "auto",
                overflowX: "hidden",
            }}
        >
            <SimpleGrid
                cols={columns}
                spacing="md"
                style={{
                    minHeight: "100%",
                    gridAutoRows: `calc((100% - ${(rows - 1) * 16}px) / ${rows})`,
                }}
            >
                {streams.map((stream) => (
                    <CameraTile key={stream.id} stream={stream} />
                ))}
            </SimpleGrid>
        </Box>
    );
}

function CameraTile({ stream }: { stream: StreamTile }) {
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
                            background: "#62CE58",
                            flexShrink: 0,
                        }}
                    />

                    <Text size="xs" fw={700} c="#62CE58">
                        LIVE
                    </Text>

                    <Text size="xs" fw={700} c="#00A3F6">
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
                            VIDEO STREAM HERE
                        </Text>
                    </Box>
                )}
            </Box>
        </Box>
    );
}