import assert from "node:assert/strict";
import test from "node:test";
import type { Network, Region } from "../lib/geospatial";
import { cityNetworksForMode, cityRegionsForMode, preferredCityRegion } from "../lib/city/catalog";

const region = (id: string, synthetic: boolean): Region => ({
  id, name: id, slug: id, country_code: "AE", emirate: "Dubai", timezone: "Asia/Dubai",
  area_km2: 1, centroid: [55.27, 25.19], bounds: [55.26, 25.18, 55.28, 25.2],
  metadata: {is_synthetic: synthetic}, created_at: "2026-10-27T00:00:00Z", updated_at: "2026-10-27T00:00:00Z",
});
const real = region("dubai-downtown-business-bay-osm", false);
const fixture = region("dubai-downtown-demo", true);
const network = (id: string, synthetic: boolean): Network => ({
  id, region_id: synthetic ? fixture.id : real.id, data_source_id: null, version_label: id,
  status: "published", checksum_sha256: "a".repeat(64), source_format: synthetic ? "synthetic" : "osm",
  projection_srid: 4326, node_count: 10, edge_count: 12, is_validated: true,
  validation_summary: {status: "VALID"}, bounds: real.bounds, created_at: "2026-10-27T00:00:00Z", is_synthetic: synthetic,
});

test("real and development catalogs are disjoint; fixtures cannot silently become the default", () => {
  assert.deepEqual(cityRegionsForMode([fixture, real], false), [real]);
  assert.deepEqual(cityRegionsForMode([fixture, real], true), [fixture]);
  assert.deepEqual(cityRegionsForMode([fixture], false), []);
  assert.equal(preferredCityRegion(cityRegionsForMode([fixture], false), fixture.id), null);
});

test("real imported region is preferred even if the API returns the fixture first", () => {
  assert.equal(preferredCityRegion(cityRegionsForMode([fixture, real], false), fixture.id), real);
  const other = region("another-import", false);
  assert.equal(preferredCityRegion([other, real], ""), real);
  assert.equal(preferredCityRegion([other, real], other.id), other);
});

test("network catalog mode cannot merge real OSM and synthetic versions", () => {
  const imported = network("osm-v1", false), synthetic = network("synthetic-v1", true);
  assert.deepEqual(cityNetworksForMode([synthetic, imported], false), [imported]);
  assert.deepEqual(cityNetworksForMode([synthetic, imported], true), [synthetic]);
});
