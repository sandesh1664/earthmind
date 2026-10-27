"use client";

import { Layers3, LockKeyhole } from "lucide-react";
import type {
  LayerSettings,
  ProviderState,
  ViewerStatus,
} from "@/lib/city/types";

const LAYERS: {
  key: keyof LayerSettings;
  label: string;
  source: string;
}[] = [
  { key: "boundary", label: "Study region", source: "PostGIS boundary" },
  { key: "roads", label: "Road centerlines", source: "Versioned network" },
  {
    key: "intersections",
    label: "Intersections",
    source: "Stored node records",
  },
  { key: "buildings", label: "3D buildings", source: "OSM height tags / optional ion tiles" },
  {
    key: "imagery",
    label: "Geographic basemap",
    source: "Local OSM / configured ion",
  },
  { key: "terrain", label: "World terrain", source: "Configured Cesium ion" },
  {
    key: "highlight",
    label: "Selection highlight",
    source: "Selected feature",
  },
  {
    key: "centroid",
    label: "Region centroid",
    source: "PostGIS representative point",
  },
];

export function toggleLayer(
  layers: LayerSettings,
  key: keyof LayerSettings,
): LayerSettings {
  return { ...layers, [key]: !layers[key] };
}

export function LayerManager({
  layers,
  onChange,
  status,
  hasProviderAccess,
  hasLocalBuildings = false,
}: {
  layers: LayerSettings;
  onChange: (layers: LayerSettings) => void;
  status: ViewerStatus | null;
  hasProviderAccess: boolean;
  hasLocalBuildings?: boolean;
}) {
  const providerStates: Partial<
    Record<keyof LayerSettings, ProviderState | undefined>
  > = {
    buildings: status?.buildings,
    imagery: status?.imagery,
    terrain: status?.terrain,
  };
  return (
    <section className="city-layer-panel" aria-labelledby="city-layer-title">
      <div className="city-panel-heading">
        <h3 id="city-layer-title">
          <Layers3 size={15} /> Scene layers
        </h3>
        <span>{Object.values(layers).filter(Boolean).length} enabled</span>
      </div>
      <div className="city-layer-list">
        {LAYERS.map(({ key, label, source }) => {
          const provider = providerStates[key];
          const unavailable = !hasProviderAccess && (key === "terrain" || (key === "buildings" && !hasLocalBuildings));
          const blocked = unavailable || provider?.status === "blocked";
          const message = provider?.status === "blocked" ? provider.message
            : unavailable ? "Blocked · public provider token required" : provider?.message;
          return (
            <div className="city-layer-row" key={key}>
              <label>
                <input
                  type="checkbox"
                  checked={layers[key]}
                  disabled={blocked && !layers[key]}
                  onChange={() => onChange(toggleLayer(layers, key))}
                  aria-label={label}
                />
                <span className="city-switch" aria-hidden="true" />
                <span className="city-layer-text">
                  <strong>{label}</strong>
                  <small>{source}</small>
                </span>
                {blocked && <LockKeyhole size={13} aria-hidden="true" />}
                {blocked && <span className="city-layer-state city-warning">Blocked</span>}
                {!blocked && provider?.status === "loading" && (
                  <span className="city-layer-state">Loading</span>
                )}
                {!blocked && provider?.status === "error" && (
                  <span className="city-layer-state city-warning">Error</span>
                )}
              </label>
              {message &&
                (blocked ||
                  provider?.status === "error" ||
                  provider?.status === "loading" ||
                  (key === "imagery" && layers.imagery)) && (
                  <p
                    className={`city-layer-detail ${blocked || provider?.status === "error" ? "city-warning" : ""}`}
                  >
                    {message}
                  </p>
                )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
