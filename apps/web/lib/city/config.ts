import { z } from "zod";

/** This single opt-in token is intentionally public; never read private ion/GIS credentials. */
export const CityConfigSchema = z.object({
  ionPublicToken: z.string().min(24).max(4096).regex(/^[A-Za-z0-9._~-]+$/).nullable(),
  imageryAssetId: z.number().int().positive(),
  terrainAssetId: z.number().int().positive(),
  diagnosticsEnabled: z.boolean(),
}).strict();

export function readPublicCityConfig(environment: Record<string, string | undefined>) {
  const token = environment.CESIUM_ION_PUBLIC_TOKEN?.trim() || null;
  return CityConfigSchema.parse({
    ionPublicToken: token,
    imageryAssetId: Number(environment.CESIUM_ION_IMAGERY_ASSET_ID || "3812"),
    terrainAssetId: Number(environment.CESIUM_ION_TERRAIN_ASSET_ID || "1"),
    diagnosticsEnabled: environment.CITY_DIAGNOSTICS_ENABLED === "true",
  });
}
