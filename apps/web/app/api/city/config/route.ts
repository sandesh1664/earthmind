import { PublicCityConfigurationError, readPublicCityConfig } from "@/lib/city/config";

export const dynamic = "force-dynamic";
export function GET(): Response {
  try {
    return Response.json(readPublicCityConfig(process.env), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return Response.json({ error: error instanceof PublicCityConfigurationError ? error.message : "Public viewer configuration is invalid. Check the public token format and numeric asset IDs in the server environment." }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
