import { z } from "zod";

/** Safe operator-facing errors contain setting names, never configured values. */
export class PublicCityConfigurationError extends Error {}

/** This single opt-in token is intentionally public; never read private ion/GIS credentials. */
export const CityConfigSchema = z.object({
  imageryMode: z.enum(["local-osm", "ion", "natural-earth"]).default("local-osm"),
  ionPublicToken: z.string().min(24).max(4096).regex(/^[A-Za-z0-9._~-]+$/).nullable(),
  imageryAssetId: z.number().int().positive(),
  terrainAssetId: z.number().int().positive(),
  diagnosticsEnabled: z.boolean(),
}).strict();

export function readPublicCityConfig(environment: Record<string, string | undefined>) {
  // Runtime indirection avoids embedding a NEXT_PUBLIC_* literal into a client
  // bundle. Next still loads its normal .env.local files; Compose injects root .env.
  const canonical = environment.NEXT_PUBLIC_CESIUM_ION_TOKEN?.trim() || null;
  const legacy = environment.CESIUM_ION_PUBLIC_TOKEN?.trim() || null;
  if (canonical && legacy && canonical !== legacy) {
    throw new PublicCityConfigurationError("NEXT_PUBLIC_CESIUM_ION_TOKEN and CESIUM_ION_PUBLIC_TOKEN differ. Keep one public token setting or make both match, then recreate web.");
  }
  const token = canonical ?? legacy;
  return CityConfigSchema.parse({
    ionPublicToken: token,
    imageryMode: environment.CITY_IMAGERY_MODE || (token ? "ion" : "local-osm"),
    imageryAssetId: Number(environment.CESIUM_ION_IMAGERY_ASSET_ID || "2"),
    terrainAssetId: Number(environment.CESIUM_ION_TERRAIN_ASSET_ID || "1"),
    diagnosticsEnabled: environment.CITY_DIAGNOSTICS_ENABLED === "true",
  });
}
