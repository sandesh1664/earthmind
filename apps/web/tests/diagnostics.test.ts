import assert from "node:assert/strict";
import test from "node:test";
import { DiagnosticJobSchema } from "@earthmind/contracts";
import { proxyBackend } from "../lib/backend";
import { POST } from "../app/api/diagnostics/route";
import { GET } from "../app/api/diagnostics/[id]/route";

test("same-origin diagnostics reject malformed JSON, unsupported jobs and extra fields", async () => {
  for (const [body, expected] of [
    ["{broken", 400],
    [JSON.stringify({ kind: "traffic_simulation" }), 422],
    [JSON.stringify({ kind: "diagnostic", command: "untrusted" }), 422],
  ] as const) {
    const response = await POST(
      new Request("http://localhost/api/diagnostics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      }),
    );
    assert.equal(response.status, expected);
  }
});

test("diagnostic submissions reject simple cross-site requests and foreign origins", async () => {
  const body = JSON.stringify({ kind: "sumo_runtime" });
  const simple = await POST(
    new Request("http://localhost/api/diagnostics", { method: "POST", body }),
  );
  assert.equal(simple.status, 415);
  const foreign = await POST(
    new Request("http://localhost/api/diagnostics", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "https://untrusted.example",
      },
      body,
    }),
  );
  assert.equal(foreign.status, 403);
});

test("same-origin diagnostic lookup rejects a non-UUID before fetching upstream", async () => {
  const response = await GET(
    new Request("http://localhost/api/diagnostics/not-a-uuid"),
    { params: Promise.resolve({ id: "not-a-uuid" }) },
  );
  assert.equal(response.status, 422);
});

test("standalone bind address accepts the real loopback Host and same browser Origin", async (context) => {
  const job = {
    job_id: "c7be43cc-5e36-4d7a-a87e-e00ccece2df4",
    kind: "diagnostic",
    status: "queued",
    created_at: "2026-10-26T17:00:00Z",
    updated_at: "2026-10-26T17:00:00Z",
    result: null,
    error: null,
  };
  const fetch = context.mock.method(globalThis, "fetch", async () => Response.json(job, { status: 202 }));
  const response = await POST(new Request("http://0.0.0.0:3000/api/diagnostics", {
    method: "POST",
    headers: { Host: "127.0.0.1:3000", Origin: "http://127.0.0.1:3000", "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "diagnostic" }),
  }));
  assert.equal(response.status, 202);
  assert.deepEqual(await response.json(), job);
  assert.equal(fetch.mock.calls.length, 1);
});

test("standalone origin guard fails closed for foreign origins, malformed Host and DNS rebinding", async () => {
  for (const [host, origin] of [
    ["127.0.0.1:3000", "https://untrusted.example"],
    ["untrusted.example", "http://untrusted.example"],
    ["127.0.0.1:3000@untrusted.example", "http://untrusted.example"],
    ["127.0.0.1:3000/path", "http://127.0.0.1:3000"],
    ["127.0.0.1:0", "http://127.0.0.1:0"],
    ["127.0.0.1:65536", "http://127.0.0.1:65536"],
    ["localhost,untrusted.example", "http://localhost"],
  ]) {
    const response = await POST(new Request("http://0.0.0.0:3000/api/diagnostics", {
      method: "POST",
      headers: { Host: host!, Origin: origin!, "X-Forwarded-Host": "127.0.0.1:3000", "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "diagnostic" }),
    }));
    assert.equal(response.status, 403, `Host ${host} / Origin ${origin}`);
  }
});

test("diagnostic proxy preserves queue-full HTTP429 without forwarding internal upstream details", async () => {
  const response = await proxyBackend(
    "/api/v1/diagnostics",
    DiagnosticJobSchema,
    { method: "POST", body: { kind: "diagnostic" } },
    async (_url, options) => {
      assert.equal(options?.method, "POST");
      assert.equal(options?.body, JSON.stringify({ kind: "diagnostic" }));
      assert.ok(options?.signal instanceof AbortSignal);
      return Response.json(
        { detail: "private queue connection detail" },
        { status: 429 },
      );
    },
  );
  assert.equal(response.status, 429);
  assert.equal((await response.text()).includes("private"), false);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
});

test("diagnostic proxy rejects invalid success payloads and returns a safe unavailable response", async () => {
  const response = await proxyBackend(
    "/api/v1/diagnostics",
    DiagnosticJobSchema,
    {},
    async () => Response.json({ job_id: "invalid" }),
  );
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {
    error: "Platform service unavailable",
  });
});
