import assert from "node:assert/strict";
import test from "node:test";
import {
  boundaryPaths,
  DataSourceSchema,
  NetworkValidationSchema,
  PositionSchema,
  RegionFeatureSchema,
  RegionListSchema,
  RegionSchema,
} from "../lib/geospatial";
import { proxyGeospatial } from "../lib/geospatial-proxy";

const id = "11111111-1111-4111-8111-111111111111";
const timestamp = "2026-10-26T12:00:00Z";
const region = {
  id,
  slug: "test-synthetic-region",
  name: "Synthetic test region",
  country_code: "AE",
  emirate: "Dubai",
  timezone: "Asia/Dubai",
  area_km2: 1.25,
  centroid: [55.274, 25.195],
  bounds: [55.27, 25.19, 55.28, 25.2],
  metadata: {
    is_synthetic: true,
    boundary_policy: "Illustrative fixture",
    private_api_token: "never forward",
  },
  created_at: timestamp,
  updated_at: timestamp,
};
const feature = {
  type: "Feature",
  id,
  geometry: {
    type: "MultiPolygon",
    coordinates: [
      [
        [
          [55.27, 25.19],
          [55.28, 25.19],
          [55.28, 25.2],
          [55.27, 25.2],
          [55.27, 25.19],
        ],
      ],
    ],
  },
  properties: {
    id,
    slug: region.slug,
    name: region.name,
    is_synthetic: true,
    area_km2: 1.25,
    country_code: "AE",
    boundary_policy: "Illustrative fixture",
  },
};

test("spatial contracts enforce finite longitude/latitude and actual metric area", () => {
  assert.equal(PositionSchema.safeParse([181, 25]).success, false);
  assert.equal(PositionSchema.safeParse([55, 91]).success, false);
  assert.equal(PositionSchema.safeParse([55, 25, 0]).success, false);
  assert.equal(PositionSchema.safeParse([Number.NaN, 25]).success, false);
  assert.equal(
    RegionSchema.safeParse({ ...region, area_km2: -1 }).success,
    false,
  );
  assert.equal(
    RegionSchema.safeParse({ ...region, bounds: [55.28, 25.19, 55.27, 25.2] })
      .success,
    false,
  );
});

test("region boundary preview uses parsed GeoJSON and finite coordinate-only paths", () => {
  const parsed = RegionFeatureSchema.parse(feature);
  const paths = boundaryPaths(parsed);
  assert.equal(paths.length, 1);
  assert.match(paths[0]!, /^M[\d., LZ]+$/);
  assert.equal(paths[0]?.includes("NaN"), false);
  assert.equal(
    RegionFeatureSchema.safeParse({
      ...feature,
      geometry: "0106000020E6100000",
    }).success,
    false,
  );
});

test("public consumer strips unapproved provenance fields", () => {
  const publicRegion = RegionSchema.parse({
    ...region,
    database_password: "private",
  });
  assert.equal(
    JSON.stringify(publicRegion).includes("private_api_token"),
    false,
  );
  assert.equal(
    JSON.stringify(publicRegion).includes("database_password"),
    false,
  );
  const data = DataSourceSchema.parse({
    id,
    provider_name: "EARTHMIND",
    dataset_name: "Synthetic fixture",
    source_type: "synthetic",
    source_url: null,
    license_identifier: null,
    attribution_text: "Project-generated",
    collected_at: timestamp,
    source_version: "fixture-1",
    checksum_sha256: "a".repeat(64),
    created_at: timestamp,
    is_synthetic: true,
    metadata: { credential: "never expose" },
  });
  assert.equal(data.license_identifier, null);
  assert.equal(JSON.stringify(data).includes("credential"), false);
  assert.equal(
    DataSourceSchema.safeParse({ ...data, source_url: "javascript:alert(1)" })
      .success,
    false,
  );
  for (const source_url of [
    "https://user:secret@example.com/data",
    "https://provider.example/data?token=secret",
    "https://127.0.0.1/data",
    "https://internal.local/data",
  ]) {
    assert.equal(
      DataSourceSchema.safeParse({ ...data, source_url }).success,
      false,
    );
  }
});

test("validation status cannot claim success for an invalid report", () => {
  const report = {
    network_id: id,
    validated: false,
    status: "INVALID",
    checks: { connectivity_valid: false },
    warnings: [],
    errors: ["Disconnected topology"],
    counts: { nodes: 6, edges: 8, components: 2, isolated_nodes: 0 },
    boundary_tolerance_m: 5,
    semantics: "Errors invalidate the network",
  };
  assert.equal(NetworkValidationSchema.safeParse(report).success, true);
  assert.equal(
    NetworkValidationSchema.safeParse({ ...report, validated: true }).success,
    false,
  );
  assert.equal(
    NetworkValidationSchema.safeParse({
      ...report,
      status: "VALID",
      validated: true,
    }).success,
    true,
  );
});

test("read-only proxy reaches allowlisted region API and validates public response", async () => {
  const fetcher: typeof fetch = async (url, init) => {
    assert.equal(url, "http://127.0.0.1:8000/api/v1/regions?limit=20&offset=0");
    assert.equal(init?.method, "GET");
    assert.equal(init?.cache, "no-store");
    assert.ok(init?.signal instanceof AbortSignal);
    assert.equal(JSON.stringify(init).includes("Dev-Token"), false);
    return Response.json({ items: [region], total: 1, limit: 20, offset: 0 });
  };
  const response = await proxyGeospatial(
    new Request("http://localhost/api/geospatial/regions?limit=20&offset=0"),
    ["regions"],
    fetcher,
  );
  assert.equal(response.status, 200);
  const payload = RegionListSchema.parse(await response.json());
  assert.equal(payload.items[0]?.id, id);
  assert.equal(JSON.stringify(payload).includes("private_api_token"), false);
});

test("proxy rejects traversal, arbitrary endpoints, invalid IDs and unbounded queries before fetch", async () => {
  const fetcher: typeof fetch = async () => {
    throw new Error("upstream must not be called");
  };
  for (const [path, query] of [
    [["http:", "attacker.example"], ""],
    [["regions", ".."], ""],
    [["regions", `${id}/secret`], ""],
    [["diagnostics"], ""],
    [["networks", id, "publish"], ""],
    [["regions"], "?limit=101"],
    [["regions"], "?offset=-1"],
    [["regions"], "?limit=10&limit=20"],
    [["regions"], "?token=secret"],
    [["networks", id, "edges"], "?bbox=55,25,57,26"],
    [["networks", id, "edges"], "?bbox=NaN,25,55,26"],
  ] as const) {
    const response = await proxyGeospatial(
      new Request(`http://localhost/api/geospatial/regions${query}`),
      path,
      fetcher,
    );
    assert.ok(
      [404, 422].includes(response.status),
      `${path.join("/")}${query}`,
    );
  }
});

test("proxy preserves missing/invalid resources and hides internal error payloads", async () => {
  for (const status of [404, 422, 429, 500, 503]) {
    const response = await proxyGeospatial(
      new Request(`http://localhost/api/geospatial/regions/${id}`),
      ["regions", id],
      async () =>
        Response.json({ password: "private connection detail" }, { status }),
    );
    assert.equal(response.status, status === 500 ? 503 : status);
    assert.equal(
      JSON.stringify(await response.json()).includes("private"),
      false,
    );
  }
  const malformed = await proxyGeospatial(
    new Request("http://localhost/api/geospatial/regions"),
    ["regions"],
    async () => Response.json({ items: [], total: 0, limit: 1000, offset: 0 }),
  );
  assert.equal(malformed.status, 503);
  const unavailable = await proxyGeospatial(
    new Request("http://localhost/api/geospatial/regions"),
    ["regions"],
    async () => {
      throw new Error("private host");
    },
  );
  assert.equal(unavailable.status, 503);
  assert.equal(
    JSON.stringify(await unavailable.json()).includes("private"),
    false,
  );
});

test("proxy rejects a valid but mismatched resource identity", async () => {
  const response = await proxyGeospatial(
    new Request(`http://localhost/api/geospatial/regions/${id}`),
    ["regions", id],
    async () =>
      Response.json({ ...region, id: "22222222-2222-4222-8222-222222222222" }),
  );
  assert.equal(response.status, 503);
});

test("uncomputed topology counts stay unknown when validation budget is exceeded", () => {
  const report = NetworkValidationSchema.parse({
    network_id: id,
    validated: false,
    status: "NOT_VALIDATED",
    checks: {},
    warnings: ["Configured validation budget exceeded"],
    errors: [],
    counts: { nodes: 6, edges: 8, components: null, isolated_nodes: null },
    boundary_tolerance_m: 5,
    semantics: "Topology was not computed within the configured budget",
  });
  assert.equal(report.validated, false);
  assert.equal(report.counts.components, null);
  assert.equal(report.counts.isolated_nodes, null);
});
