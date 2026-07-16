import { Box } from "@mantine/core";
import { useElementSize } from "@mantine/hooks";
import {
    CAMERA_TILE_CHROME_HEIGHT_PX,
    CameraTile,
    STREAM_PREVIEW_ASPECT_RATIO,
    type StreamTile,
} from "./CameraTile";

const GRID_GAP_PX = 16;

function getGridMetrics({
    columns,
    streamCount,
    containerWidth,
}: {
    columns: number;
    streamCount: number;
    containerWidth: number;
}) {
    const rows = Math.ceil(streamCount / columns);
    const tileWidth =
        (containerWidth - GRID_GAP_PX * Math.max(columns - 1, 0)) / columns;
    const videoHeight = tileWidth / STREAM_PREVIEW_ASPECT_RATIO;
    const tileHeight = CAMERA_TILE_CHROME_HEIGHT_PX + videoHeight;
    const gridHeight = rows * tileHeight + GRID_GAP_PX * Math.max(rows - 1, 0);

    return {
        rows,
        tileWidth,
        tileHeight,
        videoHeight,
        gridHeight,
    };
}

function getAutoColumns({
    streamCount,
    containerWidth,
    containerHeight,
}: {
    streamCount: number;
    containerWidth: number;
    containerHeight: number;
}) {
    if (streamCount <= 1) {
        return Math.max(streamCount, 1);
    }

    const maxColumns = Math.min(streamCount, 7);

    if (containerWidth <= 0 || containerHeight <= 0) {
        return Math.min(streamCount, 3);
    }

    let bestFit: {
        columns: number;
        videoArea: number;
        overflow: number;
    } | null = null;
    let bestOverflow: {
        columns: number;
        overflow: number;
        videoArea: number;
    } | null = null;

    for (let columns = 1; columns <= maxColumns; columns += 1) {
        const metrics = getGridMetrics({
            columns,
            streamCount,
            containerWidth,
        });

        if (metrics.tileWidth <= 0) {
            continue;
        }

        const overflow = Math.max(metrics.gridHeight - containerHeight, 0);
        const videoArea = metrics.tileWidth * metrics.videoHeight;

        if (overflow === 0) {
            if (
                !bestFit ||
                videoArea > bestFit.videoArea ||
                (videoArea === bestFit.videoArea && columns < bestFit.columns)
            ) {
                bestFit = {
                    columns,
                    videoArea,
                    overflow,
                };
            }
            continue;
        }

        if (
            !bestOverflow ||
            overflow < bestOverflow.overflow ||
            (overflow === bestOverflow.overflow && videoArea > bestOverflow.videoArea)
        ) {
            bestOverflow = {
                columns,
                overflow,
                videoArea,
            };
        }
    }

    return bestFit?.columns ?? bestOverflow?.columns ?? Math.min(streamCount, 3);
}

type CameraGridProps = {
    layoutMode: "auto" | 1 | 2 | 3 | 4 | 5 | 6 | 7;
    streams: StreamTile[];
    onDeleteStream?: (stream: StreamTile) => void;
};

export function CameraGrid({
    layoutMode,
    streams,
    onDeleteStream,
}: CameraGridProps) {
    const { ref, width, height } = useElementSize();
    const streamCount = streams.length;
    const columns =
        layoutMode === "auto"
            ? getAutoColumns({
                streamCount,
                containerWidth: width,
                containerHeight: height,
            })
            : Math.min(layoutMode, Math.max(streamCount, 1));

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
