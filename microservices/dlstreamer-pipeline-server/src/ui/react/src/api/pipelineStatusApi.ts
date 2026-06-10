import { appConfig } from "../config/appConfig";

export type PipelineStatusItem = {
    id: string;
    state: string;
    avg_fps: number;
    frame_fps: number;
};

type PipelineStatusResponse = {
    status: string;
    metadata: string;
};

export async function getPipelineStatus(): Promise<PipelineStatusItem[]> {
    const response = await fetch(`${appConfig.apiUrl}/pipeline/status`);

    if (!response.ok) {
        throw new Error("Failed to fetch pipeline status");
    }

    const data = (await response.json()) as PipelineStatusResponse;

    return JSON.parse(data.metadata) as PipelineStatusItem[];
}