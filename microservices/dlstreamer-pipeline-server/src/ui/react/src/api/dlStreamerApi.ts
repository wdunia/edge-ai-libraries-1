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

export async function getStreamUrl(streamId: string): Promise<string> {
  const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

  if (!response.ok) {
    throw new Error(`Failed to get stream url. Status: ${response.status}`);
  }

  const data = (await response.json()) as StreamResponse;
  const streamUrl = data.metadata[streamId];

  if (!streamUrl) {
    throw new Error(`Stream url not found for stream id: ${streamId}`);
  }

  return streamUrl.trim();
}

export async function createCameraPipeline(device: DeviceType): Promise<string> {
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
          uri: "url_here",
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

  console.log("[DLStreamer] Created pipeline:", {
    streamId,
    peerId,
    device,
  });

  return peerId;
}