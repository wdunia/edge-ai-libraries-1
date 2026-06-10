import { appConfig } from "../config/appConfig";
import type { DeviceType } from "../styles/theme";

export type HealthStatus = {
  ok: boolean;
  status: number;
  data?: unknown;
  error?: string;
};

export async function checkHealth(): Promise<HealthStatus> {
  try {
    const response = await fetch(`${appConfig.apiUrl}/health`);

    let data: unknown = undefined;

    try {
      data = await response.json();
    } catch {
      data = await response.text();
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error instanceof Error ? error.message : "Unknown health check error",
    };
  }
}

export type StreamResponse = {
  status: string;
  metadata: Record<string, string>;
};

export async function getStreamUrl(streamId: string): Promise<string | null> {
  const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

  if (!response.ok) {
    throw new Error(`Failed to get stream url. Status: ${response.status}`);
  }

  const data = (await response.json()) as StreamResponse;
  const streamUrl = data.metadata[streamId]?.trim();

  if (!streamUrl) {
    return null;
  }

  if (!streamUrl.startsWith(appConfig.webrtcUrl)) {
    console.warn("[DLStreamer] Invalid stream URL:", {
      streamId,
      streamUrl,
    });

    return null;
  }

  if (streamUrl.includes("{") || streamUrl.includes("Stream ID") || streamUrl.includes("status: error")) {
    console.warn("[DLStreamer] Backend returned error as stream URL:", {
      streamId,
      streamUrl,
    });

    return null;
  }

  return streamUrl.endsWith("/") ? streamUrl : `${streamUrl}/`;
}

export type CreatedPipeline = {
  streamId: string;
  peerId: string;
  streamUrl: string;
};

export async function createCameraPipeline(
  device: DeviceType,
  sourceUri: string
): Promise<CreatedPipeline> {
  const peerId = `camera0-webrtc-${device.toLowerCase()}-${Date.now()}`;

  const response = await fetch(
    `${appConfig.pipelineServerUrl}/pipelines/user_defined_pipelines/pallet_defect_detection`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source: {
          uri: sourceUri,
          type: "uri",
        },
        destination: {
          metadata: {
            type: "file",
            format: "json-lines",
            path: "/tmp/results.jsonl",
          },
          frame: {
            type: "webrtc",
            "peer-id": peerId,
          },
        },
        parameters: {
          "detection-properties": {
            model:
              "/home/fst/edge-ai-libraries/microservices/dlstreamer-pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml",
            device,
          },
        },
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to create pipeline. Status: ${response.status}`);
  }

  const streamId = (await response.text()).replaceAll('"', "").trim();

  return {
    streamId,
    peerId,
    streamUrl: `${appConfig.webrtcUrl}/${peerId}/`,
  };
}


export async function deletePipeline(streamId: string): Promise<void> {
  const response = await fetch(`${appConfig.apiUrl}/pipeline/${streamId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Failed to delete pipeline. Status: ${response.status}`);
  }
}


export type PipelineStatusItem = {
  id: string;
  state: "RUNNING" | "COMPLETED" | "ENDED" | "CANCELED" | string;
  frame_fps?: number;
  avg_fps?: number;
};
export type PipelineStatusResponse = {
  status: string;
  metadata: string;
};


export async function getPipelineStatus(): Promise<PipelineStatusItem[]> {
  const response = await fetch(`${appConfig.apiUrl}/pipeline/status`);

  if (!response.ok) {
    throw new Error(`Failed to get pipeline status. Status: ${response.status}`);
  }

  const data = (await response.json()) as PipelineStatusResponse;

  return JSON.parse(data.metadata) as PipelineStatusItem[];
}