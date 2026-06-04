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

export async function getPeerId(streamId: string): Promise<string> {
  const response = await fetch(`${appConfig.apiUrl}/stream/${streamId}`);

  if (!response.ok) {
    throw new Error(`Failed to get peer id. Status: ${response.status}`);
  }

  return await response.text();
}