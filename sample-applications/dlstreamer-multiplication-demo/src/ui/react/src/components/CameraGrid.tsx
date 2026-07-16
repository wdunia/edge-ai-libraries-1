import { Box } from "@mantine/core";
import { useElementSize } from "@mantine/hooks";
import {
    CAMERA_TILE_CHROME_HEIGHT_PX,
    CameraTile,
    STREAM_PREVIEW_ASPECT_RATIO,
    type StreamTile,
} from "./CameraTile";

const GRID_GAP_PX = 16;

function getAutoColumns({
    preferredColumns,
    streamCount,
    containerWidth,
    containerHeight,
}: {
    preferredColumns: number;
    streamCount: number;
    containerWidth: number;
    containerHeight: number;
}) {
    if (streamCount <= 1) {
        return Math.max(streamCount, 1);
    }

    const safePreferredColumns = Math.min(
        Math.max(Math.round(preferredColumns), 1),
        streamCount
    );

    if (containerWidth <= 0 || containerHeight <= 0) {
        return safePreferredColumns;
    }

    for (let columns = safePreferredColumns; columns <= streamCount; columns += 1) {
        const rows = Math.ceil(streamCount / columns);
        const tileWidth =
            (containerWidth - GRID_GAP_PX * Math.max(columns - 1, 0)) / columns;

        if (tileWidth <= 0) {
            continue;
        }

        const tileHeight =
            CAMERA_TILE_CHROME_HEIGHT_PX +
            tileWidth / STREAM_PREVIEW_ASPECT_RATIO;
        const gridHeight =
            rows * tileHeight + GRID_GAP_PX * Math.max(rows - 1, 0);

        if (gridHeight <= containerHeight) {
            return columns;
        }
    }

    return streamCount;
}

type CameraGridProps = {
    layoutMode: 1 | 2 | 3 | 4 | 5 | 6;
    streams: StreamTile[];
    onDeleteStream?: (stream: StreamTile) => void;
};

export function CameraGrid({
    layoutMode,
    streams,
    onDeleteStream,
}: CameraGridProps) {
    const { ref, width, height } = useElementSize();
    const columns = getAutoColumns({
        preferredColumns: layoutMode,
        streamCount: streams.length,
        containerWidth: width,
        containerHeight: height,
    });

    return (
        <Box
            ref={ref}
            style={{
                height: "100%",
                overflowY: "auto",
                overflowX: "hidden",
            }}
        >
            <Box
                style={{
                    minHeight: "100%",
                    display: "grid",
                    gridTemplateColumns: `repeat(${Math.max(columns, 1)}, minmax(0, 1fr))`,
                    gap: GRID_GAP_PX,
                    alignContent: "start",
                }}
            >
                {streams.map((stream) => (
                    <CameraTile
                        key={stream.id}
                        stream={stream}
                        onDelete={onDeleteStream}
                    />
                ))}
            </Box>
        </Box>
    );
}
