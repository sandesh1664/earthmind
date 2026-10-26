import { z } from "zod";

export async function proxyBackend<T extends z.ZodType>(
  path: string,
  schema: T,
  options: { method?: "GET" | "POST"; body?: unknown } = {},
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  const origin = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetcher(`${origin.replace(/\/$/, "")}${path}`, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      ...(options.body === undefined
        ? {}
        : { body: JSON.stringify(options.body) }),
      signal: AbortSignal.timeout(8_000),
      cache: "no-store",
    });
    if (!response.ok) {
      const status = [404, 422, 429, 503].includes(response.status)
        ? response.status
        : 503;
      return Response.json(
        {
          error:
            status === 404
              ? "Diagnostic job not found"
              : status === 429
                ? "Diagnostic queue is full; retry shortly"
                : "Platform service unavailable",
        },
        { status, headers: { "Cache-Control": "no-store" } },
      );
    }
    const body = schema.safeParse(await response.json());
    if (!body.success) throw new Error("Invalid backend contract");
    return Response.json(body.data, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { error: "Platform service unavailable" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
