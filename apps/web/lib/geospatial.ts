import { z } from "zod";

const UUID = z.uuid();
const finite = z.number().finite();
export const PositionSchema = z.tuple([
  finite.min(-180).max(180),
  finite.min(-90).max(90),
]);
export const BoundsSchema = z
  .tuple([
    finite.min(-180).max(180),
    finite.min(-90).max(90),
    finite.min(-180).max(180),
    finite.min(-90).max(90),
  ])
  .refine(([west, south, east, north]) => west <= east && south <= north);
const Timestamp = z.iso.datetime({ offset: true });
const Checksum = z.string().regex(/^[a-fA-F0-9]{64}$/);
const RingSchema = z
  .array(PositionSchema)
  .min(4)
  .max(5_000)
  .refine((ring) => {
    const first = ring[0],
      last = ring.at(-1);
    return (
      first !== undefined &&
      last !== undefined &&
      first[0] === last[0] &&
      first[1] === last[1]
    );
  });
const MultiPolygonSchema = z
  .object({
    type: z.literal("MultiPolygon"),
    coordinates: z.array(z.array(RingSchema).min(1).max(128)).min(1).max(128),
  })
  .strip()
  .refine((geometry) => {
    const coordinates = geometry.coordinates.flat(2);
    return (
      coordinates.length <= 5_000 &&
      Math.min(...coordinates.map(([x]) => x)) <
        Math.max(...coordinates.map(([x]) => x)) &&
      Math.min(...coordinates.map(([, y]) => y)) <
        Math.max(...coordinates.map(([, y]) => y))
    );
  });

export const PublicFeatureMetadataSchema = z.object({
  osm_way_id: z.string().max(256).nullable().optional(),
  osm_node_id: z.string().max(256).nullable().optional(),
  osm_lanes: z.string().max(256).nullable().optional(),
  osm_directional_lanes: z.string().max(256).nullable().optional(),
  osm_maxspeed: z.string().max(256).nullable().optional(),
  lane_count_source: z.string().max(256).nullable().optional(),
  speed_limit_source: z.string().max(256).nullable().optional(),
  turn_restrictions_status: z.string().max(256).nullable().optional(),
  geometry_derivation: z.string().max(256).nullable().optional(),
  signal_status: z.string().max(256).nullable().optional(),
  node_origin: z.string().max(256).nullable().optional(),
  osm_way_ids: z.array(z.string().max(128)).max(64).optional(),
  sumo_identifier_verified:z.boolean().optional(),
}).strip();

export const PublicRegionMetadataSchema = z
  .object({
    is_synthetic: z.boolean().optional(),
    boundary_policy: z.string().max(2_000).optional(),
    description: z.string().max(2_000).optional(),
    source: z.string().max(2_000).optional(),
    fixture_version: z.string().max(128).optional(),
  })
  .strip();

export const RegionSchema = z
  .object({
    id: UUID,
    slug: z.string().min(1).max(120),
    name: z.string().min(1).max(255),
    country_code: z.string().length(2),
    emirate: z.string().max(128).nullable(),
    timezone: z.string().min(1).max(128),
    area_km2: finite.nonnegative(),
    centroid: PositionSchema,
    bounds: BoundsSchema,
    metadata: PublicRegionMetadataSchema,
    created_at: Timestamp,
    updated_at: Timestamp,
  })
  .strip();

export const ValidationStatusSchema = z.enum([
  "VALID",
  "VALID_WITH_WARNINGS",
  "INVALID",
  "NOT_VALIDATED",
]);
export const NetworkSchema = z
  .object({
    id: UUID,
    region_id: UUID,
    data_source_id: UUID.nullable(),
    version_label: z.string().min(1).max(128),
    status: z.string().min(1).max(32),
    checksum_sha256: Checksum,
    source_format: z.string().min(1).max(128),
    projection_srid: z.number().int().positive(),
    node_count: z.number().int().nonnegative(),
    edge_count: z.number().int().nonnegative(),
    is_validated: z.boolean(),
    validation_summary: z
      .object({
        status: ValidationStatusSchema.optional(),
        warnings: z.array(z.string().max(2_000)).max(100).optional(),
        errors: z.array(z.string().max(2_000)).max(100).optional(),
      })
      .strip(),
    bounds: BoundsSchema.nullable(),
    created_at: Timestamp,
    is_synthetic: z.boolean(),
  })
  .strip();

export const NetworkValidationSchema = z
  .object({
    network_id: UUID,
    validated: z.boolean(),
    status: ValidationStatusSchema,
    checks: z.record(z.string().max(128), z.boolean()),
    warnings: z.array(z.string().max(2_000)).max(100),
    errors: z.array(z.string().max(2_000)).max(100),
    counts: z
      .object({
        nodes: z.number().int().nonnegative(),
        edges: z.number().int().nonnegative(),
        components: z.number().int().nonnegative().nullable(),
        isolated_nodes: z.number().int().nonnegative().nullable(),
      })
      .strip(),
    boundary_tolerance_m: finite.nonnegative().max(1_000),
    semantics: z.string().max(4_000),
  })
  .strip()
  .refine(
    (value) =>
      value.validated ===
      ["VALID", "VALID_WITH_WARNINGS"].includes(value.status),
  );

export const DataSourceSchema = z
  .object({
    id: UUID,
    provider_name: z.string().min(1).max(255),
    dataset_name: z.string().min(1).max(255),
    source_type: z.string().min(1).max(128),
    source_url: z
      .url()
      .refine((value) => {
        const url = new URL(value);
        const host = url.hostname.toLowerCase();
        return (
          url.protocol === "https:" &&
          !url.username &&
          !url.password &&
          !url.hash &&
          host.includes(".") &&
          !host.endsWith(".local") &&
          !host.endsWith(".localhost") &&
          !host.includes(":") &&
          !/^\d+(\.\d+){3}$/.test(host) &&
          !Array.from(url.searchParams.keys()).some((key) =>
            /password|secret|token|credential|authorization|signature|api.?key/i.test(
              key,
            ),
          )
        );
      })
      .nullable(),
    license_identifier: z.string().max(255).nullable(),
    attribution_text: z.string().max(4_000),
    collected_at: Timestamp,
    source_version: z.string().max(255),
    checksum_sha256: Checksum,
    created_at: Timestamp,
    is_synthetic: z.boolean(),
  })
  .strip();

export const RegionFeatureSchema = z
  .object({
    type: z.literal("Feature"),
    id: UUID,
    geometry: MultiPolygonSchema,
    properties: z
      .object({
        id: UUID,
        slug: z.string().max(120),
        name: z.string().max(255),
        is_synthetic: z.boolean(),
        area_km2: finite.nonnegative(),
        country_code: z.string().length(2),
        boundary_policy: z.string().max(2_000),
      })
      .strip(),
  })
  .strip();

const Pagination = {
  total: z.number().int().nonnegative(),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().nonnegative(),
};
export const RegionListSchema = z
  .object({ items: z.array(RegionSchema).max(100), ...Pagination })
  .strip();
export const NetworkListSchema = z
  .object({ items: z.array(NetworkSchema).max(100), ...Pagination })
  .strip();
export const DataSourceListSchema = z
  .object({ items: z.array(DataSourceSchema).max(100), ...Pagination })
  .strip();
const SpatialFeatureSchema = z
  .object({
    type: z.literal("Feature"),
    id: z.string().max(128),
    geometry: z.union([
      z
        .object({ type: z.literal("Point"), coordinates: PositionSchema })
        .strip(),
      z
        .object({
          type: z.literal("LineString"),
          coordinates: z.array(PositionSchema).min(2).max(5_000),
        })
        .strip(),
    ]),
    properties: z
      .object({
        network_version_id: UUID.optional(),
        name: z.string().max(255).nullable().optional(),
        source_edge_id: z.string().max(255).nullable().optional(),
        metadata: PublicFeatureMetadataSchema.optional(),
    start_intersection_id: UUID.optional(),
        end_intersection_id: UUID.optional(),
        road_class: z.string().max(128).optional(),
        lane_count: z.number().int().positive().optional(),
        speed_limit_mps: finite.positive().nullable().optional(),
        length_m: finite.nonnegative().optional(),
        is_one_way: z.boolean().optional(),
        is_synthetic: z.boolean().optional(),
    source_node_id: z.string().max(255).nullable().optional(),
        sumo_node_id: z.string().max(255).nullable().optional(),
        sumo_edge_id: z.string().max(255).optional(),
        intersection_type: z.string().max(128).optional(),
        is_signalized: z.boolean().optional(),
      })
      .strip(),
  })
  .strip();
export const SpatialCollectionSchema = z
  .object({
    type: z.literal("FeatureCollection"),
    features: z.array(SpatialFeatureSchema).max(100),
    ...Pagination,
  })
  .strip();

export type Region = z.output<typeof RegionSchema>;
export type Network = z.output<typeof NetworkSchema>;
export type RegionFeature = z.output<typeof RegionFeatureSchema>;
export type ValidationStatus = z.output<typeof ValidationStatusSchema>;

/** Unitless coordinate preview; never used as a metric distance calculation. */
export function boundaryPaths(feature: RegionFeature): string[] {
  const coordinates = feature.geometry.coordinates.flat(2);
  const longitudes = coordinates.map(([longitude]) => longitude);
  const latitudes = coordinates.map(([, latitude]) => latitude);
  const west = Math.min(...longitudes),
    east = Math.max(...longitudes);
  const south = Math.min(...latitudes),
    north = Math.max(...latitudes);
  const dx = east - west,
    dy = north - south;
  if (dx <= 0 || dy <= 0) throw new Error("Boundary has no geographic extent");
  const scale = Math.min(570 / dx, 270 / dy);
  const offsetX = (640 - dx * scale) / 2,
    offsetY = (330 - dy * scale) / 2;
  return feature.geometry.coordinates.map((polygon) =>
    polygon
      .map(
        (ring) =>
          ring
            .map(
              ([longitude, latitude], index) =>
                `${index === 0 ? "M" : "L"}${(offsetX + (longitude - west) * scale).toFixed(2)},${(offsetY + (north - latitude) * scale).toFixed(2)}`,
            )
            .join(" ") + " Z",
      )
      .join(" "),
  );
}
