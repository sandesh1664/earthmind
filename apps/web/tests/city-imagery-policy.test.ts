import assert from "node:assert/strict";
import test from "node:test";
import { effectiveImageryMode, imageryDescription } from "../lib/city/provider-policy";
import type { CityConfig } from "../lib/city/types";

const config: CityConfig = {imageryMode:"local-osm",ionPublicToken:null,imageryAssetId:3812,terrainAssetId:1,diagnosticsEnabled:false};

test("synthetic scope always labels the renderer's actual Natural Earth mode", () => {
  assert.equal(effectiveImageryMode(config,true),"natural-earth");
  assert.equal(effectiveImageryMode({...config,imageryMode:"ion",ionPublicToken:"public-token"},true),"natural-earth");
  assert.match(imageryDescription(config,true),/Natural Earth reference only/);
  assert.doesNotMatch(imageryDescription(config,true),/OpenStreetMap cartography/);
});

test("imagery descriptions disclose missing credentials and reference resolution without promising coverage", () => {
  assert.match(imageryDescription(config,false),/no satellite imagery/);
  assert.match(imageryDescription({...config,imageryMode:"ion"},false),/blocked: public token missing.*low-resolution Natural Earth/);
  assert.match(imageryDescription({...config,imageryMode:"ion",ionPublicToken:"public-token"},false),/requested.*depend on the provider/);
});
