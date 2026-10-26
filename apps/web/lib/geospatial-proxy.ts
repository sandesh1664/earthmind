import { z } from "zod";
import {
  DataSourceListSchema,
  DataSourceSchema,
  NetworkListSchema,
  NetworkSchema,
  NetworkValidationSchema,
  RegionFeatureSchema,
  RegionListSchema,
  RegionSchema,
  SpatialCollectionSchema,
} from "./geospatial";

const uuid = z.uuid();
const pagination = z.coerce.number().int().nonnegative().max(1_000_000);
function error(status: number, message: string): Response {
  return Response.json(
    { error: message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function proxyGeospatial(
  request: Request,
  path: readonly string[],
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  const [resource, identifier, operation] = path;
  let schema: z.ZodType;
  const allowed = new Set<string>();
  if (path.length === 1) {
    allowed.add("limit");
    allowed.add("offset");
    if (resource === "regions") schema = RegionListSchema;
    else if (resource === "networks") {
      schema = NetworkListSchema;
      allowed.add("region_id");
    } else if (resource === "data-sources") schema = DataSourceListSchema;
    else return error(404, "Geospatial resource not found");
  } else if (
    (path.length === 2 || path.length === 3) &&
    uuid.safeParse(identifier).success
  ) {
    if (resource === "regions" && path.length === 2) schema = RegionSchema;
    else if (resource === "regions" && operation === "geojson")
      schema = RegionFeatureSchema;
    else if (resource === "networks" && path.length === 2)
      schema = NetworkSchema;
    else if (resource === "networks" && operation === "validation")
      schema = NetworkValidationSchema;
    else if (
      resource === "networks" &&
      ["edges", "intersections"].includes(operation ?? "")
    ) {
      schema = SpatialCollectionSchema;
      allowed.add("limit");
      allowed.add("offset");
      allowed.add("bbox");
    } else if (resource === "data-sources" && path.length === 2)
      schema = DataSourceSchema;
    else return error(404, "Geospatial resource not found");
  } else
    return error(422, "A valid geospatial resource identifier is required");

  const source = new URL(request.url);
  const query = new URLSearchParams();
  for (const [name, value] of source.searchParams) {
    if (!allowed.has(name) || query.has(name))
      return error(422, "Unsupported geospatial query parameter");
    if (name === "region_id" && !uuid.safeParse(value).success)
      return error(422, "A valid region identifier is required");
    if (
      name === "limit" &&
      !z.coerce.number().int().min(1).max(100).safeParse(value).success
    )
      return error(422, "Page size must be between 1 and 100");
    if (name === "offset" && !pagination.safeParse(value).success)
      return error(422, "Pagination offset is invalid");
    if (name === "bbox") {
      const bounds = value.split(",").map(Number);
      const parsed = z
        .tuple([
          z.number().finite().min(-180).max(180),
          z.number().finite().min(-90).max(90),
          z.number().finite().min(-180).max(180),
          z.number().finite().min(-90).max(90),
        ])
        .safeParse(bounds);
      if (
        !parsed.success ||
        parsed.data[0] >= parsed.data[2] ||
        parsed.data[1] >= parsed.data[3] ||
        parsed.data[2] - parsed.data[0] > 1 ||
        parsed.data[3] - parsed.data[1] > 1
      )
        return error(422, "Bounding box is invalid or too large");
    }
    query.set(name, value);
  }
  const origin = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  try {
    const suffix = query.size ? `?${query}` : "";
    const response = await fetcher(
      `${origin.replace(/\/$/, "")}/api/v1/${path.map(encodeURIComponent).join("/")}${suffix}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(8_000),
        cache: "no-store",
      },
    );
    if (!response.ok)
      return error(
        [404, 422, 429, 503].includes(response.status) ? response.status : 503,
        response.status === 404
          ? "Geospatial resource not found"
          : "Geospatial service unavailable",
      );
    const body = schema.safeParse(await response.json());
    if (!body.success)
      return error(503, "Geospatial response could not be validated");
    if (
      identifier !== undefined &&
      operation !== "edges" &&
      operation !== "intersections"
    ) {
      const actual = body.data as { id?: string; network_id?: string };
      if (
        (actual.id ?? actual.network_id)?.toLowerCase() !==
        identifier.toLowerCase()
      ) {
        return error(
          503,
          "Geospatial response does not match the requested resource",
        );
      }
    }
    return Response.json(body.data, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return error(503, "Geospatial service unavailable");
  }
}
