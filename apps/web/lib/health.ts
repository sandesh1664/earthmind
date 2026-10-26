import { isReadyHealth, type ReadyHealth } from "@earthmind/contracts";

export type HealthProxyResult = {
  status: 200 | 503;
  body: ReadyHealth;
  reachable: boolean;
};

const unavailable: ReadyHealth = {
  service: "api",
  status: "degraded",
  checks: { database: "error", redis: "error", worker: "error" },
};

export async function getBackendHealth(
  baseUrl: string,
  fetcher: typeof fetch = fetch,
): Promise<HealthProxyResult> {
  try {
    const response = await fetcher(
      `${baseUrl.replace(/\/$/, "")}/api/v1/ready`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
        headers: { Accept: "application/json" },
      },
    );
    const body: unknown = await response.json();
    if (!isReadyHealth(body))
      return { status: 503, body: unavailable, reachable: false };
    const healthy =
      response.status === 200 &&
      body.status === "ok" &&
      Object.values(body.checks).every((check) => check === "ok");
    return {
      status: healthy ? 200 : 503,
      body: healthy ? body : { ...body, status: "degraded" },
      reachable: response.status === 200 || response.status === 503,
    };
  } catch {
    return { status: 503, body: unavailable, reachable: false };
  }
}
