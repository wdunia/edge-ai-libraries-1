import { Box, SimpleGrid } from "@mantine/core";
import { type DeviceType } from "../styles/theme";
import { CameraTile } from "./CameraTile"
import { appConfig } from "../config/appConfig";

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
    const testCameraPeerId = "camera0-webrtc";

    return {
        id: index + 1,
        name: `CAM-${String(index + 1).padStart(2, "0")}`,
        type,
        fps: 29 + (index % 4),
        streamUrl:
            index === 0
                ? `${appConfig.webrtcUrl}/${testCameraPeerId}/`
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