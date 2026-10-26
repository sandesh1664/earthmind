import { liveHealthSchema, readyHealthSchema } from "./schema";
import { z } from "zod";

export * from "./platform";

/** Types and validation share schema literals checked against the Python contracts. */
export interface LiveHealth {
  status: typeof liveHealthSchema.properties.status.const;
  service: typeof liveHealthSchema.properties.service.const;
}

type Dependencies = typeof readyHealthSchema.$defs.DependencyChecks.properties;

export interface ReadyHealth {
  status: (typeof readyHealthSchema.properties.status.enum)[number];
  service: typeof readyHealthSchema.properties.service.const;
  checks: {
    [Key in keyof Dependencies]: Dependencies[Key]["enum"][number];
  };
}

export type CheckStatus = ReadyHealth["checks"][keyof ReadyHealth["checks"]];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

function matchesEnum(value: unknown, allowed: readonly unknown[]): boolean {
  return allowed.includes(value);
}

export function isReadyHealth(value: unknown): value is ReadyHealth {
  if (!isRecord(value)) return false;
  if (!hasOnlyKeys(value, Object.keys(readyHealthSchema.properties)))
    return false;
  if (value.service !== readyHealthSchema.properties.service.const)
    return false;
  if (!matchesEnum(value.status, readyHealthSchema.properties.status.enum)) {
    return false;
  }
  if (!isRecord(value.checks)) return false;
  const checks = value.checks;
  const dependencies = readyHealthSchema.$defs.DependencyChecks.properties;
  if (!hasOnlyKeys(checks, Object.keys(dependencies))) return false;
  return Object.entries(dependencies).every(([name, schema]) =>
    matchesEnum(checks[name], schema.enum),
  );
}

export type HealthResponse = ReadyHealth;

export const ReadyHealthSchema = z.custom<ReadyHealth>(
  isReadyHealth,
  "Invalid readiness response",
);
