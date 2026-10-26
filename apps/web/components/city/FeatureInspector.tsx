"use client";

import {
  Building2,
  Crosshair,
  GitBranch,
  MousePointer2,
  Route,
  X,
} from "lucide-react";
import type { z } from "zod";
import type {
  DataSourceSchema,
  Network,
  NetworkValidationSchema,
} from "@/lib/geospatial";
import type {
  FeatureSelection,
  IntersectionFeature,
  RoadFeature,
} from "@/lib/city/types";

export function recorded(value: unknown): string {
  if (value === null || value === undefined || value === "")
    return "Not recorded";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number")
    return Number.isFinite(value)
      ? value.toLocaleString("en", { maximumFractionDigits: 2 })
      : "Not recorded";
  return String(value);
}

export function selectedFeature(
  selection: FeatureSelection,
  roads: RoadFeature[],
  intersections: IntersectionFeature[],
) {
  if (selection?.kind === "road")
    return roads.find((item) => item.id === selection.id) ?? null;
  if (selection?.kind === "intersection")
    return intersections.find((item) => item.id === selection.id) ?? null;
  return null;
}

function Field({
  name,
  value,
  testId,
}: {
  name: string;
  value: unknown;
  testId?: string;
}) {
  return (
    <div>
      <dt>{name}</dt>
      <dd {...(testId ? { "data-testid": testId } : {})}>{recorded(value)}</dd>
    </div>
  );
}

export function FeatureInspector({
  selection,
  roads,
  intersections,
  network,
  source,
  validation,
  onDeselect,
  onZoom,
  onClose,
}: {
  selection: FeatureSelection;
  roads: RoadFeature[];
  intersections: IntersectionFeature[];
  network: Network | null;
  source: z.output<typeof DataSourceSchema> | null;
  validation: z.output<typeof NetworkValidationSchema> | null;
  onDeselect: () => void;
  onZoom: () => void;
  onClose?: () => void;
}) {
  const road =
    selection?.kind === "road"
      ? roads.find((item) => item.id === selection.id)
      : undefined;
  const node =
    selection?.kind === "intersection"
      ? intersections.find((item) => item.id === selection.id)
      : undefined;
  const building = selection?.kind === "building" ? selection : undefined;
  const hasSelection = Boolean(road || node || building);
  return (
    <section
      className="city-inspector"
      aria-labelledby="city-inspector-title"
      data-testid="feature-inspector"
    >
      <div className="city-panel-heading">
        <h3 id="city-inspector-title">
          <Crosshair size={15} /> Feature inspector
        </h3>
        {onClose && (
          <button
            type="button"
            aria-label="Close feature inspector"
            onClick={onClose}
          >
            <X size={17} />
          </button>
        )}
      </div>
      {hasSelection ? (
        <>
          <div className="city-inspector-identity">
            <span className="city-feature-symbol">
              {road ? (
                <Route size={21} />
              ) : node ? (
                <GitBranch size={21} />
              ) : (
                <Building2 size={21} />
              )}
            </span>
            <div>
              <p className="city-eyebrow">
                {road
                  ? "ROAD SEGMENT"
                  : node
                    ? "INTERSECTION"
                    : "PROVIDER BUILDING"}
              </p>
              <h4>
                {road?.properties.name ||
                  road?.properties.sumo_edge_id ||
                  node?.properties.source_node_id ||
                  (building ? "Selected building" : "Selected feature")}
              </h4>
            </div>
          </div>
          {road || node ? (
            <span
              className={`city-data-badge ${road?.properties.is_synthetic || node?.properties.is_synthetic ? "synthetic" : ""}`}
            >
              {road?.properties.is_synthetic || node?.properties.is_synthetic
                ? "SYNTHETIC DATA"
                : "STORED SOURCE DATA"}
            </span>
          ) : (
            <span className="city-data-badge">EXTERNAL PROVIDER DATA</span>
          )}
          <dl className="city-inspector-fields">
            <Field
              name={building ? "Provider feature key" : "Feature UUID"}
              value={selection?.id}
              testId="selected-feature-id"
            />
            {road && (
              <>
                <Field
                  name="Road identifier"
                  value={road.properties.sumo_edge_id}
                  testId="selected-road-identifier"
                />
                <Field
                  name="Source identifier"
                  value={road.properties.source_edge_id}
                />
                <Field
                  name="Road category"
                  value={road.properties.road_class}
                />
                <Field
                  name="Lane count"
                  value={road.properties.lane_count}
                  testId="selected-road-lanes"
                />
                <Field
                  name="Speed limit · m/s"
                  value={road.properties.speed_limit_mps}
                />
                <Field
                  name="Length · meters"
                  value={road.properties.length_m}
                  testId="selected-road-length"
                />
                <Field name="One-way" value={road.properties.is_one_way} />
                <Field
                  name="Start intersection"
                  value={road.properties.start_intersection_id}
                />
                <Field
                  name="End intersection"
                  value={road.properties.end_intersection_id}
                />
              </>
            )}
            {node && (
              <>
                <Field
                  name="Source node"
                  value={node.properties.source_node_id}
                />
                <Field
                  name="Compatibility node ID"
                  value={node.properties.sumo_node_id}
                />
                <Field
                  name="Intersection category"
                  value={node.properties.intersection_type}
                />
                <Field
                  name={
                    node.properties.is_synthetic
                      ? "Simulated signalized flag"
                      : "Stored signalized flag"
                  }
                  value={node.properties.is_signalized}
                />
                <Field
                  name="Longitude, latitude"
                  value={node.geometry.coordinates.join(", ")}
                />
              </>
            )}
            {building &&
              Object.entries(building.properties)
                .slice(0, 25)
                .map(([name, value]) => (
                  <Field key={name} name={name} value={value} />
                ))}
            {!building && (
              <>
                <Field name="Network version" value={network?.version_label} />
                <Field name="Network UUID" value={network?.id} />
                <Field name="Dataset" value={source?.dataset_name} />
                <Field name="Data source" value={source?.provider_name} />
                <Field name="Source type" value={source?.source_type} />
                <Field
                  name="Structural validation"
                  value={
                    validation?.status ?? network?.validation_summary.status
                  }
                />
              </>
            )}
          </dl>
          <p className="city-inspector-note">
            {building
              ? "Only available provider properties are shown. Building coverage and metadata vary by location."
              : "Synthetic compatibility IDs are provisional. Structural validation does not establish real-world infrastructure accuracy."}
          </p>
          <div className="city-inspector-actions">
            {!building && (
              <button type="button" onClick={onZoom}>
                Zoom to feature
              </button>
            )}
            <button type="button" onClick={onDeselect}>
              Deselect
            </button>
          </div>
        </>
      ) : (
        <div className="city-inspector-empty">
          <MousePointer2 size={28} />
          <h4>Inspect the study network</h4>
          <p>
            Select a road or intersection on the globe, or choose a visible
            feature from the list below.
          </p>
          <span>Selection priority: intersection → road → building.</span>
        </div>
      )}
    </section>
  );
}
