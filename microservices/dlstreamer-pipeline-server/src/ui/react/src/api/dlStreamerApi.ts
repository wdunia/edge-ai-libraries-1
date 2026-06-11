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
  metadata: Record<
    string,
    {
      target_device: string;
      url: string;
    }
  >;
};

export async function getStreamUrl(streamId: string): Promise<string | null> {
  const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

  if (!response.ok) {
    throw new Error(`Failed to get stream url. Status: ${response.status}`);
  }

  const data = (await response.json()) as StreamResponse;
  const rawMetadata = data.metadata;
  const rawStreamValue = rawMetadata?.[streamId];
  const rawUrl = rawStreamValue?.url;

  const streamUrl = typeof rawUrl === "string" ? rawUrl.trim() : null;

  if (!streamUrl) {
    console.warn("[DLStreamer] Missing stream URL:", {
      streamId,
      rawMetadata,
      rawStreamValue,
    });

    return null;
  }

  if (!streamUrl.startsWith(appConfig.webrtcUrl)) {
    console.warn("[DLStreamer] Invalid stream URL:", {
      streamId,
      streamUrl,
    });

    return null;
  }

  if (
    streamUrl.includes("{") ||
    streamUrl.includes("status: error")
  ) {
    // console.warn("[DLStreamer] Backend returned error as stream URL:", {
    //   streamId,
    //   streamUrl,
    // });

    return null;
  }

  return streamUrl.endsWith("/") ? streamUrl : `${streamUrl}/`;
}

export type CreatedPipeline = {
  streamId: string;
  peerId: string;
  streamUrl: string;
};

export type AddPipelineResponse = {
  status: string;
  message: string;
};

const palletDefectDetectionModelPath =
  "/home/fst/edge-ai-libraries/microservices/dlstreamer-pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml";
  
export async function createCameraPipeline(
  device: DeviceType,
  sourceUri: string,
  index = 0
): Promise<CreatedPipeline> {
  const params = new URLSearchParams({
    stream_path: sourceUri,
    model_path: palletDefectDetectionModelPath,
    target_device: device,
  });

  const response = await fetch(
    `${appConfig.apiUrl}/pipeline/add?${params.toString()}`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
      },
      body: "",
    }
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `Failed to create pipeline. Status: ${response.status}. Response: ${errorText}`
    );
  }

  const data = (await response.json()) as AddPipelineResponse;

  if (data.status !== "Success") {
    throw new Error(`Failed to create pipeline. Message: ${data.message}`);
  }

  const streamId = data.message.replaceAll('"', "").trim();

  const streamUrl = await getStreamUrl(streamId);

  return {
    streamId,
    peerId: streamId,
    streamUrl: streamUrl ?? `${appConfig.webrtcUrl}/${streamId}/`,
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
  state: string;
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

export async function deleteAllPipelines(streamIds: string[]): Promise<void> {
  await Promise.all(streamIds.map((streamId) => deletePipeline(streamId)));
}