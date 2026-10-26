import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { getBackendHealth } from "../lib/health";
import { isReadyHealth } from "@earthmind/contracts";
import {
  ApiHealthSchema,
  CapabilitiesSchema,
  DiagnosticJobSchema,
  DiagnosticRequestSchema,
} from "@earthmind/contracts";
import {
  liveHealthSchema,
  readyHealthSchema,
  apiHealthSchema,
  sumoRuntimeRecordSchema,
  systemCapabilitiesSchema,
  diagnosticRequestSchema,
  diagnosticJobSchema,
} from "../../../packages/contracts/src/schema";

const healthy = {
  status: "ok",
  service: "api",
  checks: { database: "ok", redis: "ok", worker: "ok" },
};

test("proxy reaches the configured API origin and forwards a healthy contract", async () => {
  const fetcher: typeof fetch = async (url, options) => {
    assert.equal(url, "http://api:8000/api/v1/ready");
    assert.equal(options?.cache, "no-store");
    assert.ok(options?.signal instanceof AbortSignal);
    return Response.json(healthy);
  };
  assert.deepEqual(await getBackendHealth("http://api:8000/", fetcher), {
    status: 200,
    body: healthy,
    reachable: true,
  });
});

test("degraded dependencies preserve the readiness failure", async () => {
  const degraded = {
    ...healthy,
    status: "degraded",
    checks: { ...healthy.checks, worker: "error" },
  };
  const result = await getBackendHealth("http://api:8000", async () =>
    Response.json(degraded, { status: 503 }),
  );
  assert.equal(result.status, 503);
  assert.deepEqual(result.body, degraded);
  assert.equal(result.reachable, true);
});

test("invalid upstream JSON never reports healthy", async () => {
  const result = await getBackendHealth("http://api:8000", async () =>
    Response.json({ status: "ok" }),
  );
  assert.equal(result.status, 503);
  assert.equal(result.body.status, "degraded");
  assert.equal(result.reachable, false);
});

test("network failure returns a bounded degraded response without internal error details", async () => {
  const result = await getBackendHealth("http://api:8000", async () => {
    throw new Error("private connection details");
  });
  assert.equal(result.status, 503);
  assert.equal(result.body.status, "degraded");
  assert.equal(JSON.stringify(result).includes("private"), false);
  assert.equal(result.reachable, false);
});

test("HTTP failure cannot return a healthy body to the dashboard", async () => {
  const result = await getBackendHealth("http://api:8000", async () =>
    Response.json(healthy, { status: 503 }),
  );
  assert.equal(result.status, 503);
  assert.equal(result.body.status, "degraded");
});

test("an inconsistent healthy status with an error check is normalized to degraded", async () => {
  const inconsistent = {
    ...healthy,
    checks: { ...healthy.checks, database: "error" },
  };
  const result = await getBackendHealth("http://api:8000", async () =>
    Response.json(inconsistent),
  );
  assert.equal(result.status, 503);
  assert.equal(result.body.status, "degraded");
});

test("contract validator rejects enum values that only coerce to valid strings", () => {
  assert.equal(isReadyHealth({ ...healthy, status: ["ok"] }), false);
  assert.equal(
    isReadyHealth({
      ...healthy,
      checks: { ...healthy.checks, database: ["ok"] },
    }),
    false,
  );
  assert.equal(
    isReadyHealth({ ...healthy, status: { toString: () => "ok" } }),
    false,
  );
});

test("TypeScript schema literals match the canonical Python JSON schemas", async () => {
  for (const [name, actual] of [
    ["LiveHealth", liveHealthSchema],
    ["ReadyHealth", readyHealthSchema],
    ["ApiHealth", apiHealthSchema],
    ["SumoRuntimeRecord", sumoRuntimeRecordSchema],
    ["SystemCapabilities", systemCapabilitiesSchema],
    ["DiagnosticRequest", diagnosticRequestSchema],
    ["DiagnosticJob", diagnosticJobSchema],
  ] as const) {
    const path = new URL(
      `../../../packages/contracts/schema/${name}.json`,
      import.meta.url,
    );
    assert.deepEqual(actual, JSON.parse(await readFile(path, "utf8")));
  }
});

test("versioned liveness and capabilities use the canonical Zod API boundary", () => {
  assert.equal(
    ApiHealthSchema.safeParse({
      service: "EARTHMIND API",
      status: "healthy",
      version: "0.1.0",
    }).success,
    true,
  );
  const capabilities = {
    application: "EARTHMIND",
    version: "0.1.0",
    milestone: "M01",
    capabilities: {
      api: true,
      database: true,
      redis: true,
      worker: true,
      simulation_runtime: false,
      dubai_network_import: false,
      traffic_simulation: false,
      ai_forecasting: false,
    },
    runtime: null,
  };
  assert.equal(CapabilitiesSchema.safeParse(capabilities).success, true);
  assert.equal(
    CapabilitiesSchema.safeParse({
      ...capabilities,
      private_connection: "secret",
    }).success,
    false,
  );
  assert.equal(
    CapabilitiesSchema.safeParse({
      ...capabilities,
      capabilities: { ...capabilities.capabilities, traffic_simulation: true },
    }).success,
    false,
  );
  assert.equal(
    CapabilitiesSchema.safeParse({
      ...capabilities,
      capabilities: { ...capabilities.capabilities, api: false },
    }).success,
    false,
  );
});

test("diagnostic requests reject future simulation kinds and unknown fields", () => {
  assert.equal(
    DiagnosticRequestSchema.safeParse({ kind: "diagnostic" }).success,
    true,
  );
  assert.equal(
    DiagnosticRequestSchema.safeParse({ kind: "sumo_runtime" }).success,
    true,
  );
  assert.equal(
    DiagnosticRequestSchema.safeParse({ kind: "traffic_simulation" }).success,
    false,
  );
  assert.equal(
    DiagnosticRequestSchema.safeParse({
      kind: "diagnostic",
      command: "anything",
    }).success,
    false,
  );
});

test("diagnostic jobs validate UUID, lifecycle and JSON results from the canonical model", () => {
  const job = {
    job_id: "c7be43cc-5e36-4d7a-a87e-e00ccece2df4",
    kind: "diagnostic",
    status: "succeeded",
    created_at: "2026-10-26T17:00:00Z",
    updated_at: "2026-10-26T17:00:01Z",
    result: { verified: true },
    error: null,
  };
  assert.equal(DiagnosticJobSchema.safeParse(job).success, true);
  assert.equal(
    DiagnosticJobSchema.safeParse({ ...job, job_id: "not-a-uuid" }).success,
    false,
  );
  assert.equal(
    DiagnosticJobSchema.safeParse({ ...job, status: "completed" }).success,
    false,
  );
  assert.equal(
    DiagnosticJobSchema.safeParse({ ...job, error: "x".repeat(513) }).success,
    false,
  );
});

test("unexpected upstream fields are rejected instead of forwarded across the proxy", async () => {
  for (const extra of [
    { ...healthy, private_connection_detail: "must not leave upstream" },
    {
      ...healthy,
      checks: {
        ...healthy.checks,
        private_connection_detail: "must not leave upstream",
      },
    },
  ]) {
    assert.equal(isReadyHealth(extra), false);
    const result = await getBackendHealth("http://api:8000", async () =>
      Response.json(extra),
    );
    assert.equal(result.status, 503);
    assert.equal(
      JSON.stringify(result.body).includes("private_connection_detail"),
      false,
    );
  }
});
