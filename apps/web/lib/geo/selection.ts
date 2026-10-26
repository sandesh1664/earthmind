import type { FeatureSelection } from "../city/types";

export const SELECTION_PRIORITY = ["intersection", "road", "building"] as const;
export function selectionKey(value: FeatureSelection): string | null {
  return value === null ? null : `${value.kind}:${value.id}`;
}
export function preferredSelection(values: readonly FeatureSelection[]): FeatureSelection {
  for (const kind of SELECTION_PRIORITY) {
    const match = values.find((value) => value?.kind === kind);
    if (match) return match;
  }
  return null;
}
/** Only primitive values are shown as React text. No HTML or provider objects escape. */
export function publicBuildingProperties(keys: readonly string[], get: (key: string) => unknown): Record<string, string | number | boolean> {
  const output: Record<string, string | number | boolean> = {};
  for (const key of keys.slice(0, 50)) {
    if (/password|secret|token|credential|authorization|api.?key/i.test(key)) continue;
    const value = get(key);
    if (typeof value === "string") output[key.slice(0, 128)] = value.slice(0, 1_000);
    else if (typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))) output[key.slice(0, 128)] = value;
  }
  return output;
}


/** OSM node/way/relation identifiers occupy distinct namespaces. */
export function buildingSelectionId(properties: Record<string,string | number | boolean>, fallback: string): string {
  const elementType = properties["elementType"] ?? properties["osm_type"];
  const elementId = properties["elementId"] ?? properties["osm_id"];
  if ((typeof elementType === "string" || typeof elementType === "number") && (typeof elementId === "string" || typeof elementId === "number")) {
    return `${elementType}:${elementId}`;
  }
  return fallback;
}
