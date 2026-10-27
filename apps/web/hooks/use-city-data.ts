"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CityConfigSchema } from "../lib/city/config";
import { cityNetworksForMode, cityRegionsForMode, preferredCityRegion } from "../lib/city/catalog";
import { CITY_SPATIAL_QUERY_OPTIONS } from "../lib/city/query-options";
import {
  CITY_LIMITS,
  cityRequestBounds,
  fetchCityBoundary,
  fetchCityIntersections,
  fetchCityNetworks,
  fetchCityRegions,
  fetchCityRoads,
  fetchCitySource,
  fetchCityValidation,
  readCityJSON,
} from "../lib/city/api";
import type {
  Bounds,
  CameraSnapshot,
  IntersectionFeature,
  RoadFeature,
  SceneData,
} from "../lib/city/types";

const EMPTY_ROADS: RoadFeature[] = [];
const EMPTY_INTERSECTIONS: IntersectionFeature[] = [];

/** Timer cleanup also prevents a pending old camera stop from winning on unmount. */
function useCameraBounds(camera: CameraSnapshot | null): Bounds | null {
  const key = camera?.bounds?.map((value) => value.toFixed(6)).join(",") ?? "";
  const [settledKey, setSettledKey] = useState(key);
  useEffect(() => {
    const timer = setTimeout(() => setSettledKey(key), CITY_LIMITS.cameraDebounceMs);
    return () => clearTimeout(timer);
  }, [key]);
  return useMemo(() => settledKey ? settledKey.split(",").map(Number) as Bounds : null, [settledKey]);
}

/**
 * Server-state keys include region/network and bounded viewport identity.
 * Consuming TanStack's signal aborts obsolete requests; no previous-region
 * placeholder data is reused while a new selection is loading.
 */
export function useCityData(camera: CameraSnapshot | null, development = false) {
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState({regionId: "", networkId: ""});
  const cameraBounds = useCameraBounds(camera);
  const configQuery = useQuery({
    queryKey: ["city", "config"],
    queryFn: ({signal}) => readCityJSON("/api/city/config", CityConfigSchema, signal),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const regionsQuery = useQuery({
    queryKey: ["city", "regions"],
    queryFn: ({signal}) => fetchCityRegions(signal),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });
  const regions = cityRegionsForMode(regionsQuery.data?.items ?? [], development);
  const region = preferredCityRegion(regions, selection.regionId);
  const regionId = region?.id ?? "";
  const networksQuery = useQuery({
    queryKey: ["city", "networks", regionId],
    queryFn: ({signal}) => fetchCityNetworks(regionId, signal),
    enabled: Boolean(regionId),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });
  const networks = cityNetworksForMode(networksQuery.data?.items ?? [], development);
  const network = (selection.regionId === regionId
    ? networks.find((value) => value.id === selection.networkId) : undefined)
    ?? networks.find((value) => value.status === "published")
    ?? networks[0] ?? null;
  const networkId = network?.id ?? "";
  const sourceId = network?.data_source_id ?? "";
  const boundaryQuery = useQuery({
    queryKey: ["city", "boundary", regionId],
    queryFn: ({signal}) => fetchCityBoundary(regionId, signal),
    enabled: Boolean(regionId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const sourceQuery = useQuery({
    queryKey: ["city", "source", sourceId],
    queryFn: ({signal}) => fetchCitySource(sourceId, signal),
    enabled: Boolean(sourceId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const validationQuery = useQuery({
    queryKey: ["city", "validation", networkId],
    queryFn: ({signal}) => fetchCityValidation(networkId, signal),
    enabled: Boolean(networkId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const viewport = region ? cityRequestBounds(cameraBounds, region.bounds)
    : {bounds: null, state: "zoom" as const};
  const bboxKey = viewport.bounds?.join(",") ?? "";
  const queryBounds = useMemo(() => bboxKey ? bboxKey.split(",").map(Number) as Bounds : null, [bboxKey]);
  const roadsQuery = useQuery({
    queryKey: ["city", "spatial", "roads", regionId, networkId, bboxKey],
    queryFn: ({signal}) => {
      if (!queryBounds) throw new Error("Select a bounded map extent first.");
      return fetchCityRoads(networkId, queryBounds, signal);
    },
    enabled: Boolean(networkId && queryBounds),
    ...CITY_SPATIAL_QUERY_OPTIONS,
  });
  const intersectionsQuery = useQuery({
    queryKey: ["city", "spatial", "intersections", regionId, networkId, bboxKey],
    queryFn: ({signal}) => {
      if (!queryBounds) throw new Error("Select a bounded map extent first.");
      return fetchCityIntersections(networkId, queryBounds, signal);
    },
    enabled: Boolean(networkId && queryBounds),
    ...CITY_SPATIAL_QUERY_OPTIONS,
  });
  const roads = queryBounds ? roadsQuery.data?.items ?? EMPTY_ROADS : EMPTY_ROADS;
  const intersections = queryBounds ? intersectionsQuery.data?.items ?? EMPTY_INTERSECTIONS : EMPTY_INTERSECTIONS;
  const boundary = boundaryQuery.data ?? null;
  const sceneData = useMemo<SceneData>(() => ({
    region, boundary, network, roads, intersections,
  }), [region, boundary, network, roads, intersections]);
  const selectRegion = useCallback((id: string) => {
    void queryClient.cancelQueries({queryKey: ["city", "spatial"]});
    setSelection({regionId: id, networkId: ""});
  }, [queryClient]);
  const selectNetwork = useCallback((id: string) => {
    void queryClient.cancelQueries({queryKey: ["city", "spatial"]});
    setSelection({regionId, networkId: id});
  }, [queryClient, regionId]);
  const retry = useCallback(() => {
    void queryClient.invalidateQueries({queryKey: ["city"]});
  }, [queryClient]);
  const queries = [configQuery, regionsQuery, networksQuery, boundaryQuery, sourceQuery, validationQuery, roadsQuery, intersectionsQuery];
  const errors = Array.from(new Set(queries.filter((query) => query.isError).map((query) =>
    query.error instanceof Error ? query.error.message : "Geographic service is unavailable. Retry the request.")));
  const truncated = Boolean(roadsQuery.data?.truncated || intersectionsQuery.data?.truncated);
  const messages: string[] = [];
  if (regionsQuery.data?.truncated || networksQuery.data?.truncated) messages.push("Catalog limited to the first 500 registered items.");
  if (network && viewport.state === "outside") messages.push("The current view is outside the selected study region. Fly to the study region to load its network.");
  if (network && viewport.state === "zoom") messages.push("Zoom closer to load network geometry within a one-degree map extent.");
  if (truncated) messages.push("Display budget reached: at most 500 features and 25,000 coordinate positions per layer. Zoom closer to inspect remaining features.");
  return {
    config: configQuery.data ?? null,
    regions, regionId, selectRegion, region, boundary,
    networks, networkId, selectNetwork, network,
    roads, intersections,
    source: sourceQuery.data ?? null,
    validation: validationQuery.data ?? null,
    sceneData,
    loading: configQuery.isLoading || regionsQuery.isLoading || networksQuery.isLoading,
    geometryLoading: boundaryQuery.isLoading || roadsQuery.isLoading || intersectionsQuery.isLoading,
    errors, messages, retry,
    roadTotal: queryBounds ? roadsQuery.data?.total ?? 0 : 0,
    intersectionTotal: queryBounds ? intersectionsQuery.data?.total ?? 0 : 0,
    truncated,
    viewportState: viewport.state,
  };
}

export type CityData = ReturnType<typeof useCityData>;
