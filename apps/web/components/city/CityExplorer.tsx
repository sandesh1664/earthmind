"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ChevronDown,
  Crosshair,
  Database,
  Globe2,
  Layers3,
  LoaderCircle,
  MapPin,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useCityData } from "@/hooks/use-city-data";
import {
  DEFAULT_LAYERS,
  type CameraCommand,
  type CameraPreset,
  type CameraSnapshot,
  type FeatureSelection,
  type ViewerStatus,
} from "@/lib/city/types";
import { FeatureInspector, selectedFeature } from "./FeatureInspector";
import { LayerManager } from "./LayerManager";
import { MapToolbar } from "./MapToolbar";
import { ViewerErrorBoundary } from "./ViewerErrorBoundary";

const CesiumViewer = dynamic(() => import("./CesiumViewer"), {
  ssr: false,
  loading: () => (
    <div className="city-viewer-loading" role="status">
      <LoaderCircle size={22} className="city-spin" />
      <span>Loading the 3D renderer…</span>
    </div>
  ),
});

export function CityExplorer() {
  const [camera, setCamera] = useState<CameraSnapshot | null>(null);
  const data = useCityData(camera);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [picked, setPicked] = useState<{
    scope: string;
    feature: FeatureSelection;
  } | null>(null);
  const [viewerStatus, setViewerStatus] = useState<ViewerStatus | null>(null);
  const [cameraCommand, setCameraCommand] = useState<CameraCommand>({
    preset: "downtown",
    sequence: 0,
  });
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [layersOpen, setLayersOpen] = useState(false);
  const [featureTab, setFeatureTab] = useState<"roads" | "intersections">(
    "roads",
  );
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [viewerGeneration, setViewerGeneration] = useState(0);
  const scope = `${data.regionId}/${data.networkId}`;
  const candidate = picked?.scope === scope ? picked.feature : null;
  const selection =
    candidate?.kind === "building" ||
    selectedFeature(candidate, data.roads, data.intersections)
      ? candidate
      : null;
  const ready = viewerStatus?.phase === "ready";
  const statusCallback = useCallback(
    (status: ViewerStatus) => setViewerStatus(status),
    [],
  );
  const cameraCallback = useCallback(
    (next: CameraSnapshot) => setCamera(next),
    [],
  );
  const select = useCallback(
    (feature: FeatureSelection) => {
      setPicked(feature ? { scope, feature } : null);
      if (feature) setInspectorOpen(true);
    },
    [scope],
  );
  const command = useCallback(
    (preset: CameraPreset) =>
      setCameraCommand((previous) => ({
        preset,
        sequence: previous.sequence + 1,
      })),
    [],
  );
  const retryViewer = () => {
    setViewerStatus(null);
    setViewerGeneration((value) => value + 1);
  };
  const classes = useMemo(
    () =>
      [...new Set(data.roads.map((road) => road.properties.road_class))].slice(
        0,
        4,
      ),
    [data.roads],
  );
  const isSynthetic =
    data.network?.is_synthetic ?? data.region?.metadata.is_synthetic;
  const selectedRows = featureTab === "roads" ? data.roads : data.intersections;

  return (
    <section
      className="city-workspace"
      aria-label="Dubai 3D digital twin"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          select(null);
          setLayersOpen(false);
        }
      }}
    >
      <div className="city-heading">
        <div>
          <p className="city-eyebrow">M03 · GEOGRAPHIC VISUALIZATION</p>
          <h2>Dubai digital twin</h2>
          <p>Explore geographic context and inspect versioned study data.</p>
        </div>
        <span className="city-live-badge">
          <Globe2 size={14} /> 3D EXPLORER
        </span>
      </div>

      <div className="city-context-bar">
        <label>
          Study region
          <select
            aria-label="3D study region"
            value={data.regionId}
            disabled={!data.regions.length}
            onChange={(event) => {
              data.selectRegion(event.target.value);
              select(null);
              setCamera(null);
            }}
          >
            {data.regions.length ? (
              data.regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))
            ) : (
              <option value="">
                {data.loading ? "Loading regions…" : "No study regions"}
              </option>
            )}
          </select>
        </label>
        <label>
          Network version
          <select
            aria-label="3D network version"
            value={data.networkId}
            disabled={!data.networks.length}
            onChange={(event) => {
              data.selectNetwork(event.target.value);
              select(null);
            }}
          >
            {data.networks.length ? (
              data.networks.map((network) => (
                <option key={network.id} value={network.id}>
                  {network.version_label} · {network.status}
                </option>
              ))
            ) : (
              <option value="">
                {data.loading ? "Loading networks…" : "No network versions"}
              </option>
            )}
          </select>
        </label>
        <div className="city-context-actions">
          <button
            type="button"
            aria-expanded={layersOpen}
            aria-controls="city-layer-drawer"
            onClick={() => setLayersOpen((open) => !open)}
          >
            <Layers3 size={16} /> Layers <ChevronDown size={13} />
          </button>
          <button
            type="button"
            aria-label={
              inspectorOpen
                ? "Hide feature inspector"
                : "Show feature inspector"
            }
            aria-expanded={inspectorOpen}
            onClick={() => setInspectorOpen((open) => !open)}
          >
            {inspectorOpen ? (
              <PanelRightClose size={17} />
            ) : (
              <PanelRightOpen size={17} />
            )}
          </button>
          <button
            type="button"
            aria-label="Refresh geographic data"
            onClick={data.retry}
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {data.errors.length > 0 && (
        <div className="city-query-errors" role="alert">
          <AlertTriangle size={17} />
          <div>
            <strong>Some geographic data could not load</strong>
            {data.errors.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </div>
          <button type="button" onClick={data.retry}>
            Retry data
          </button>
        </div>
      )}
      {isSynthetic && (
        <div className="city-synthetic-strip" role="note">
          <ShieldCheck size={15} />
          <span>
            <strong>Synthetic study data.</strong> Illustrative boundary and
            invented roads; no official street, signal, or live traffic accuracy
            is claimed.
          </span>
        </div>
      )}

      <div
        className={`city-scene-layout ${inspectorOpen ? "has-inspector" : ""}`}
      >
        <div className="city-map-column">
          <div className="city-map-stage">
            <div className="city-map-label">
              <span className={`city-state-dot ${ready ? "ready" : ""}`} />
              <span>{ready ? "CESIUM · WGS84" : "3D WORKSPACE"}</span>
              <span className="city-source-pill">
                {isSynthetic
                  ? "SYNTHETIC OVERLAYS"
                  : data.network
                    ? "STORED NETWORK"
                    : "GEOGRAPHIC CONTEXT"}
              </span>
            </div>
            <ViewerErrorBoundary key={viewerGeneration} retry={retryViewer}>
              {data.config ? (
                <CesiumViewer
                  data={data.sceneData}
                  config={data.config}
                  layers={layers}
                  selection={selection}
                  cameraCommand={cameraCommand}
                  onSelect={select}
                  onCameraChange={cameraCallback}
                  onStatus={statusCallback}
                />
              ) : (
                <div className="city-viewer-loading" role="status">
                  <LoaderCircle size={22} className="city-spin" />
                  <span>
                    {data.errors.length
                      ? "Viewer configuration is unavailable. Retry data to continue."
                      : "Preparing the geographic workspace…"}
                  </span>
                </div>
              )}
            </ViewerErrorBoundary>
            {(viewerStatus?.phase === "error" ||
              viewerStatus?.phase === "webgl-unavailable") && (
              <div className="city-renderer-alert" role="alert">
                <AlertTriangle size={18} />
                <strong>
                  {viewerStatus.phase === "webgl-unavailable"
                    ? "WebGL is unavailable"
                    : "3D renderer unavailable"}
                </strong>
                <p>{viewerStatus.message}</p>
                <button type="button" onClick={retryViewer}>
                  Retry 3D viewer
                </button>
              </div>
            )}
            <div className="city-map-progress" role="status">
              {data.geometryLoading ? (
                <>
                  <LoaderCircle className="city-spin" size={13} /> Loading
                  visible network…
                </>
              ) : ready ? (
                <>
                  <span data-testid="scene-road-count">
                    {viewerStatus.roadCount}
                  </span>{" "}
                  roads ·{" "}
                  <span data-testid="scene-intersection-count">
                    {viewerStatus.intersectionCount}
                  </span>{" "}
                  intersections rendered
                </>
              ) : (
                (viewerStatus?.message ?? "Starting viewer")
              )}
            </div>
            <div className="city-map-legend" aria-label="Map legend">
              <span>
                <i className="city-legend-line" />
                {classes.length
                  ? classes.join(" · ").replaceAll("_", " ")
                  : "Road centerlines"}
              </span>
              <span>
                <i className="city-legend-node" />
                Intersection
              </span>
              <span>
                <i className="city-legend-node signal" />
                Stored signal flag
              </span>
              <span>
                <i className="city-legend-selected" />
                Selected feature
              </span>
            </div>
          </div>
          <MapToolbar
            command={command}
            disabled={!ready}
            hasRegion={Boolean(data.region)}
            hasSelection={selection !== null && selection.kind !== "building"}
          />
          <div
            className="city-position-bar"
            aria-label="Camera position indicator"
          >
            <MapPin size={13} />
            <span data-testid="camera-position">
              {camera
                ? `${camera.longitude.toFixed(5)}° E · ${camera.latitude.toFixed(5)}° N · ${Math.round(camera.height).toLocaleString("en")} m altitude`
                : "Camera position available when the globe initializes"}
            </span>
            <span className="city-position-crs">
              EPSG:4326 · longitude, latitude
            </span>
          </div>
        </div>

        {inspectorOpen && (
          <aside
            className={`city-right-panel ${selection ? "has-selection" : ""}`}
            aria-label="Geographic inspection panel"
          >
            <FeatureInspector
              selection={selection}
              roads={data.roads}
              intersections={data.intersections}
              network={data.network}
              source={data.source}
              validation={data.validation}
              onDeselect={() => select(null)}
              onZoom={() => command("feature")}
              onClose={() => setInspectorOpen(false)}
            />
            <section
              className="city-feature-list"
              aria-labelledby="city-features-title"
            >
              <div className="city-panel-heading">
                <h3 id="city-features-title">
                  <Crosshair size={14} /> Visible features
                </h3>
                <span>{selectedRows.length}</span>
              </div>
              <div className="city-feature-tabs">
                <button
                  type="button"
                  aria-pressed={featureTab === "roads"}
                  onClick={() => setFeatureTab("roads")}
                >
                  Roads
                </button>
                <button
                  type="button"
                  aria-pressed={featureTab === "intersections"}
                  onClick={() => setFeatureTab("intersections")}
                >
                  Intersections
                </button>
              </div>
              {data.geometryLoading ? (
                <p className="city-empty-copy">
                  Loading the current map extent…
                </p>
              ) : !selectedRows.length ? (
                <p className="city-empty-copy">
                  {data.viewportState === "outside"
                    ? "The camera is outside the selected study region. Zoom to the study region to inspect its network."
                    : data.viewportState === "zoom"
                      ? "Zoom closer to load a bounded network view."
                      : "No features are stored in this view."}
                </p>
              ) : (
                <ul>
                  {selectedRows.slice(0, 100).map((feature) => {
                    const road = "sumo_edge_id" in feature.properties;
                    const label =
                      "sumo_edge_id" in feature.properties
                        ? feature.properties.sumo_edge_id
                        : feature.properties.source_node_id;
                    return (
                      <li key={feature.id}>
                        <button
                          type="button"
                          className={
                            selection?.id === feature.id ? "selected" : ""
                          }
                          aria-label={`Inspect ${road ? "road" : "intersection"} ${label}`}
                          aria-pressed={selection?.id === feature.id}
                          disabled={
                            road ? !layers.roads : !layers.intersections
                          }
                          onClick={() =>
                            select({
                              kind: road ? "road" : "intersection",
                              id: feature.id,
                            })
                          }
                        >
                          <span
                            className={road ? "city-row-road" : "city-row-node"}
                          />
                          <span>
                            {label}
                            <small>
                              {feature.properties.is_synthetic
                                ? "Synthetic"
                                : "Stored source"}
                            </small>
                          </span>
                          <Crosshair size={12} />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {selectedRows.length > 100 && (
                <p className="city-empty-copy">
                  First 100 features listed. Zoom closer or select on the map.
                </p>
              )}
            </section>
          </aside>
        )}
        {layersOpen && (
          <div className="city-layer-drawer" id="city-layer-drawer">
            <LayerManager
              layers={layers}
              onChange={setLayers}
              status={viewerStatus}
              hasProviderAccess={Boolean(data.config?.ionPublicToken)}
            />
            <button
              type="button"
              className="city-layer-close"
              onClick={() => setLayersOpen(false)}
            >
              Close layers
            </button>
          </div>
        )}
      </div>

      <div className="city-summary-grid">
        <section className="city-study-summary">
          <div className="city-panel-heading">
            <h3>
              <MapPin size={15} /> Study region
            </h3>
            <span>{data.region?.country_code ?? "—"}</span>
          </div>
          <strong>
            {data.region?.name ??
              (data.loading ? "Loading region…" : "No region selected")}
          </strong>
          <dl>
            <div>
              <dt>Geodesic area</dt>
              <dd data-testid="city-region-area">
                {data.region
                  ? `${data.region.area_km2.toLocaleString("en", { maximumFractionDigits: 4 })} km²`
                  : "Not available"}
              </dd>
            </div>
            <div>
              <dt>Stored network</dt>
              <dd>
                {data.network
                  ? `${data.network.node_count} nodes · ${data.network.edge_count} edges`
                  : "No network selected"}
              </dd>
            </div>
            <div className="city-full-field">
              <dt>Bounds · west, south, east, north</dt>
              <dd data-testid="city-region-bounds">
                {data.region?.bounds
                  .map((value) => value.toFixed(5))
                  .join(", ") ?? "Not available"}
              </dd>
            </div>
          </dl>
        </section>
        <section className="city-provenance-summary">
          <div className="city-panel-heading">
            <h3>
              <Database size={15} /> Dataset provenance
            </h3>
            <span className="city-validation-status">
              {data.validation?.status ??
                data.network?.validation_summary.status ??
                "NOT_VALIDATED"}
            </span>
          </div>
          <strong>
            {data.source?.dataset_name ?? "No source record available"}
          </strong>
          <p>
            {data.source?.provider_name ?? "Source attribution has not loaded."}
          </p>
          <dl>
            <div>
              <dt>License</dt>
              <dd data-testid="city-source-license">
                {data.source?.license_identifier ?? "Not recorded"}
              </dd>
            </div>
            <div>
              <dt>Source version</dt>
              <dd>{data.source?.source_version ?? "Not recorded"}</dd>
            </div>
          </dl>
          <p className="city-attribution">
            {data.source?.attribution_text ??
              "Review a recorded license before reusing external data."}
          </p>
        </section>
      </div>

      {data.messages.length > 0 && (
        <div className="city-data-messages" role="status">
          {data.messages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
      {!data.config?.ionPublicToken && data.config && (
        <p className="city-provider-notice">
          <Globe2 size={15} />
          <span>
            Using the bundled Natural Earth basemap and ellipsoid globe.
            Optional ion imagery, terrain and 3D buildings require a scoped
            public visualization token. Building access:{" "}
            <strong>BLOCKED — token not configured.</strong>
          </span>
        </p>
      )}
      {data.config?.diagnosticsEnabled && (
        <section className="city-diagnostics">
          <button
            type="button"
            aria-expanded={diagnosticsOpen}
            onClick={() => setDiagnosticsOpen((open) => !open)}
          >
            <Activity size={15} /> Local rendering diagnostics{" "}
            <ChevronDown size={13} />
          </button>
          {diagnosticsOpen && (
            <div>
              <p>
                Actual browser observations. Request-render idle time is not
                animation throughput; JS heap excludes GPU allocations.
              </p>
              <dl>
                <div>
                  <dt>Rendered frames</dt>
                  <dd>{viewerStatus?.renderedFrames ?? "Not sampled"}</dd>
                </div>
                <div>
                  <dt>Recent rendered FPS</dt>
                  <dd>
                    {viewerStatus?.sampleFps == null
                      ? "Idle / not sampled"
                      : viewerStatus.sampleFps.toFixed(1)}
                  </dd>
                </div>
                <div>
                  <dt>Browser JS heap</dt>
                  <dd>
                    {viewerStatus?.heapBytes == null
                      ? "Not available"
                      : `${(viewerStatus.heapBytes / 1024 / 1024).toFixed(1)} MiB`}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </section>
      )}
    </section>
  );
}

export default CityExplorer;
