import { CapabilitiesSchema } from "@earthmind/contracts";
import { proxyBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  return proxyBackend("/api/v1/system/capabilities", CapabilitiesSchema);
}
