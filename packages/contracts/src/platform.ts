import { z } from "zod";
import {
  apiHealthSchema,
  diagnosticJobSchema,
  diagnosticRequestSchema,
  sumoRuntimeRecordSchema,
  systemCapabilitiesSchema,
} from "./schema";

/** Resolve the small JSON-schema vocabulary emitted by the M01 Pydantic models. */
type WireType<Schema, Root = Schema> = Schema extends {
  $ref: `#/$defs/${infer Name}`;
}
  ? Root extends { $defs: infer Definitions }
    ? Name extends keyof Definitions
      ? WireType<Definitions[Name], Root>
      : never
    : never
  : Schema extends { const: infer Value }
    ? Value
    : Schema extends { enum: readonly (infer Value)[] }
      ? Value
      : Schema extends { anyOf: readonly (infer Variant)[] }
        ? WireType<Variant, Root>
        : Schema extends { type: "string" }
          ? string
          : Schema extends { type: "boolean" }
            ? boolean
            : Schema extends { type: "integer" | "number" }
              ? number
              : Schema extends { type: "null" }
                ? null
                : Schema extends {
                      type: "object";
                      properties: infer Properties;
                    }
                  ? {
                      [Key in keyof Properties]: WireType<
                        Properties[Key],
                        Root
                      >;
                    }
                  : Schema extends { type: "object" }
                    ? Record<string, unknown>
                    : unknown;

function fromCanonical<Schema extends object>(
  schema: Schema,
): z.ZodType<WireType<Schema>> {
  // Canonical schemas are JSON. Zod's converter enforces formats, enums, references,
  // defaults and additionalProperties, using exactly the backend's generated shape.
  return z.fromJSONSchema(JSON.parse(JSON.stringify(schema))) as z.ZodType<
    WireType<Schema>
  >;
}

export const ApiHealthSchema = fromCanonical(apiHealthSchema);
export const RuntimeSchema = fromCanonical(sumoRuntimeRecordSchema);
export const CapabilitiesSchema = fromCanonical(systemCapabilitiesSchema);
export const DiagnosticRequestSchema = fromCanonical(diagnosticRequestSchema);
export const DiagnosticJobSchema = fromCanonical(diagnosticJobSchema);
export type Capabilities = z.output<typeof CapabilitiesSchema>;
export type DiagnosticJob = z.output<typeof DiagnosticJobSchema>;
export type DiagnosticRequest = z.output<typeof DiagnosticRequestSchema>;
