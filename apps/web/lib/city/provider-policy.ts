import type { CityConfig } from "./types";

/** The renderer and its labels must describe the same selected dataset. */
export function effectiveImageryMode(config: CityConfig, isSynthetic: boolean) {
  return isSynthetic ? "natural-earth" : config.imageryMode ?? "local-osm";
}

export function imageryDescription(config: CityConfig, isSynthetic: boolean): string {
  const mode = effectiveImageryMode(config, isSynthetic);
  if (mode === "local-osm") return "Local OpenStreetMap cartography over Natural Earth reference; no satellite imagery";
  if (mode === "ion" && config.ionPublicToken) return "Cesium ion imagery requested; availability and coverage depend on the provider";
  if (mode === "ion") return "Cesium ion imagery blocked: public token missing; using low-resolution Natural Earth reference";
  return "Natural Earth reference only; no city-scale satellite detail";
}
