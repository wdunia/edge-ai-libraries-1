import { appConfig } from "../config/appConfig";

export type PipelineStatusItem = {
    id: string;
    state: string;
    avg_fps: number;
    frame_fps: number;
};

type PipelineStatusResponse = {
    status: string;
    metadata: string | PipelineStatusItem[];
};

function parsePipelineStatusMetadata(
    metadata: PipelineStatusResponse["metadata"]
): PipelineStatusItem[] {
    if (Array.isArray(metadata)) {
        return metadata;
    }

    if (typeof metadata === "string") {
        return JSON.parse(metadata) as PipelineStatusItem[];
    }

    throw new Error("Unexpected pipeline status response format");
}

export async function getPipelineStatus(): Promise<PipelineStatusItem[]> {
    const response = await fetch(`${appConfig.apiUrl}/pipeline/status`);

    if (!response.ok) {
        throw new Error("Failed to fetch pipeline status");
    }

    const data = (await response.json()) as PipelineStatusResponse;

    return parsePipelineStatusMetadata(data.metadata);
}
