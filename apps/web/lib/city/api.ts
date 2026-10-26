/** Bounded read-only city data. PostGIS remains the geographic source of truth. */
import { z } from "zod";
import {
  BoundsSchema,
  DataSourceSchema,
  NetworkListSchema,
  NetworkValidationSchema,
  PositionSchema,
  RegionFeatureSchema,
  RegionListSchema,
} from "../geospatial";
import type { Bounds, IntersectionFeature, RoadFeature } from "./types";

export const CITY_LIMITS = {
  pageSize: 100,
  registryFeatures: 500,
  spatialFeatures: 500,
  spatialCoordinates: 25_000,
  responseBytes: 4 * 1024 * 1024,
  timeoutMs: 8_000,
  cameraDebounceMs: 350,
  bboxSpan: 1,
} as const;

/** Preserve exact optional semantics instead of materializing undefined keys. */
function withoutUndefined<T extends Record<string, unknown>>(value: T): {
  [K in keyof T]: Exclude<T[K], undefined>
} {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined)) as {
    [K in keyof T]: Exclude<T[K], undefined>
  };
}

const uuid = z.uuid();
const finite = z.number().finite();
export const CityRoadSchema = z.object({
  type: z.literal("Feature"),
  id: uuid,
  geometry: z.object({
    type: z.literal("LineString"),
    coordinates: z.array(PositionSchema).min(2).max(5_000),
  }).strip().refine((geometry) => geometry.coordinates.some((point) => {
    const first = geometry.coordinates[0];
    return first !== undefined && (point[0] !== first[0] || point[1] !== first[1]);
  }), "Road geometry has no extent"),
  properties: z.object({
    network_version_id: uuid,
    sumo_edge_id: z.string().min(1).max(255),
    source_edge_id: z.string().max(255).nullable().optional(),
    name: z.string().max(255).nullable().optional(),
    road_class: z.string().min(1).max(128),
    lane_count: z.number().int().positive(),
    speed_limit_mps: finite.positive().nullable().optional(),
    length_m: finite.nonnegative(),
    is_one_way: z.boolean(),
    is_synthetic: z.boolean(),
    start_intersection_id: uuid.optional(),
    end_intersection_id: uuid.optional(),
  }).strip(),
}).strip().transform((value) => ({...value, properties: withoutUndefined(value.properties)})) satisfies z.ZodType<RoadFeature>;

export const CityIntersectionSchema = z.object({
  type: z.literal("Feature"),
  id: uuid,
  geometry: z.object({type: z.literal("Point"), coordinates: PositionSchema}).strip(),
  properties: z.object({
    network_version_id: uuid,
    source_node_id: z.string().min(1).max(255),
    sumo_node_id: z.string().max(255).nullable().optional(),
    intersection_type: z.string().min(1).max(128),
    is_signalized: z.boolean().optional(),
    is_synthetic: z.boolean(),
  }).strip(),
}).strip().transform((value) => ({...value, properties: withoutUndefined(value.properties)})) satisfies z.ZodType<IntersectionFeature>;

const pagination = {
  total: z.number().int().nonnegative(),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().nonnegative().max(100_000),
};
export const CityRoadCollectionSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(CityRoadSchema).max(100),
  ...pagination,
}).strip();
export const CityIntersectionCollectionSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(CityIntersectionSchema).max(100),
  ...pagination,
}).strip();

export class CityDataError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "CityDataError";
  }
}

/** Combine cancellation with a deadline; never replace the query's AbortSignal. */
export async function readCityJSON<T>(
  url: string,
  schema: z.ZodType<T>,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<T> {
  const combined = AbortSignal.any([signal, AbortSignal.timeout(CITY_LIMITS.timeoutMs)]);
  combined.throwIfAborted();
  const response = await fetcher(url, {
    cache: "no-store",
    headers: {Accept: "application/json"},
    signal: combined,
  });
  combined.throwIfAborted();
  if (!response.ok) {
    throw new CityDataError(
      response.status === 404 ? "Selected geographic resource is no longer available." :
      `Geographic service unavailable (HTTP ${response.status}). Retry the request.`,
      response.status,
    );
  }
  const declaredBytes = Number(response.headers.get("content-length"));
  if (declaredBytes > CITY_LIMITS.responseBytes) {
    await response.body?.cancel();
    throw new CityDataError("Geographic response exceeds the display budget. Zoom closer.");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new CityDataError("Geographic service returned an empty response.");
  const decoder = new TextDecoder();
  let bytes = 0;
  let text = "";
  try {
    while (true) {
      combined.throwIfAborted();
      const next = await reader.read();
      if (next.done) break;
      bytes += next.value.byteLength;
      if (bytes > CITY_LIMITS.responseBytes) {
        await reader.cancel();
        throw new CityDataError("Geographic response exceeds the display budget. Zoom closer.");
      }
      text += decoder.decode(next.value, {stream: true});
    }
    text += decoder.decode();
    combined.throwIfAborted();
  } finally {
    reader.releaseLock();
  }
  let parsed: unknown;
  try { parsed = JSON.parse(text); }
  catch { throw new CityDataError("Geographic service returned invalid JSON."); }
  const result = schema.safeParse(parsed);
  if (!result.success) {
    throw new CityDataError("Geographic data is invalid or unsupported. No invalid geometry was rendered.");
  }
  return result.data;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  truncated: boolean;
  coordinateCount: number;
}
interface RegistryPage<T> { items: T[]; total: number; limit: number; offset: number }
interface SpatialPage<T> { features: T[]; total: number; limit: number; offset: number }

async function registryPages<T extends {id: string}>(
  path: string,
  schema: z.ZodType<RegistryPage<T>>,
  signal: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<PageResult<T>> {
  const items: T[] = [];
  const ids = new Set<string>();
  let total: number | undefined;
  let offset = 0;
  do {
    const separator = path.includes("?") ? "&" : "?";
    const page = await readCityJSON(`${path}${separator}limit=100&offset=${offset}`, schema, signal, fetcher);
    if (page.offset !== offset || page.limit !== CITY_LIMITS.pageSize || (total !== undefined && total !== page.total)) {
      throw new CityDataError("Geographic catalog changed while loading. Retry for a consistent view.");
    }
    total = page.total;
    if (page.items.length > total - offset || (page.items.length === 0 && offset < total)) {
      throw new CityDataError("Geographic catalog pagination is inconsistent. Retry the request.");
    }
    for (const item of page.items) {
      if (ids.has(item.id)) throw new CityDataError("Geographic catalog contains duplicate identifiers.");
      ids.add(item.id);
      items.push(item);
    }
    offset += page.items.length;
    if (offset < total && page.items.length < CITY_LIMITS.pageSize) {
      throw new CityDataError("Geographic catalog pagination is incomplete. Retry the request.");
    }
  } while (offset < (total ?? 0) && items.length < CITY_LIMITS.registryFeatures);
  return {items, total: total ?? 0, truncated: items.length < (total ?? 0), coordinateCount: 0};
}

export const fetchCityRegions = (signal: AbortSignal, fetcher: typeof fetch = fetch) =>
  registryPages("/api/geospatial/regions", RegionListSchema, signal, fetcher);
export async function fetchCityNetworks(regionId: string, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  uuid.parse(regionId);
  const result = await registryPages(`/api/geospatial/networks?region_id=${encodeURIComponent(regionId)}`, NetworkListSchema, signal, fetcher);
  if (result.items.some((network) => network.region_id !== regionId)) {
    throw new CityDataError("Network catalog did not match the selected study region.");
  }
  return result;
}
export async function fetchCityBoundary(regionId: string, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  uuid.parse(regionId);
  const value = await readCityJSON(`/api/geospatial/regions/${regionId}/geojson`, RegionFeatureSchema, signal, fetcher);
  if (value.id !== regionId || value.properties.id !== regionId) {
    throw new CityDataError("Region geometry did not match the selected study region.");
  }
  return value;
}
export async function fetchCitySource(sourceId: string, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  uuid.parse(sourceId);
  const value = await readCityJSON(`/api/geospatial/data-sources/${sourceId}`, DataSourceSchema, signal, fetcher);
  if (value.id !== sourceId) throw new CityDataError("Dataset source did not match the requested source.");
  return value;
}
export async function fetchCityValidation(networkId: string, signal: AbortSignal, fetcher: typeof fetch = fetch) {
  uuid.parse(networkId);
  const value = await readCityJSON(`/api/geospatial/networks/${networkId}/validation`, NetworkValidationSchema, signal, fetcher);
  if (value.network_id !== networkId) throw new CityDataError("Validation did not match the selected network.");
  return value;
}

export interface ViewportQuery { bounds: Bounds | null; state: "ready" | "outside" | "zoom" }
/** Clip requests, not stored geometry. Measurements remain backend-owned. */
export function cityRequestBounds(view: Bounds | null, region: Bounds): ViewportQuery {
  if (!BoundsSchema.safeParse(region).success || region[0] >= region[2] || region[1] >= region[3]) {
    return {bounds: null, state: "zoom"};
  }
  if (view && (!BoundsSchema.safeParse(view).success || view[0] >= view[2] || view[1] >= view[3])) {
    return {bounds: null, state: "zoom"};
  }
  const clipped: Bounds = view ? [
    Math.max(view[0], region[0]), Math.max(view[1], region[1]),
    Math.min(view[2], region[2]), Math.min(view[3], region[3]),
  ] : [...region];
  if (clipped[0] >= clipped[2] || clipped[1] >= clipped[3]) return {bounds: null, state: "outside"};
  if (clipped[2] - clipped[0] > CITY_LIMITS.bboxSpan || clipped[3] - clipped[1] > CITY_LIMITS.bboxSpan) {
    return {bounds: null, state: "zoom"};
  }
  // Fixed precision gives equivalent camera stops a stable query/cache identity.
  const quantized = clipped.map((value) => Number(value.toFixed(6))) as Bounds;
  if (quantized[0] >= quantized[2] || quantized[1] >= quantized[3]) return {bounds: null, state: "zoom"};
  return {bounds: quantized, state: "ready"};
}

async function spatialPages<T extends RoadFeature | IntersectionFeature>(
  networkId: string,
  kind: "edges" | "intersections",
  bounds: Bounds,
  schema: z.ZodType<SpatialPage<T>>,
  signal: AbortSignal,
  fetcher: typeof fetch,
): Promise<PageResult<T>> {
  uuid.parse(networkId);
  const checked = cityRequestBounds(bounds, bounds);
  if (!checked.bounds) throw new CityDataError("Map request bounds are invalid or too large. Zoom closer.");
  const items: T[] = [];
  const ids = new Set<string>();
  let total: number | undefined;
  let offset = 0;
  let coordinateCount = 0;
  let coordinateBudgetReached = false;
  do {
    const query = new URLSearchParams({bbox: checked.bounds.join(","), limit: "100", offset: String(offset)});
    const page = await readCityJSON(`/api/geospatial/networks/${networkId}/${kind}?${query}`, schema, signal, fetcher);
    if (page.offset !== offset || page.limit !== CITY_LIMITS.pageSize || (total !== undefined && total !== page.total)) {
      throw new CityDataError("Network geometry changed while loading. Retry for a consistent view.");
    }
    total = page.total;
    if (page.features.length > total - offset || (page.features.length === 0 && offset < total)) {
      throw new CityDataError("Network geometry pagination is inconsistent. Retry the request.");
    }
    for (const item of page.features) {
      if (item.properties.network_version_id !== networkId) {
        throw new CityDataError("Geographic feature did not match the selected network.");
      }
      if (ids.has(item.id)) throw new CityDataError("Network geometry contains duplicate identifiers.");
      ids.add(item.id);
      const size = item.geometry.type === "Point" ? 1 : item.geometry.coordinates.length;
      if (coordinateCount + size > CITY_LIMITS.spatialCoordinates) {
        coordinateBudgetReached = true;
        break;
      }
      items.push(item);
      coordinateCount += size;
    }
    offset += page.features.length;
    if (offset < total && page.features.length < CITY_LIMITS.pageSize) {
      throw new CityDataError("Network geometry pagination is incomplete. Retry the request.");
    }
  } while (!coordinateBudgetReached && offset < (total ?? 0) && items.length < CITY_LIMITS.spatialFeatures);
  return {items, total: total ?? 0, truncated: items.length < (total ?? 0), coordinateCount};
}
export const fetchCityRoads = (networkId: string, bounds: Bounds, signal: AbortSignal, fetcher: typeof fetch = fetch) =>
  spatialPages<RoadFeature>(networkId, "edges", bounds, CityRoadCollectionSchema, signal, fetcher);
export const fetchCityIntersections = (networkId: string, bounds: Bounds, signal: AbortSignal, fetcher: typeof fetch = fetch) =>
  spatialPages<IntersectionFeature>(networkId, "intersections", bounds, CityIntersectionCollectionSchema, signal, fetcher);
