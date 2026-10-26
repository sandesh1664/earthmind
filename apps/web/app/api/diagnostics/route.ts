import {
  DiagnosticJobSchema,
  DiagnosticRequestSchema,
} from "@earthmind/contracts";
import { proxyBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function browserFacingOrigin(request: Request): string | null {
  const url = new URL(request.url);
  // Standalone Next.js constructs Request.url from its internal bind address.
  // The browser-facing Host is authoritative here; forwarded hosts are ignored.
  const host = request.headers.get("Host") ?? url.host;
  const match = /^(localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?$/i.exec(host);
  if (!match || !["http:", "https:"].includes(url.protocol)) return null;
  if (match[2] && (Number(match[2]) < 1 || Number(match[2]) > 65535)) return null;
  return new URL(`${url.protocol}//${host}`).origin;
}

export async function POST(request: Request): Promise<Response> {
  const origin = request.headers.get("Origin");
  const expectedOrigin = browserFacingOrigin(request);
  if (expectedOrigin === null || (origin !== null && origin !== expectedOrigin)) {
    return Response.json(
      { error: "Cross-origin diagnostic requests are not allowed" },
      { status: 403 },
    );
  }
  if (
    request.headers.get("Content-Type")?.split(";")[0]?.trim().toLowerCase() !==
    "application/json"
  ) {
    return Response.json(
      { error: "Content-Type must be application/json" },
      { status: 415 },
    );
  }
  let input: unknown;
  try {
    input = await request.json();
  } catch {
    return Response.json(
      { error: "A JSON diagnostic request is required" },
      { status: 400 },
    );
  }
  const parsed = DiagnosticRequestSchema.safeParse(input);
  if (!parsed.success)
    return Response.json(
      { error: "Choose diagnostic or sumo_runtime" },
      { status: 422 },
    );
  return proxyBackend("/api/v1/diagnostics", DiagnosticJobSchema, {
    method: "POST",
    body: parsed.data,
  });
}
