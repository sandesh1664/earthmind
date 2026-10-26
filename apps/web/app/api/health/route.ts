import { getBackendHealth } from "@/lib/health";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  const result = await getBackendHealth(
    process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
  );
  return Response.json(result.body, {
    status: result.status,
    headers: {
      "Cache-Control": "no-store",
      "X-Earthmind-Api-Reachable": String(result.reachable),
    },
  });
}
