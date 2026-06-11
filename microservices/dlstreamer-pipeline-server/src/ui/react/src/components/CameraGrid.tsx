import { Box, SimpleGrid } from "@mantine/core";
import { CameraTile, type StreamTile } from "./CameraTile";

type CameraGridProps = {
    layoutMode: 1 | 4 | 9 | 16 | 25 | 36;
    streams: StreamTile[];
    onDeleteStream?: (stream: StreamTile) => void;
    onCloneStream?: (stream: StreamTile) => void;
};

export function CameraGrid({
    layoutMode,
    streams,
    onDeleteStream,
    onCloneStream,
}: CameraGridProps) {
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
                    <CameraTile
                        key={stream.id}
                        stream={stream}
                        onDelete={onDeleteStream}
                        onClone={onCloneStream}
                    />
                ))}
            </SimpleGrid>
        </Box>
    );
}