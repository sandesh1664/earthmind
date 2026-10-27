import { test } from "node:test";
import assert from "node:assert/strict";
import { readPublicCityConfig } from "../lib/city/config";

test("missing public visualization token produces the self-hosted OSM configuration", () => {
  assert.deepEqual(readPublicCityConfig({}), {
    ionPublicToken: null, imageryMode: "local-osm", imageryAssetId: 3812, terrainAssetId: 1, diagnosticsEnabled: false,
  });
});
test("viewer configuration exposes only the explicitly public token and allowlisted settings", () => {
  const publicToken = "public-scoped-visualization-token-example";
  const config = readPublicCityConfig({ CESIUM_ION_PUBLIC_TOKEN: publicToken,
    CESIUM_ION_SECRET_TOKEN: "private-sentinel-value", EARTHMIND_DEV_WRITE_TOKEN: "private-write-sentinel",
    DATABASE_URL: "private-database-sentinel", CITY_DIAGNOSTICS_ENABLED: "true" });
  assert.equal(config.ionPublicToken, publicToken);
  assert.equal(config.diagnosticsEnabled, true);
  assert.equal(JSON.stringify(config).includes("private-"), false);
});
test("malformed visualization configuration fails closed without forwarding arbitrary URLs", () => {
  assert.throws(() => readPublicCityConfig({ CESIUM_ION_IMAGERY_ASSET_ID: "https://example.com" }));
  assert.throws(() => readPublicCityConfig({ CESIUM_ION_PUBLIC_TOKEN: "untrusted token with whitespace" }));
  assert.throws(() => readPublicCityConfig({ CESIUM_ION_TERRAIN_ASSET_ID: "-2" }));
});

test("imagery modes are allowlisted, not arbitrary tile URLs",()=>{
 assert.equal(readPublicCityConfig({CITY_IMAGERY_MODE:"natural-earth"}).imageryMode,"natural-earth");
 assert.throws(()=>readPublicCityConfig({CITY_IMAGERY_MODE:"https://arbitrary.example/tiles"}));
});
