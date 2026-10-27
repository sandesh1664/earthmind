import assert from "node:assert/strict";
import test from "node:test";
import { z } from "zod";
import { QueryClient, QueryObserver } from "@tanstack/react-query";
import {
  CITY_LIMITS,
  CityDataError,
  CityIntersectionSchema,
  CityRoadSchema,
  cityRequestBounds,
  fetchCityBoundary,
  fetchCityIntersections,
  fetchCityNetworks,
  fetchCityRegions,
  fetchCityRoads,
  readCityJSON,
} from "../lib/city/api";
import { proxyGeospatial } from "../lib/geospatial-proxy";
import { CITY_SPATIAL_QUERY_OPTIONS } from "../lib/city/query-options";
import type { Bounds } from "../lib/city/types";

const networkId = "11111111-1111-4111-8111-111111111111";
const regionId = "22222222-2222-4222-8222-222222222222";
const otherNetworkId = "33333333-3333-4333-8333-333333333333";
const bounds: Bounds = [55.2685, 25.19, 55.2805, 25.2];
const identifier = (index: number) => `aaaaaaaa-aaaa-4aaa-8aaa-${String(index).padStart(12, "0")}`;
const signal = () => new AbortController().signal;
const response = (body: unknown) => Response.json(body);
const road = (index = 1) => ({
  type: "Feature",
  id: identifier(index),
  geometry: {type: "LineString", coordinates: [[55.27, 25.192], [55.274, 25.192]]},
  properties: {
    network_version_id: networkId,
    sumo_edge_id: `provisional:e${index}`,
    source_edge_id: `synthetic:e${index}`,
    name: `Synthetic road ${index}`,
    road_class: "synthetic_local",
    lane_count: 1,
    speed_limit_mps: 8,
    length_m: 403.17,
    is_one_way: true,
    is_synthetic: true,
    private_access_token: "excluded",
  },
});
const intersection = () => ({
  type: "Feature",
  id: identifier(1000),
  geometry: {type: "Point", coordinates: [55.27, 25.192]},
  properties: {
    network_version_id: networkId,
    source_node_id: "synthetic:n0",
    intersection_type: "synthetic_junction",
    is_synthetic: true,
  },
});
const collection = (features: unknown[], total = features.length, offset = 0) => ({
  type: "FeatureCollection", features, total, limit: 100, offset,
});
const region = (index = 1) => ({
  id: identifier(index), slug: `synthetic-${index}`, name: `Synthetic ${index}`,
  country_code: "AE", emirate: "Dubai", timezone: "Asia/Dubai", area_km2: 1.3,
  centroid: [55.2745, 25.195], bounds, metadata: {is_synthetic: true},
  created_at: "2026-10-27T00:00:00Z", updated_at: "2026-10-27T00:00:00Z",
});

test("city road adapters retain actual inspector fields and strip private metadata", () => {
  const parsed = CityRoadSchema.parse(road());
  assert.equal(parsed.properties.name, "Synthetic road 1");
  assert.equal(parsed.properties.speed_limit_mps, 8);
  assert.equal(parsed.properties.source_edge_id, "synthetic:e1");
  assert.equal(JSON.stringify(parsed).includes("private_access_token"), false);
});

test("road schemas reject wrong geometry, invalid ranges, empty extent and nonfinite values", () => {
  for (const geometry of [
    {type: "Point", coordinates: [55, 25]},
    {type: "LineString", coordinates: [[181, 25], [55, 25]]},
    {type: "LineString", coordinates: [[55, 91], [55, 25]]},
    {type: "LineString", coordinates: [[55, 25, 0], [55, 25, 0]]},
    {type: "LineString", coordinates: [[55, 25], [55, 25]]},
    {type: "LineString", coordinates: [[Number.NaN, 25], [55, 25]]},
  ]) assert.equal(CityRoadSchema.safeParse({...road(), geometry}).success, false);
  assert.equal(CityRoadSchema.safeParse({...road(), properties: {...road().properties, speed_limit_mps: Infinity}}).success, false);
});

test("absent node signal metadata stays absent instead of becoming a fabricated false", () => {
  const parsed = CityIntersectionSchema.parse(intersection());
  assert.equal("is_signalized" in parsed.properties, false);
  assert.equal("sumo_node_id" in parsed.properties, false);
});

test("map bbox clips the camera to a region without computing metric geometry", () => {
  assert.deepEqual(cityRequestBounds([55.27, 25.18, 55.29, 25.198], bounds), {
    bounds: [55.27, 25.19, 55.2805, 25.198], state: "ready",
  });
  assert.deepEqual(cityRequestBounds(null, bounds), {bounds, state: "ready"});
  assert.deepEqual(cityRequestBounds([0, 0, 1, 1], bounds), {bounds: null, state: "outside"});
});

test("camera requests reject invalid, wrapping, excessive or sub-precision extents", () => {
  for (const view of [
    [55, 25, 54, 26], [NaN, 25, 56, 26], [55, 25, 55, 26], [55, 25, 55.00000001, 26],
  ] as Bounds[]) assert.equal(cityRequestBounds(view, [54, 24, 57, 28]).state, "zoom");
  assert.equal(cityRequestBounds(null, [54, 24, 57, 28]).state, "zoom");
  assert.equal(cityRequestBounds([54, 24, 57, 28], [54, 24, 57, 28]).bounds, null);
});

test("equivalent camera extents generate stable quantized request bounds", () => {
  assert.deepEqual(cityRequestBounds([55.27000001, 25.19200001, 55.27600001, 25.19800001], bounds),
    cityRequestBounds([55.27000002, 25.19200002, 55.27600002, 25.19800002], bounds));
});

test("fetches real-contract roads through the same-origin proxy with bounded bbox and pagination", async () => {
  const urls: string[] = [];
  const value = await fetchCityRoads(networkId, bounds, signal(), async (input, init) => {
    urls.push(String(input));
    assert.ok(init?.signal instanceof AbortSignal);
    return response(collection([road()]));
  });
  const url = new URL(urls[0]!, "http://localhost");
  assert.equal(url.pathname, `/api/geospatial/networks/${networkId}/edges`);
  assert.equal(url.searchParams.get("limit"), "100");
  assert.equal(url.searchParams.get("bbox"), bounds.join(","));
  assert.equal(value.items[0]?.properties.name, "Synthetic road 1");
  assert.equal(value.truncated, false);
});

test("pagination stops after 500 features and reports remaining data explicitly", async () => {
  let requests = 0;
  const result = await fetchCityRoads(networkId, bounds, signal(), async (input) => {
    requests++;
    const offset = Number(new URL(String(input), "http://localhost").searchParams.get("offset"));
    return response(collection(Array.from({length: 100}, (_, i) => road(offset + i + 1)), 1200, offset));
  });
  assert.equal(requests, 5);
  assert.equal(result.items.length, 500);
  assert.equal(result.total, 1200);
  assert.equal(result.truncated, true);
});

test("aggregate coordinate budget truncates before loading another page", async () => {
  const features = Array.from({length: 6}, (_, index) => ({
    ...road(index + 1),
    geometry: {type: "LineString", coordinates: Array.from({length: 5000}, (_, point) => [55.27 + point / 1_000_000, 25.192])},
  }));
  let requests = 0;
  const result = await fetchCityRoads(networkId, bounds, signal(), async () => {
    requests++;
    return response(collection(features));
  });
  assert.equal(requests, 1);
  assert.equal(result.items.length, 5);
  assert.equal(result.coordinateCount, 25_000);
  assert.equal(result.truncated, true);
});

test("inconsistent counts, offsets, empty pages and duplicate identifiers fail visibly", async () => {
  for (const body of [
    collection([road()], 1, 10), collection([], 1), collection([road(), road()], 2), collection([road()], 200),
  ]) await assert.rejects(fetchCityRoads(networkId, bounds, signal(), async () => response(body)), CityDataError);
});

test("network changes during pagination reject mixed snapshots", async () => {
  let requests = 0;
  await assert.rejects(fetchCityRoads(networkId, bounds, signal(), async () => {
    requests++;
    return response(requests === 1 ? collection(Array.from({length: 100}, (_, i) => road(i)), 101) : collection([road(100)], 102, 100));
  }), /changed while loading/);
  assert.equal(requests, 2);
});

test("features from a different network cannot enter the selected scene", async () => {
  await assert.rejects(fetchCityRoads(networkId, bounds, signal(), async () => response(collection([
    {...road(), properties: {...road().properties, network_version_id: otherNetworkId}},
  ]))), /did not match the selected network/);
});

test("intersection loads preserve known signal status and synthetic identity", async () => {
  const node = intersection();
  const result = await fetchCityIntersections(networkId, bounds, signal(), async () => response(collection([
    {...node, properties: {...node.properties, is_signalized: true}},
  ])));
  assert.equal(result.items[0]?.properties.is_signalized, true);
  assert.equal(result.items[0]?.properties.is_synthetic, true);
});

test("aborted queries never start a request or return a stale successful result", async () => {
  const controller = new AbortController();
  controller.abort();
  let requests = 0;
  await assert.rejects(fetchCityRoads(networkId, bounds, controller.signal, async () => {
    requests++;
    return response(collection([road()]));
  }), {name: "AbortError"});
  assert.equal(requests, 0);
  const pending = new AbortController();
  await assert.rejects(fetchCityRoads(networkId, bounds, pending.signal, async (_url, init) => {
    pending.abort();
    assert.equal(init?.signal?.aborted, true);
    return response(collection([road()]));
  }), {name: "AbortError"});
});

test("a region/network change cancels the next pagination response before parsing", async () => {
  const controller = new AbortController();
  let requests = 0;
  await assert.rejects(fetchCityRoads(networkId, bounds, controller.signal, async () => {
    requests++;
    if (requests === 2) controller.abort();
    return response(collection(Array.from({length: 100}, (_, i) => road(i + 100 * (requests - 1))), 300, 100 * (requests - 1)));
  }), {name: "AbortError"});
  assert.equal(requests, 2);
});

test("oversized declared and streaming JSON responses are rejected with a display-budget message", async () => {
  await assert.rejects(readCityJSON("/test", z.unknown(), signal(), async () => new Response("{}", {
    headers: {"content-length": String(CITY_LIMITS.responseBytes + 1)},
  })), /display budget/);
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {controller.enqueue(new Uint8Array(CITY_LIMITS.responseBytes + 1));},
    cancel() {cancelled = true;},
  });
  await assert.rejects(readCityJSON("/test", z.unknown(), signal(), async () => new Response(stream)), /display budget/);
  assert.equal(cancelled, true);
});

test("non-JSON, invalid geometry, missing resources and service failures stay explicit", async () => {
  await assert.rejects(readCityJSON("/test", z.unknown(), signal(), async () => new Response("<html>Unavailable</html>")), /invalid JSON/);
  await assert.rejects(fetchCityRoads(networkId, bounds, signal(), async () => response(collection([intersection()]))), /invalid or unsupported/);
  await assert.rejects(readCityJSON("/test", z.unknown(), signal(), async () => new Response("", {status: 404})), /no longer available/);
  await assert.rejects(readCityJSON("/test", z.unknown(), signal(), async () => new Response("", {status: 503})), /HTTP 503/);
});

test("region catalogs paginate within the same 500-item budget", async () => {
  let requests = 0;
  const result = await fetchCityRegions(signal(), async (input) => {
    requests++;
    const offset = Number(new URL(String(input), "http://localhost").searchParams.get("offset"));
    return response({items: Array.from({length: 100}, (_, index) => region(offset + index)), total: 1000, limit: 100, offset});
  });
  assert.equal(requests, 5);
  assert.equal(result.items.length, 500);
  assert.equal(result.truncated, true);
});

test("network registry rejects another region and missing boundary identity", async () => {
  await assert.rejects(fetchCityNetworks(regionId, signal(), async () => response({items: [{
    id: networkId, region_id: otherNetworkId, data_source_id: null, version_label: "synthetic-v1",
    status: "published", checksum_sha256: "a".repeat(64), source_format: "synthetic_geojson",
    projection_srid: 4326, node_count: 6, edge_count: 8, is_validated: true,
    validation_summary: {status: "VALID"}, bounds, created_at: "2026-10-27T00:00:00Z", is_synthetic: true,
  }], total: 1, limit: 100, offset: 0})), /did not match the selected study region/);
  await assert.rejects(fetchCityBoundary(regionId, signal(), async () => response({
    type: "Feature", id: networkId,
    geometry: {type: "MultiPolygon", coordinates: [[[[55.27, 25.19], [55.28, 25.19], [55.28, 25.20], [55.27, 25.19]]]]},
    properties: {id: networkId, slug: "synthetic", name: "Synthetic", is_synthetic: true, area_km2: 1.3, country_code: "AE", boundary_policy: "Illustrative"},
  })), /did not match the selected study region/);
});

test("backward-compatible proxy allowlist retains inspector fields without private source credentials", async () => {
  const result = await proxyGeospatial(new Request(`http://localhost/api/geospatial/networks/${networkId}/edges`),
    ["networks", networkId, "edges"], async () => response(collection([road()])));
  assert.equal(result.status, 200);
  const body = await result.json();
  assert.equal(body.features[0].properties.name, "Synthetic road 1");
  assert.equal(body.features[0].properties.network_version_id, networkId);
  assert.equal(JSON.stringify(body).includes("private_access_token"), false);
});


test("camera or region query replacement aborts obsolete work and late responses cannot overwrite current data", async () => {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  let releaseOld: ((response: Response) => void) | undefined;
  let oldSignal: AbortSignal | null | undefined;
  const observer = new QueryObserver(client, {
    ...CITY_SPATIAL_QUERY_OPTIONS,
    queryKey: ["city", "spatial", "roads", regionId, networkId, bounds.join(",")],
    queryFn: ({signal: querySignal}) => fetchCityRoads(networkId, bounds, querySignal, async (_url, init) => {
      oldSignal = init?.signal;
      return new Promise<Response>((resolve) => {releaseOld = resolve;});
    }),
  });
  const unsubscribe = observer.subscribe(() => {});
  assert.ok(releaseOld);
  observer.setOptions({
    ...CITY_SPATIAL_QUERY_OPTIONS,
    queryKey: ["city", "spatial", "roads", regionId, otherNetworkId, bounds.join(",")],
    queryFn: ({signal: querySignal}) => fetchCityRoads(otherNetworkId, bounds, querySignal, async () => response(collection([
      {...road(), properties: {...road().properties, network_version_id: otherNetworkId}},
    ]))),
  });
  assert.equal(oldSignal?.aborted, true);
  await observer.refetch();
  releaseOld(response(collection([road()])));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(observer.getCurrentResult().data?.items[0]?.properties.network_version_id, otherNetworkId);
  assert.equal(client.getQueryData(["city", "spatial", "roads", regionId, networkId, bounds.join(",")]), undefined);
  assert.equal(client.getQueryCache().find({queryKey: ["city", "spatial", "roads", regionId, networkId, bounds.join(",")], exact: true}), undefined);
  unsubscribe();
  client.clear();
});

test("browser request cancellation propagates through the read-only Next proxy to FastAPI fetch", async () => {
  const controller = new AbortController();
  const request = new Request(`http://localhost/api/geospatial/networks/${networkId}/edges`, {signal: controller.signal});
  let upstreamSignal: AbortSignal | null | undefined;
  const pending = proxyGeospatial(request, ["networks", networkId, "edges"], async (_url, init) => {
    upstreamSignal = init?.signal;
    return new Promise<Response>((_resolve, reject) => {
      upstreamSignal?.addEventListener("abort", () => reject(upstreamSignal?.reason), {once: true});
    });
  });
  controller.abort();
  assert.equal(upstreamSignal?.aborted, true);
  assert.equal((await pending).status, 503);
});


test("inactive camera viewports are garbage-collected while the active viewport retains its fresh shared cache", async () => {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const oldKey = ["city", "spatial", "roads", regionId, networkId, bounds.join(",")];
  const currentBounds: Bounds = [55.27, 25.191, 55.277, 25.199];
  const currentKey = ["city", "spatial", "roads", regionId, networkId, currentBounds.join(",")];
  let requests = 0;
  const fetcher: typeof fetch = async () => {
    requests++;
    return response(collection([road()]));
  };
  const currentOptions = {
    ...CITY_SPATIAL_QUERY_OPTIONS,
    queryKey: currentKey,
    queryFn: ({signal: querySignal}: {signal: AbortSignal}) => fetchCityRoads(networkId, currentBounds, querySignal, fetcher),
  };
  const observer = new QueryObserver(client, {
    ...CITY_SPATIAL_QUERY_OPTIONS,
    queryKey: oldKey,
    queryFn: ({signal: querySignal}) => fetchCityRoads(networkId, bounds, querySignal, fetcher),
  });
  const unsubscribe = observer.subscribe(() => {});
  await observer.refetch();
  assert.ok(client.getQueryData(oldKey));
  observer.setOptions(currentOptions);
  await observer.refetch();
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(client.getQueryCache().find({queryKey: oldKey, exact: true}), undefined);
  assert.ok(client.getQueryCache().find({queryKey: currentKey, exact: true}));
  assert.equal(observer.getCurrentResult().data?.items.length, 1);
  const completedRequests = requests;
  observer.setOptions({...currentOptions});
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(requests, completedRequests, "same active key stays fresh instead of refetching");
  unsubscribe();
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(client.getQueryCache().find({queryKey: currentKey, exact: true}), undefined);
  client.clear();
});

test("public OSM provenance preserves bounded many-source IDs and strips private tags",()=>{
 const value=road();
 const parsed=CityRoadSchema.parse({...value,properties:{...value.properties,metadata:{osm_way_id:"123",osm_way_ids:["123","456"],lane_count_source:"inferred_by_netconvert",original_osm_tags:{secret:"private"},private_token:"private"}}});
 assert.deepEqual(parsed.properties.metadata?.osm_way_ids,["123","456"]);
 assert.equal(JSON.stringify(parsed).includes("private"),false);
 assert.equal(CityRoadSchema.safeParse({...value,properties:{...value.properties,metadata:{osm_way_ids:Array(65).fill("123")}}}).success,false);
});
