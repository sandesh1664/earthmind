import { DiagnosticJobSchema } from "@earthmind/contracts";
import { z } from "zod";
import { proxyBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  if (!z.string().uuid().safeParse(id).success)
    return Response.json(
      { error: "Invalid diagnostic job ID" },
      { status: 422 },
    );
  return proxyBackend(
    `/api/v1/diagnostics/${encodeURIComponent(id)}`,
    DiagnosticJobSchema,
  );
}
