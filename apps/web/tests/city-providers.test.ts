import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LayerManager } from "../components/city/LayerManager";
import { hasBuildingTileContent, ProviderReadiness, RenderedGeometryReadiness } from "../components/city/runtime/provider-readiness";
import { DEFAULT_LAYERS, type ViewerStatus } from "../lib/city/types";

test("a tile failure while async context loads cannot be overwritten by ready", () => {
  const load = new ProviderReadiness();
  assert.equal(load.hasFailed, false);
  assert.equal(load.fail(), true);
  assert.equal(load.hasFailed, true, "async completion can skip installing a terminal readiness waiter");
  assert.equal(load.commitReady(), false);
  assert.equal(load.fail(), false);
  assert.equal(new ProviderReadiness().commitReady(), true, "a new toggle/load can recover");
});

test("readiness commits once and a later tile error remains reportable", () => {
  const load = new ProviderReadiness();
  assert.equal(load.commitReady(), true);
  assert.equal(load.commitReady(), false);
  assert.equal(load.fail(), true);
  assert.equal(load.commitReady(), false);
});

test("new native geometry must finish preparation and reach a further frame before ready", () => {
  const frames = new RenderedGeometryReadiness();
  assert.equal(frames.observe(0,false),false,"an empty scene cannot prove source geometry");
  assert.equal(frames.observe(5,true),false,"pending native batches are still preparing");
  assert.equal(frames.observe(5,false),false,"preparation alone is not a further rendered frame");
  assert.equal(frames.observe(5,true),false,"new pending batches reset the frame gate");
  assert.equal(frames.observe(5,false),false);
  assert.equal(frames.observe(5,false),true);
});

test("building readiness requires concrete content instead of tileset/root metadata", () => {
  assert.equal(hasBuildingTileContent(undefined), false);
  assert.equal(hasBuildingTileContent({url:"tileset.json",featuresLength:0,trianglesLength:0,geometryByteLength:0}), false);
  assert.equal(hasBuildingTileContent({featuresLength:NaN,trianglesLength:-1,geometryByteLength:"2048"}), false);
  assert.equal(hasBuildingTileContent({featuresLength:3}), true);
  assert.equal(hasBuildingTileContent({trianglesLength:12}), true);
  assert.equal(hasBuildingTileContent({geometryByteLength:2048}), true);
  assert.equal(hasBuildingTileContent({innerContents:[{featuresLength:0},{innerContents:[{trianglesLength:20}]}]}), true);
  assert.equal(hasBuildingTileContent({innerContents:[{},null]}), false);
});

function status(): ViewerStatus {
  return {
    phase:"ready",message:"Globe ready",roadCount:0,intersectionCount:0,
    imagery:{status:"blocked",message:"Cesium ion token missing; Natural Earth II reference fallback is active"},
    buildings:{status:"off",message:"Buildings hidden"},
    terrain:{status:"blocked",message:"Local OSM height context requires the WGS84 ellipsoid"},
  };
}

test("provider blocked reasons stay visible even when a token exists", () => {
  const html = renderToStaticMarkup(createElement(LayerManager,{
    layers:{...DEFAULT_LAYERS,terrain:true},onChange:()=>{},status:status(),hasProviderAccess:true,
  }));
  assert.match(html,/Local OSM height context requires the WGS84 ellipsoid/);
  assert.match(html,/Natural Earth II reference fallback is active/);
  assert.equal((html.match(/>Blocked<\/span>/g) ?? []).length,2);
  assert.doesNotMatch(html,/disabled=""/,"selected blocked layers remain switchable off");
});

test("missing-token imagery fallback can be disabled while unselected blocked terrain cannot be enabled", () => {
  const html = renderToStaticMarkup(createElement(LayerManager,{
    layers:{...DEFAULT_LAYERS,buildings:false},onChange:()=>{},status:status(),hasProviderAccess:false,
  }));
  assert.match(html,/<input[^>]*aria-label="Geographic basemap"[^>]*checked=""/);
  assert.doesNotMatch(html,/<input[^>]*disabled=""[^>]*aria-label="Geographic basemap"/);
  assert.match(html,/<input[^>]*disabled=""[^>]*aria-label="World terrain"/);
});
