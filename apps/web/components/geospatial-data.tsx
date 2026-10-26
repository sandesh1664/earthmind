"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Database,
  GitBranch,
  Layers3,
  MapPin,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { requestJSON } from "@/lib/client";
import {
  boundaryPaths,
  DataSourceSchema,
  NetworkListSchema,
  NetworkSchema,
  NetworkValidationSchema,
  RegionFeatureSchema,
  RegionListSchema,
  RegionSchema,
  type RegionFeature,
  type ValidationStatus,
} from "@/lib/geospatial";

const root = "/api/geospatial";
function QueryError({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div className="geo-error" role="alert">
      <AlertTriangle size={17} />
      <p>{message}</p>
      <button onClick={retry}>
        <RefreshCw size={13} /> Retry
      </button>
    </div>
  );
}
function Loading({ label }: { label: string }) {
  return (
    <div className="geo-loading" role="status" aria-label={label}>
      <span className="skeleton-line animate-pulse" />
      <span className="skeleton-line animate-pulse" />
      <span>{label}</span>
    </div>
  );
}
function ValidationBadge({ status }: { status: ValidationStatus }) {
  return (
    <span className={`geo-validation ${status.toLowerCase()}`}>
      <span />
      {status.replaceAll("_", " ")}
    </span>
  );
}
function Pagination({
  label,
  total,
  limit,
  offset,
  change,
}: {
  label: string;
  total: number;
  limit: number;
  offset: number;
  change: (offset: number) => void;
}) {
  if (total <= limit && offset === 0) return null;
  return (
    <div className="geo-pagination">
      <span>
        Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div>
        <button
          aria-label={`Previous ${label}`}
          disabled={offset === 0}
          onClick={() => change(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <button
          aria-label={`Next ${label}`}
          disabled={offset + limit >= total}
          onClick={() => change(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
function BoundaryPreview({ feature }: { feature: RegionFeature }) {
  const paths = boundaryPaths(feature);
  return (
    <figure className="geo-boundary">
      <div className="geo-map-heading">
        <span>
          <MapPin size={13} /> Boundary coordinate preview
        </span>
        <span>EPSG:4326</span>
      </div>
      <svg
        viewBox="0 0 640 360"
        role="img"
        aria-label="Illustrative study region boundary in longitude and latitude"
      >
        <defs>
          <pattern
            id="geo-grid"
            width="32"
            height="32"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="#274258"
              strokeWidth=".6"
            />
          </pattern>
          <linearGradient id="geo-fill" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#2b86a3" stopOpacity=".35" />
            <stop offset="1" stopColor="#1c566d" stopOpacity=".12" />
          </linearGradient>
        </defs>
        <rect width="640" height="330" fill="url(#geo-grid)" />
        {paths.map((path, index) => (
          <path
            key={index}
            d={path}
            fill="url(#geo-fill)"
            fillRule="evenodd"
            stroke="#70d5ea"
            strokeWidth="2"
          />
        ))}
        <text
          x="18"
          y="350"
          fill="#84a5bd"
          fontSize="10"
          fontFamily="monospace"
        >
          [longitude, latitude] · coordinate preview only
        </text>
      </svg>
      <figcaption>
        {feature.properties.is_synthetic
          ? "Illustrative project-generated boundary. This is not an official municipal boundary or a live map."
          : "Registered boundary coordinate preview. Review the recorded source and boundary policy; official status is not inferred."}
      </figcaption>
    </figure>
  );
}

export function GeospatialData() {
  const [chosenRegion, setChosenRegion] = useState<string | null>(null);
  const [chosenNetwork, setChosenNetwork] = useState<string | null>(null);
  const [regionOffset, setRegionOffset] = useState(0);
  const [networkOffset, setNetworkOffset] = useState(0);
  const regions = useQuery({
    queryKey: ["geospatial", "regions", regionOffset],
    queryFn: () =>
      requestJSON(
        `${root}/regions?limit=100&offset=${regionOffset}`,
        RegionListSchema,
      ),
    staleTime: 30_000,
  });
  const regionId = regions.data?.items.some(
    (region) => region.id === chosenRegion,
  )
    ? chosenRegion
    : regions.data?.items[0]?.id;
  const region = useQuery({
    queryKey: ["geospatial", "region", regionId],
    queryFn: () => requestJSON(`${root}/regions/${regionId}`, RegionSchema),
    enabled: Boolean(regionId),
  });
  const boundary = useQuery({
    queryKey: ["geospatial", "boundary", regionId],
    queryFn: () =>
      requestJSON(`${root}/regions/${regionId}/geojson`, RegionFeatureSchema),
    enabled: Boolean(regionId),
  });
  const networks = useQuery({
    queryKey: ["geospatial", "networks", regionId, networkOffset],
    queryFn: () =>
      requestJSON(
        `${root}/networks?region_id=${regionId}&limit=100&offset=${networkOffset}`,
        NetworkListSchema,
      ),
    enabled: Boolean(regionId),
  });
  const networkId = networks.data?.items.some(
    (network) => network.id === chosenNetwork,
  )
    ? chosenNetwork
    : networks.data?.items[0]?.id;
  const network = useQuery({
    queryKey: ["geospatial", "network", networkId],
    queryFn: () => requestJSON(`${root}/networks/${networkId}`, NetworkSchema),
    enabled: Boolean(networkId),
  });
  const validation = useQuery({
    queryKey: ["geospatial", "validation", networkId],
    queryFn: () =>
      requestJSON(
        `${root}/networks/${networkId}/validation`,
        NetworkValidationSchema,
      ),
    enabled: Boolean(networkId),
  });
  const sourceId = network.data?.data_source_id;
  const source = useQuery({
    queryKey: ["geospatial", "source", sourceId],
    queryFn: () =>
      requestJSON(`${root}/data-sources/${sourceId}`, DataSourceSchema),
    enabled: Boolean(sourceId),
  });
  const active = region.data;

  return (
    <div className="geospatial-workspace">
      <section className="geo-intro panel" aria-labelledby="geospatial-title">
        <div>
          <p className="section-kicker">M02 · GEOSPATIAL PERSISTENCE</p>
          <h2 id="geospatial-title">Geospatial data management</h2>
          <p className="panel-description">
            Inspect stored study regions, immutable network versions and dataset
            provenance. Geometry and validation are read from the spatial API.
          </p>
        </div>
        <span className="geo-module-tag">
          <Layers3 size={14} /> M02
        </span>
      </section>
      {regions.isPending ? (
        <Loading label="Loading study regions" />
      ) : regions.isError ? (
        <QueryError
          message="Study regions are unavailable. Check the spatial service and retry."
          retry={() => {
            void regions.refetch();
          }}
        />
      ) : regions.data.items.length === 0 ? (
        <section className="panel geo-empty">
          <Database size={27} />
          <h3>No study regions registered</h3>
          <p>
            Registered geospatial datasets will appear here. No boundary or
            network data is being inferred.
          </p>
        </section>
      ) : (
        <>
          <section className="geo-selector-bar" aria-label="Dataset selection">
            <div>
              <label htmlFor="study-region">Study region</label>
              <select
                id="study-region"
                value={regionId ?? ""}
                onChange={(event) => {
                  setChosenRegion(event.target.value);
                  setChosenNetwork(null);
                  setNetworkOffset(0);
                }}
              >
                {regions.data.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <span>
              {regions.data.total} registered{" "}
              {regions.data.total === 1 ? "region" : "regions"}
            </span>
          </section>
          <Pagination
            label="regions"
            total={regions.data.total}
            limit={regions.data.limit}
            offset={regions.data.offset}
            change={(offset) => {
              setRegionOffset(offset);
              setChosenRegion(null);
              setChosenNetwork(null);
              setNetworkOffset(0);
            }}
          />
          {region.isPending ? (
            <Loading label="Loading selected region" />
          ) : region.isError ? (
            <QueryError
              message="Selected region metadata is unavailable."
              retry={() => {
                void region.refetch();
              }}
            />
          ) : (
            active && (
              <>
                {active.metadata.is_synthetic && (
                  <div className="geo-synthetic-notice" role="note">
                    <ShieldCheck size={19} />
                    <div>
                      <strong>Synthetic study data</strong>
                      <p>
                        This region is labeled project-generated synthetic
                        geometry. Its illustrative boundary does not represent
                        an official administrative boundary, surveyed streets or
                        observed traffic.
                      </p>
                    </div>
                  </div>
                )}
                <div className="geo-region-grid">
                  <section
                    className="panel geo-metadata"
                    aria-labelledby="region-metadata-title"
                  >
                    <div className="panel-heading">
                      <div>
                        <p className="section-kicker">STUDY REGION</p>
                        <h3 id="region-metadata-title">{active.name}</h3>
                      </div>
                      <MapPin size={19} className="muted-icon" />
                    </div>
                    <p className="geo-slug">{active.slug}</p>
                    <dl className="geo-definition-grid">
                      <div>
                        <dt>Geographic area</dt>
                        <dd data-testid="region-area">
                          {active.area_km2.toLocaleString(undefined, {
                            maximumFractionDigits: 4,
                          })}{" "}
                          km²
                        </dd>
                        <span>Geodesic measurement</span>
                      </div>
                      <div>
                        <dt>Coordinate system</dt>
                        <dd>EPSG:4326</dd>
                        <span>Longitude, latitude</span>
                      </div>
                      <div>
                        <dt>Country / emirate</dt>
                        <dd>
                          {active.country_code} /{" "}
                          {active.emirate ?? "Not provided"}
                        </dd>
                      </div>
                      <div>
                        <dt>Time zone</dt>
                        <dd>{active.timezone}</dd>
                      </div>
                      <div className="geo-full">
                        <dt>Centroid [longitude, latitude]</dt>
                        <dd className="geo-mono">
                          {active.centroid
                            .map((value) => value.toFixed(6))
                            .join(", ")}
                        </dd>
                      </div>
                      <div className="geo-full">
                        <dt>Bounds [west, south, east, north]</dt>
                        <dd className="geo-mono" data-testid="region-bounds">
                          {active.bounds
                            .map((value) => value.toFixed(6))
                            .join(", ")}
                        </dd>
                      </div>
                    </dl>
                    <p className="geo-policy">
                      {active.metadata.boundary_policy ??
                        "Boundary policy not provided."}
                    </p>
                  </section>
                  <section
                    className="panel geo-preview-panel"
                    aria-label="Region geometry"
                  >
                    {boundary.isPending ? (
                      <Loading label="Loading boundary preview" />
                    ) : boundary.isError ? (
                      <QueryError
                        message="Region GeoJSON could not be loaded or validated."
                        retry={() => {
                          void boundary.refetch();
                        }}
                      />
                    ) : (
                      boundary.data && (
                        <BoundaryPreview feature={boundary.data} />
                      )
                    )}
                  </section>
                </div>
                <section
                  className="panel geo-networks"
                  aria-labelledby="network-title"
                >
                  <div className="panel-heading">
                    <div>
                      <p className="section-kicker">VERSIONED DATA</p>
                      <h3 id="network-title">Stored network versions</h3>
                    </div>
                    <GitBranch size={19} className="muted-icon" />
                  </div>
                  {networks.isPending ? (
                    <Loading label="Loading network versions" />
                  ) : networks.isError ? (
                    <QueryError
                      message="Network versions are unavailable."
                      retry={() => {
                        void networks.refetch();
                      }}
                    />
                  ) : networks.data.items.length === 0 ? (
                    <p className="geo-empty-copy">
                      No stored networks are associated with this region.
                    </p>
                  ) : (
                    <>
                      <div className="geo-table-scroll">
                        <table>
                          <caption className="sr-only">
                            Network versions associated with selected study
                            region
                          </caption>
                          <thead>
                            <tr>
                              <th scope="col">Version</th>
                              <th scope="col">Lifecycle</th>
                              <th scope="col">Intersections</th>
                              <th scope="col">Road edges</th>
                              <th scope="col">Dataset</th>
                            </tr>
                          </thead>
                          <tbody>
                            {networks.data.items.map((item) => (
                              <tr
                                key={item.id}
                                className={
                                  item.id === networkId ? "is-selected" : ""
                                }
                              >
                                <td>
                                  <button
                                    onClick={() => setChosenNetwork(item.id)}
                                    aria-pressed={item.id === networkId}
                                  >
                                    {item.version_label}
                                  </button>
                                </td>
                                <td>
                                  <span className="geo-lifecycle">
                                    {item.status}
                                  </span>
                                </td>
                                <td>{item.node_count}</td>
                                <td>{item.edge_count}</td>
                                <td>
                                  {item.is_synthetic ? (
                                    <span className="geo-synthetic-chip">
                                      SYNTHETIC
                                    </span>
                                  ) : (
                                    "Registered source"
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <Pagination
                        label="network versions"
                        total={networks.data.total}
                        limit={networks.data.limit}
                        offset={networks.data.offset}
                        change={(offset) => {
                          setNetworkOffset(offset);
                          setChosenNetwork(null);
                        }}
                      />
                    </>
                  )}
                </section>
                {networkId && (
                  <>
                    <div className="geo-details-grid">
                      <section
                        className="panel geo-network-detail"
                        aria-labelledby="selected-network-title"
                      >
                        <div className="panel-heading">
                          <div>
                            <p className="section-kicker">SELECTED VERSION</p>
                            <h3 id="selected-network-title">
                              Network identity
                            </h3>
                          </div>
                          <Layers3 size={19} className="muted-icon" />
                        </div>
                        {network.isPending ? (
                          <Loading label="Loading network metadata" />
                        ) : network.isError ? (
                          <QueryError
                            message="Selected network metadata is unavailable."
                            retry={() => {
                              void network.refetch();
                            }}
                          />
                        ) : (
                          network.data && (
                            <>
                              <dl className="geo-definition-grid">
                                <div>
                                  <dt>Version label</dt>
                                  <dd>{network.data.version_label}</dd>
                                </div>
                                <div>
                                  <dt>Lifecycle</dt>
                                  <dd>{network.data.status}</dd>
                                </div>
                                <div>
                                  <dt>Intersections</dt>
                                  <dd data-testid="network-node-count">
                                    {network.data.node_count}
                                  </dd>
                                </div>
                                <div>
                                  <dt>Road edges</dt>
                                  <dd data-testid="network-edge-count">
                                    {network.data.edge_count}
                                  </dd>
                                </div>
                                <div>
                                  <dt>Source format</dt>
                                  <dd>{network.data.source_format}</dd>
                                </div>
                                <div>
                                  <dt>Projection metadata</dt>
                                  <dd>EPSG:{network.data.projection_srid}</dd>
                                </div>
                                <div className="geo-full">
                                  <dt>Network UUID</dt>
                                  <dd className="geo-mono">
                                    {network.data.id}
                                  </dd>
                                </div>
                                <div className="geo-full">
                                  <dt>Content checksum · SHA-256</dt>
                                  <dd className="geo-mono">
                                    {network.data.checksum_sha256}
                                  </dd>
                                </div>
                                <div className="geo-full">
                                  <dt>Geometry bounds</dt>
                                  <dd className="geo-mono">
                                    {network.data.bounds
                                      ?.map((value) => value.toFixed(6))
                                      .join(", ") ?? "No geometry bounds"}
                                  </dd>
                                </div>
                              </dl>
                              {network.data.is_synthetic && (
                                <p className="capability-note">
                                  Provisional fixture identifiers are synthetic
                                  compatibility IDs, not verified SUMO network
                                  identifiers.
                                </p>
                              )}
                            </>
                          )
                        )}
                      </section>
                      <section
                        className="panel geo-validation-panel"
                        aria-labelledby="validation-title"
                      >
                        <div className="panel-heading">
                          <div>
                            <p className="section-kicker">
                              STRUCTURAL INTEGRITY
                            </p>
                            <h3 id="validation-title">Network validation</h3>
                          </div>
                          <CheckCircle2 size={19} className="muted-icon" />
                        </div>
                        {validation.isPending ? (
                          <Loading label="Loading validation report" />
                        ) : validation.isError ? (
                          <QueryError
                            message="A current validation report could not be loaded. Validation success is not assumed."
                            retry={() => {
                              void validation.refetch();
                            }}
                          />
                        ) : (
                          validation.data && (
                            <>
                              <ValidationBadge
                                status={validation.data.status}
                              />
                              <p className="geo-validation-semantics">
                                {validation.data.semantics}
                              </p>
                              <dl className="geo-validation-counts">
                                <div>
                                  <dt>Components</dt>
                                  <dd>
                                    {validation.data.counts.components ??
                                      "Not computed"}
                                  </dd>
                                </div>
                                <div>
                                  <dt>Isolated nodes</dt>
                                  <dd>
                                    {validation.data.counts.isolated_nodes ??
                                      "Not computed"}
                                  </dd>
                                </div>
                                <div>
                                  <dt>Boundary tolerance</dt>
                                  <dd>
                                    {validation.data.boundary_tolerance_m} m
                                  </dd>
                                </div>
                              </dl>
                              <ul className="geo-check-list">
                                {Object.entries(validation.data.checks).map(
                                  ([name, passes]) => (
                                    <li key={name}>
                                      <span
                                        className={passes ? "passes" : "fails"}
                                      >
                                        {passes ? "PASS" : "FAIL"}
                                      </span>
                                      {name.replaceAll("_", " ")}
                                    </li>
                                  ),
                                )}
                              </ul>
                              {validation.data.warnings.length > 0 && (
                                <div className="geo-validation-messages warnings">
                                  <h4>Warnings</h4>
                                  <ul>
                                    {validation.data.warnings.map((warning) => (
                                      <li key={warning}>{warning}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {validation.data.errors.length > 0 && (
                                <div className="geo-validation-messages errors">
                                  <h4>Errors</h4>
                                  <ul>
                                    {validation.data.errors.map((error) => (
                                      <li key={error}>{error}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              <p className="capability-note">
                                Topology checks do not establish real-world
                                network accuracy.
                              </p>
                            </>
                          )
                        )}
                      </section>
                    </div>
                    <section
                      className="panel geo-provenance"
                      aria-labelledby="provenance-title"
                    >
                      <div className="panel-heading">
                        <div>
                          <p className="section-kicker">DATASET PROVENANCE</p>
                          <h3 id="provenance-title">
                            Source, attribution & license
                          </h3>
                        </div>
                        <Database size={19} className="muted-icon" />
                      </div>
                      {!sourceId ? (
                        <p className="geo-empty-copy">
                          No data source is registered for this version.
                          Licensing and attribution have not been verified.
                        </p>
                      ) : source.isPending ? (
                        <Loading label="Loading source provenance" />
                      ) : source.isError ? (
                        <QueryError
                          message="Data source provenance is unavailable. Licensing must not be assumed."
                          retry={() => {
                            void source.refetch();
                          }}
                        />
                      ) : (
                        source.data && (
                          <>
                            <div className="geo-source-heading">
                              <div>
                                <h4>{source.data.dataset_name}</h4>
                                <p>
                                  {source.data.provider_name} ·{" "}
                                  {source.data.source_type}
                                </p>
                              </div>
                              {source.data.is_synthetic && (
                                <span className="geo-synthetic-chip">
                                  PROJECT-GENERATED SYNTHETIC
                                </span>
                              )}
                            </div>
                            <dl className="geo-definition-grid">
                              <div>
                                <dt>License identifier</dt>
                                <dd data-testid="source-license">
                                  {source.data.license_identifier ??
                                    "Not provided — usage unverified"}
                                </dd>
                              </div>
                              <div>
                                <dt>Source version</dt>
                                <dd>{source.data.source_version}</dd>
                              </div>
                              <div>
                                <dt>Collected at · UTC</dt>
                                <dd>
                                  {new Date(
                                    source.data.collected_at,
                                  ).toISOString()}
                                </dd>
                              </div>
                              <div>
                                <dt>Source URL</dt>
                                <dd>
                                  {source.data.source_url ? (
                                    <a
                                      href={source.data.source_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                    >
                                      Source reference{" "}
                                      <ArrowUpRight size={12} />
                                    </a>
                                  ) : (
                                    "Project-generated; no external source URL"
                                  )}
                                </dd>
                              </div>
                              <div className="geo-full">
                                <dt>Attribution</dt>
                                <dd>{source.data.attribution_text}</dd>
                              </div>
                              <div className="geo-full">
                                <dt>Original content checksum · SHA-256</dt>
                                <dd className="geo-mono">
                                  {source.data.checksum_sha256}
                                </dd>
                              </div>
                            </dl>
                            <p className="capability-note">
                              Public access does not imply a data license.
                              Review the recorded license and attribution before
                              reuse.
                            </p>
                          </>
                        )
                      )}
                    </section>
                  </>
                )}
              </>
            )
          )}
        </>
      )}
    </div>
  );
}
