import { readPublicCityConfig } from "@/lib/city/config";

export const dynamic = "force-dynamic";
export function GET(): Response {
  try {
    return Response.json(readPublicCityConfig(process.env), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ error: "Public viewer configuration is invalid. Check the server configuration." }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
