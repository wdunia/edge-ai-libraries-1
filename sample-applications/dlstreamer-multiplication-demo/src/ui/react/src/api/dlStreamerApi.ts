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

export async function getStreamInfo(streamId: string): Promise<StreamInfo> {
  const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

  if (!response.ok) {
    throw new Error(`Failed to get stream info. Status: ${response.status}`);
  }

  const data = (await response.json()) as StreamResponse;
  const rawStreamValue = data.metadata?.[streamId];

  const rawUrl = rawStreamValue?.url;
  const rawDevice = rawStreamValue?.target_device;

  const streamUrl = typeof rawUrl === "string" ? rawUrl.trim() : null;

  const device =
    rawDevice === "GPU" || rawDevice === "NPU" || rawDevice === "CPU"
      ? rawDevice
      : null;

  return {
    streamUrl: normalizeStreamUrl(streamUrl),
    device,
  };
}

export async function getStreamUrl(streamId: string): Promise<string | null> {
  const info = await getStreamInfo(streamId);
  return info.streamUrl;
}

// export async function getStreamUrl(streamId: string): Promise<string | null> {
//   const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

//   if (!response.ok) {
//     throw new Error(`Failed to get stream url. Status: ${response.status}`);
//   }

//   const data = (await response.json()) as StreamResponse;
//   const rawMetadata = data.metadata;
//   const rawStreamValue = rawMetadata?.[streamId];
//   const rawUrl = rawStreamValue?.url;

//   const streamUrl = typeof rawUrl === "string" ? rawUrl.trim() : null;

//   if (!streamUrl) {
//     console.warn("[DLStreamer] Missing stream URL:", {
//       streamId,
//       rawMetadata,
//       rawStreamValue,
//     });

//     return null;
//   }

//   if (!streamUrl.startsWith(appConfig.webrtcUrl)) {
//     console.warn("[DLStreamer] Invalid stream URL:", {
//       streamId,
//       streamUrl,
//     });

//     return null;
//   }

//   if (
//     streamUrl.includes("{") ||
//     streamUrl.includes("status: error")
//   ) {
//     // console.warn("[DLStreamer] Backend returned error as stream URL:", {
//     //   streamId,
//     //   streamUrl,
//     // });

//     return null;
//   }

//   return streamUrl.endsWith("/") ? streamUrl : `${streamUrl}/`;
// }

export type CreatedPipeline = {
  streamId: string;
  peerId: string;
  streamUrl: string;
  resolutionPreset: ResolutionPreset;
  resolution: string;
  inferenceInterval: number;
};

export type ResolutionPreset = "FULL" | "2/3" | "1/2" | "1/3";

export type CreatePipelineOptions = {
  resolutionPreset: ResolutionPreset;
  inferenceInterval: number;
};

export type AddPipelineResponse = {
  status: string;
  metadata: {
    stream_id: string;
    peer_id: string;
    stream_url: string;
    resolution_preset: ResolutionPreset;
    resolution: string;
    inference_interval: string;
  };
};

export type StreamInfo = {
  streamUrl: string | null;
  device: DeviceType | null;
};

const palletDefectDetectionModelPath = appConfig.modelPath;

function normalizeStreamUrl(url: string | null | undefined): string | null {
  if (typeof url !== "string") {
    return null;
  }

  const trimmedUrl = url.trim();
  if (!/^https?:\/\//.test(trimmedUrl)) {
    return null;
  }

  return trimmedUrl.endsWith("/") ? trimmedUrl : `${trimmedUrl}/`;
}

export async function createCameraPipeline(
  device: DeviceType,
  sourceUri: string,
  options: CreatePipelineOptions,
  index = 0
): Promise<CreatedPipeline> {
  const params = new URLSearchParams({
    stream_path: sourceUri,
    model_path: palletDefectDetectionModelPath,
    target_device: device,
    resolution_preset: options.resolutionPreset,
    inference_interval: String(options.inferenceInterval),
  });
  index = index
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

  if (data.status !== "Success" || !data.metadata) {
    throw new Error("Failed to create pipeline. Missing stream metadata.");
  }

  const streamId = data.metadata.stream_id.trim();
  const peerId = data.metadata.peer_id.trim();
  const streamUrl = normalizeStreamUrl(data.metadata.stream_url);
  const resolutionPreset = data.metadata.resolution_preset;
  const resolution = data.metadata.resolution.trim();
  const inferenceInterval = Number(data.metadata.inference_interval);

  return {
    streamId,
    peerId,
    streamUrl: streamUrl ?? "",
    resolutionPreset,
    resolution,
    inferenceInterval,
  };
}


export type CreatePipelinesResponse = {
  status: string;
  metadata: {
    message: string;
    succeeded: Array<{
      stream_id: string;
      peer_id: string;
      stream_url: string;
      resolution_preset: string;
      resolution: string;
      inference_interval: string | number;
    }>;
    failed: Array<{ error: string }>;
  };
};

export async function createCameraPipelinesParallel(
  configs: Array<{
    device: DeviceType;
    sourceUri: string;
    options: CreatePipelineOptions;
  }>
): Promise<CreatedPipeline[]> {
  if (configs.length === 0) {
    return [];
  }

  const pipelineConfigs = configs.map((cfg) => ({
    stream_path: cfg.sourceUri,
    model_path: palletDefectDetectionModelPath,
    target_device: cfg.device,
    resolution_preset: cfg.options.resolutionPreset,
    inference_interval: cfg.options.inferenceInterval,
  }));

  const response = await fetch(`${appConfig.apiUrl}/pipeline/batch/add`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      accept: "application/json",
    },
    body: JSON.stringify(pipelineConfigs),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to create pipelines. Status: ${response.status}. Response: ${errorText}`
    );
  }

  const data = (await response.json()) as CreatePipelinesResponse;

  if (data.status !== "Success" || !data.metadata) {
    throw new Error("Failed to create pipelines. Missing metadata.");
  }

  return data.metadata.succeeded.map((p) => ({
    streamId: p.stream_id,
    peerId: p.peer_id,
    streamUrl: normalizeStreamUrl(p.stream_url) ?? "",
    resolutionPreset: (p.resolution_preset as ResolutionPreset) || "2/3",
    resolution: p.resolution,
    inferenceInterval: typeof p.inference_interval === "string"
      ? Number(p.inference_interval)
      : p.inference_interval,
  }));
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

export type DeletePipelinesResponse = {
  status: string;
  metadata: {
    message: string;
    succeeded: string[];
    failed: Array<{ stream_id: string; error: string }>;
  };
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
  if (streamIds.length === 0) {
    return;
  }

  // Use batch endpoint for faster parallel deletion on the server side
  const response = await fetch(`${appConfig.apiUrl}/pipeline/batch/delete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      accept: "application/json",
    },
    body: JSON.stringify(streamIds),
  });

  if (!response.ok) {
    throw new Error(`Failed to delete pipelines. Status: ${response.status}`);
  }

  const data = (await response.json()) as DeletePipelinesResponse;
  if (data.status !== "Success") {
    throw new Error("Batch pipeline deletion failed.");
  }

  if (data.metadata.failed.length > 0) {
    const failedIds = data.metadata.failed.map((item) => item.stream_id).join(", ");
    throw new Error(`Failed to delete pipeline(s): ${failedIds}`);
  }
}
