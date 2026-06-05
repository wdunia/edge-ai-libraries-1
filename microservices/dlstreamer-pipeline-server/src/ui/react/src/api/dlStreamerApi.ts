import { appConfig } from "../config/appConfig";

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