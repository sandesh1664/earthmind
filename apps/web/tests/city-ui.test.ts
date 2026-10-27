import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  FeatureInspector,
  recorded,
  selectedFeature,
} from "../components/city/FeatureInspector";
import { LayerManager, toggleLayer } from "../components/city/LayerManager";
import { CAMERA_PRESETS, MapToolbar } from "../components/city/MapToolbar";
import { ViewerErrorBoundary } from "../components/city/ViewerErrorBoundary";
import {
  DEFAULT_LAYERS,
  type RoadFeature,
  type IntersectionFeature,
} from "../lib/city/types";

const road: RoadFeature = {
  type: "Feature",
  id: "road-test",
  geometry: {
    type: "LineString",
    coordinates: [
      [55.27, 25.192],
      [55.274, 25.192],
    ],
  },
  properties: {
    network_version_id: "network-test",
    sumo_edge_id: "provisional:unit-edge",
    road_class: "synthetic_local",
    lane_count: 2,
    speed_limit_mps: null,
    length_m: 123.45,
    is_one_way: true,
    is_synthetic: true,
  },
};
const node: IntersectionFeature = {
  type: "Feature",
  id: "node-test",
  geometry: { type: "Point", coordinates: [55.27, 25.192] },
  properties: {
    network_version_id: "network-test",
    source_node_id: "synthetic:unit-node",
    intersection_type: "synthetic",
    is_synthetic: true,
  },
};
const noAction = () => undefined;
const inspector = (
  selection: Parameters<typeof FeatureInspector>[0]["selection"],
) =>
  renderToStaticMarkup(
    createElement(FeatureInspector, {
      selection,
      roads: [road],
      intersections: [node],
      network: null,
      source: null,
      validation: null,
      onDeselect: noAction,
      onZoom: noAction,
    }),
  );

test("layer controls expose all eight scene switches and block only unavailable licensed providers", () => {
  const html = renderToStaticMarkup(
    createElement(LayerManager, {
      layers: DEFAULT_LAYERS,
      onChange: noAction,
      status: null,
      hasProviderAccess: false,
    }),
  );
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 8);
  assert.equal((html.match(/disabled=""/g) ?? []).length, 2);
  assert.match(html, /aria-label="Study region"/);
  assert.match(html, /aria-label="Geographic basemap"/);
  assert.match(html, /Blocked · public provider token required/);
  assert.match(html, /PostGIS boundary/);
});

test("configured provider controls become available without claiming they have loaded", () => {
  const html = renderToStaticMarkup(
    createElement(LayerManager, {
      layers: DEFAULT_LAYERS,
      onChange: noAction,
      status: null,
      hasProviderAccess: true,
    }),
  );
  assert.equal((html.match(/disabled=""/g) ?? []).length, 0);
  assert.doesNotMatch(html, /Blocked ·/);
  assert.doesNotMatch(html, /Loading<|>Error</);
});

test("layer changes preserve other settings and do not mutate the previous state", () => {
  const next = toggleLayer(DEFAULT_LAYERS, "roads");
  assert.equal(next.roads, false);
  assert.equal(DEFAULT_LAYERS.roads, true);
  assert.equal(next.boundary, DEFAULT_LAYERS.boundary);
  assert.equal(toggleLayer(next, "roads").roads, true);
});

test("road inspector reflects backend numbers and does not invent absent speed/source values", () => {
  const html = inspector({ kind: "road", id: road.id });
  assert.match(html, /provisional:unit-edge/);
  assert.match(html, /data-testid="selected-road-lanes">2</);
  assert.match(html, /data-testid="selected-road-length">123.45</);
  assert.match(html, /SYNTHETIC DATA/);
  assert.match(html, /Speed limit · m\/s<\/dt><dd>Not recorded/);
  assert.match(html, /One-way<\/dt><dd>Yes/);
  assert.doesNotMatch(html, /undefined|>null</);
  assert.match(html, /Zoom to feature/);
  assert.match(html, /Deselect/);
});

test("intersection inspector distinguishes absent signal metadata from a false stored flag", () => {
  const html = inspector({ kind: "intersection", id: node.id });
  assert.match(html, /Simulated signalized flag<\/dt><dd>Not recorded/);
  assert.match(html, /synthetic:unit-node/);
  assert.doesNotMatch(html, /Real signal|verified traffic signal/i);
});

test("selection matches both category and stable feature identifier", () => {
  assert.equal(
    selectedFeature({ kind: "road", id: road.id }, [road], [node]),
    road,
  );
  assert.equal(
    selectedFeature({ kind: "intersection", id: node.id }, [road], [node]),
    node,
  );
  assert.equal(
    selectedFeature({ kind: "intersection", id: road.id }, [road], [node]),
    null,
  );
  assert.equal(
    selectedFeature({ kind: "road", id: "stale" }, [road], [node]),
    null,
  );
  assert.equal(selectedFeature(null, [road], [node]), null);
});

test("unknown or stale selection uses the empty inspector rather than fabricated metadata", () => {
  const html = inspector({ kind: "road", id: "stale" });
  assert.match(html, /Inspect the study network/);
  assert.doesNotMatch(html, /selected-road-lanes/);
});

test("building property values render as escaped text and only supplied fields", () => {
  const html = inspector({
    kind: "building",
    id: "provider:building",
    properties: { name: "<script>alert(1)</script>", height: 32 },
  });
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /height<\/dt><dd>32/);
  assert.doesNotMatch(html, /Lane count|Speed limit/);
  assert.match(html, /Building coverage and metadata vary/);
});

test("camera toolbar has all three destination presets and disables unavailable selection commands", () => {
  assert.deepEqual(
    CAMERA_PRESETS.map((item) => item.label),
    ["Dubai overview", "Downtown Dubai", "Business Bay"],
  );
  const html = renderToStaticMarkup(
    createElement(MapToolbar, {
      command: noAction,
      disabled: false,
      hasRegion: true,
      hasSelection: false,
    }),
  );
  for (const label of [
    "Zoom to study region",
    "Zoom to selected feature",
    "Top-down view",
    "Perspective view",
    "Reset camera",
    "Zoom in",
    "Zoom out",
  ])
    assert.ok(html.includes(`aria-label="${label}"`));
  assert.equal((html.match(/disabled=""/g) ?? []).length, 1);
});

test("unavailable renderer keeps all ten camera buttons safely disabled", () => {
  const html = renderToStaticMarkup(
    createElement(MapToolbar, {
      command: noAction,
      disabled: true,
      hasRegion: true,
      hasSelection: true,
    }),
  );
  assert.equal((html.match(/disabled=""/g) ?? []).length, 10);
});

test("inspector value formatting keeps zero and false distinct from missing values", () => {
  assert.equal(recorded(0), "0");
  assert.equal(recorded(false), "No");
  assert.equal(recorded(undefined), "Not recorded");
  assert.equal(recorded(null), "Not recorded");
  assert.equal(recorded(Number.NaN), "Not recorded");
});

test("viewer error boundary preserves the normal child surface and exposes a deterministic fallback state", () => {
  const html = renderToStaticMarkup(
    createElement(ViewerErrorBoundary, { retry: noAction }, "Renderer child"),
  );
  assert.match(html, /Renderer child/);
  assert.deepEqual(ViewerErrorBoundary.getDerivedStateFromError(), {
    failed: true,
  });
});

test("real OSM inspector distinguishes converter inference from source lane tags", () => {
  const imported: RoadFeature = {
    ...road,
    properties: {
      ...road.properties,
      is_synthetic: false,
      source_edge_id: "osm:way:12345",
      sumo_edge_id: "12345#2",
      name: "Source road name",
      lane_count: 3,
      metadata: {
        osm_way_id: "12345", lane_count_source: "inferred_by_netconvert",
        osm_lanes: null, osm_maxspeed: null,
        turn_restrictions_status: "partial_osm_relations_no_field_verification",
        sumo_identifier_verified: true, geometry_derivation: "sumo_lane_centerline_from_osm",
      },
    },
  };
  const render = (feature: RoadFeature) => renderToStaticMarkup(createElement(FeatureInspector, {
    selection: {kind: "road", id: feature.id}, roads: [feature], intersections: [],
    network: null, source: null, validation: null, onDeselect: noAction, onZoom: noAction,
  }));
  const inferred = render(imported);
  assert.match(inferred, /REAL GEOGRAPHIC DATA — OpenStreetMap/);
  assert.match(inferred, /data-testid="selected-road-lanes">3 · inferred by netconvert/);
  assert.match(inferred, /OSM lanes tag<\/dt><dd>Not recorded/);
  assert.match(inferred, /Partial OSM relations; not field verified/);
  assert.match(inferred, /12345#2/);
  assert.doesNotMatch(inferred, /SYNTHETIC DATA|>undefined<|>null</);
  const directional = render({...imported, properties: {...imported.properties,
    metadata: {...imported.properties.metadata, lane_count_source: "osm_directional_tag", osm_lanes: "6", osm_directional_lanes: "3"},
  }});
  assert.match(directional, /3 · OSM directional tag/);
  const interpreted = render({...imported, properties: {...imported.properties,
    metadata: {...imported.properties.metadata, lane_count_source: "sumo_interpreted_osm_lanes", osm_lanes: "6"},
  }});
  assert.match(interpreted, /3 · SUMO interpretation of OSM lanes/);
});

test("unclassified imported source is not relabeled OpenStreetMap", () => {
  const feature: RoadFeature = {...road, properties: {...road.properties, is_synthetic: false}};
  const html = renderToStaticMarkup(createElement(FeatureInspector, {
    selection: {kind: "road", id: feature.id}, roads: [feature], intersections: [],
    network: null, source: null, validation: null, onDeselect: noAction, onZoom: noAction,
  }));
  assert.match(html, /IMPORTED GEOGRAPHIC DATA/);
  assert.match(html, /source provenance not recorded/);
  assert.doesNotMatch(html, /REAL GEOGRAPHIC DATA — OpenStreetMap/);
});
