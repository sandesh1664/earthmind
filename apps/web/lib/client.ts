import { z } from "zod";

export async function requestJSON<T extends z.ZodType>(
  url: string,
  schema: T,
  options?: RequestInit,
): Promise<z.output<T>> {
  const response = await fetch(url, {
    ...options,
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    if (response.status === 429)
      throw new Error("Diagnostic queue is full. Retry shortly.");
    throw new Error(`Platform request unavailable (HTTP ${response.status})`);
  }
  return schema.parse(await response.json());
}
