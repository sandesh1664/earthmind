import type { CityConfig, ProviderState, VisualizationMode } from "./types";

/** The renderer and its labels must describe the same selected dataset. */
export function effectiveImageryMode(config: CityConfig, isSynthetic: boolean, visualizationMode?: VisualizationMode) {
  if (isSynthetic) return "natural-earth";
  if (visualizationMode) return visualizationMode === "realistic" ? "ion" : "local-osm";
  return config.imageryMode ?? "local-osm";
}

export function imageryDescription(config: CityConfig, isSynthetic: boolean, visualizationMode?: VisualizationMode): string {
  const mode = effectiveImageryMode(config, isSynthetic, visualizationMode);
  if (mode === "local-osm") return "Local OpenStreetMap cartography over Natural Earth reference; no satellite imagery";
  if (mode === "ion" && config.ionPublicToken) return "Cesium ion imagery requested; availability and coverage depend on the provider";
  if (mode === "ion") return "Cesium ion imagery blocked: public token missing; using low-resolution Natural Earth reference";
  return "Natural Earth reference only; no city-scale satellite detail";
}

/** Read bounded status facts only. Never forward native errors, URLs or tokens. */
function providerStatusCode(error: unknown, depth = 0): number | null {
  if (depth > 3 || typeof error !== "object" || error === null) return null;
  const value = error as Record<string, unknown>;
  for (const code of [value.statusCode,value.status]) {
    if (typeof code === "number" && Number.isInteger(code) && code >= 400 && code <= 599) return code;
  }
  for (const key of ["error","cause","response"]) {
    const code = providerStatusCode(value[key],depth+1);
    if (code !== null) return code;
  }
  // Tile-failed events sometimes expose only a native status message.
  const status = typeof value.message === "string" ? value.message.slice(0,4096).match(/(?:status(?:\s+code)?|HTTP)\s*[:=]?\s*(4\d\d|5\d\d)\b/i) : null;
  return status?.[1] ? Number(status[1]) : null;
}

export function ionProviderFailure(subject: "imagery" | "buildings" | "terrain", error: unknown): ProviderState {
  const code = providerStatusCode(error);
  const prefix = `Cesium ion ${subject}`;
  if (code === 401) return {status:"error",message:`${prefix}: token rejected (HTTP 401). Check NEXT_PUBLIC_CESIUM_ION_TOKEN and restart web.`};
  if (code === 403) return {status:"error",message:`${prefix}: access denied (HTTP 403). Check read-only asset entitlements and allowed app URLs.`};
  if (code === 404 || code === 410) return {status:"error",message:`${prefix}: configured asset unavailable (HTTP ${code}). Check its asset ID and current provider availability.`};
  if (code === 429) return {status:"error",message:`${prefix}: provider rate or account quota exceeded (HTTP 429). Retry after the account limit clears.`};
  return {status:"error",message:`${prefix} unavailable${code ? ` (HTTP ${code})` : ""}. Check network access and the configured public asset token; stored overlays remain usable.`};
}
