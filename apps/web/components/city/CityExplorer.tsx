"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  Maximize,
  Minimize,
  FlaskConical,
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
  type VisualizationMode,
  type ViewerStatus,
} from "@/lib/city/types";
import { FeatureInspector, selectedFeature } from "./FeatureInspector";
import { LayerManager } from "./LayerManager";
import { MapToolbar } from "./MapToolbar";
import { ViewerErrorBoundary } from "./ViewerErrorBoundary";
import { VisualizationModeSwitch } from "./VisualizationModeSwitch";
import {ReplayControls} from "./ReplayControls";
import {useVehicleReplay} from "../../hooks/use-vehicle-replay";
import { effectiveImageryMode, imageryDescription } from "@/lib/city/provider-policy";

const CesiumViewer = dynamic(() => import("./CesiumViewer"), {
  ssr: false,
  loading: () => (
    <div className="city-viewer-loading" role="status">
      <LoaderCircle size={22} className="city-spin" />
      <span>Loading the 3D renderer…</span>
    </div>
  ),
});

export function CityExplorer({replayRunId=null,onCloseReplay}:{replayRunId?:string|null;onCloseReplay?:()=>void}={}) {
  const [camera, setCamera] = useState<CameraSnapshot | null>(null);
  const [developmentMode, setDevelopmentMode] = useState(false);
  const [visualizationMode, setVisualizationMode] = useState<VisualizationMode>("engineering");
  const data = useCityData(camera, developmentMode);
  const replay=useVehicleReplay(replayRunId,data.networkId);
  const workspaceRef = useRef<HTMLElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState("");
  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement === workspaceRef.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  const toggleFullscreen = async () => {
    setFullscreenError("");
    try {
      if (document.fullscreenElement === workspaceRef.current) await document.exitFullscreen();
      else if (workspaceRef.current?.requestFullscreen) await workspaceRef.current.requestFullscreen();
      else throw new Error("Fullscreen is unavailable in this browser.");
    } catch {
      setFullscreenError("Fullscreen could not start. Use the expanded map or your browser window controls.");
    }
  };
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
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const selectReplay=replay.select;
  const selectReplayVehicle=useCallback((id:string)=>{selectReplay(id);setInspectorOpen(false);},[selectReplay]);
  const replayScene=useMemo(()=>replay.manifest&&replay.networkMatches?{vehicles:replay.vehicles,time:replay.time,selectedId:replay.selectedId,follow:replay.follow,onSelect:selectReplayVehicle}:null,[replay.manifest,replay.networkMatches,replay.vehicles,replay.time,replay.selectedId,replay.follow,selectReplayVehicle]);
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
    (status: ViewerStatus) => {
      setViewerStatus(status);
      if (status.phase === "webgl-unavailable") setInspectorOpen(true);
    },
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
      else if (window.matchMedia("(max-width: 760px)").matches) setInspectorOpen(viewerStatus?.phase === "webgl-unavailable");
    },
    [scope, viewerStatus?.phase],
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
  const isOSM = !isSynthetic && Boolean(data.network && (data.network.source_format.toLowerCase().includes("osm") || data.source?.provider_name.toLowerCase().includes("openstreetmap")));
  const imageryMode = data.config ? effectiveImageryMode(data.config,isSynthetic === true,visualizationMode) : null;
  const basemapSource = imageryMode === "natural-earth" ? "Natural Earth"
    : imageryMode === "ion" ? "Cesium ion" : "OpenStreetMap";
  const selectedRows = featureTab === "roads" ? data.roads : data.intersections;
  const providerErrors = (["imagery","buildings","terrain"] as const)
    .flatMap(name => viewerStatus?.[name].status === "error" ? [{name,message:viewerStatus[name].message}] : []);

  return (
    <section
      ref={workspaceRef}
      className={`city-workspace city-visualization-${visualizationMode}${developmentMode ? " city-development-mode" : ""}`}
      data-visualization-mode={visualizationMode}
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
          <p className="city-eyebrow">DOWNTOWN DUBAI / BUSINESS BAY</p>
          <h2>Dubai digital twin</h2>
          <p>Geographic exploration · source-backed road intelligence</p>
        </div>
        <div className="city-heading-actions">
          <VisualizationModeSwitch mode={visualizationMode} onChange={setVisualizationMode} />
          <span className="city-live-badge">
            <Globe2 size={14} /> {isOSM ? "OPENSTREETMAP" : developmentMode ? "DEVELOPMENT DATA" : "GEOGRAPHIC WORKSPACE"}
          </span>
        </div>
      </div>

      <div className="city-context-bar">
        <label>
          Study region
          <select
            aria-label="3D study region"
            value={data.regionId}
            disabled={!data.regions.length}
            onChange={(event) => {
              if (event.target.value === data.regionId) return;
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
              if (event.target.value === data.networkId) return;
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
          <label className="city-development-toggle" title="Show synthetic fixtures instead of imported geographic datasets">
            <input
              type="checkbox"
              aria-label="Development datasets"
              checked={developmentMode}
              onChange={(event) => {
                setDevelopmentMode(event.target.checked);
                setLayers(current=>({...current,intersections:event.target.checked,boundary:event.target.checked}));
                select(null);
                setCamera(null);
              }}
            />
            <FlaskConical size={14} /> <span>Development datasets</span>
          </label>
          <button
            type="button"
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            aria-pressed={fullscreen}
            onClick={() => void toggleFullscreen()}
          >
            {fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}
          </button>
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

      {fullscreenError && <p className="city-fullscreen-error" role="alert">{fullscreenError}</p>}
      {!developmentMode && !data.loading && !data.region && (
        <p className="city-import-notice" role="status">
          No imported road dataset is available. The geographic basemap remains operational.
          Import the bounded OpenStreetMap extract to inspect real roads; development datasets are separate fixtures.
        </p>
      )}
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
      <div className="city-provenance-strip" aria-label="Geographic data provenance">
        <span className={isOSM ? "city-real-source" : ""} data-testid="city-geographic-source">
          {isOSM ? "REAL GEOGRAPHIC DATA — OpenStreetMap" : isSynthetic ? "SYNTHETIC GEOGRAPHY — Development fixture" : `GEOGRAPHIC BASEMAP — ${basemapSource}`}
        </span>
        <span>3D BUILDINGS — {imageryMode === "local-osm"
          ? `OSM source-height context · ${viewerStatus?.buildings.status === "ready" ? "partial coverage" : viewerStatus?.buildings.status ?? "loading"}`
          : viewerStatus?.buildings.status === "ready" ? "Cesium OSM tiles · partial provider coverage"
          : !data.config?.ionPublicToken ? "Blocked · public token required" : `Cesium OSM tiles · ${viewerStatus?.buildings.status ?? "loading"}`}</span>
        <span>SYNTHETIC TRAFFIC — {replayRunId?"Recorded SUMO replay · not live":"Configure recorded runs in Scenario Studio"}</span>
        <span>LIVE TRAFFIC — Not connected</span>
        <span>INFERRED SIGNALS — Not field verified</span>
      </div>
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
                    ? "OSM ROAD NETWORK"
                    : "GEOGRAPHIC CONTEXT"}
              </span>
            </div>
            <ViewerErrorBoundary key={viewerGeneration} retry={retryViewer}>
              {data.config ? (
                <CesiumViewer
                  data={data.sceneData}
                  config={data.config}
                  visualizationMode={visualizationMode}
                  replay={replayScene}
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
                {isSynthetic ? "Simulated signal flag" : "OSM signal tag · unverified"}
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
            <span data-testid="camera-position" data-camera={data.config?.diagnosticsEnabled && camera ? JSON.stringify(camera) : undefined}>
              {camera
                ? `${camera.longitude.toFixed(5)}° E · ${camera.latitude.toFixed(5)}° N · ${Math.round(camera.height).toLocaleString("en")} m altitude`
                : "Camera position available when the globe initializes"}
            </span>
            <span className="city-position-crs">
              EPSG:4326 · longitude, latitude
            </span>
            <span className="city-map-progress" role="status">
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
                            {"name" in feature.properties && feature.properties.name ? feature.properties.name : label}
                            <small>
                              {feature.properties.is_synthetic
                                ? "Synthetic"
                                : "OpenStreetMap · source geometry"}
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
              hasProviderAccess={visualizationMode === "realistic" && !isSynthetic && Boolean(data.config?.ionPublicToken)}
              hasLocalBuildings={!isSynthetic && imageryMode === "local-osm"}
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

      {replayRunId&&<ReplayControls replay={replay} onClose={()=>onCloseReplay?.()} onMatchNetwork={()=>{setDevelopmentMode(false);if(replay.manifest)data.selectNetwork(replay.manifest.network_version_id);}}/>}
      <div className="city-data-footer">
      <details className="city-metadata">
        <summary><Database size={14} /> Network &amp; source details <span>{data.network ? `${data.network.edge_count.toLocaleString("en")} roads · ${data.network.node_count.toLocaleString("en")} nodes` : "No network selected"}</span><ChevronDown size={13} /></summary>
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
      {!isSynthetic && <section className="city-experiment-help"><strong>Reproducible real-network SUMO smoke</strong><p>Run <code>make smoke-real</code> from the repository. It creates three synthetic vehicles on mapped imported roads, verifies actual movement/completion, and saves recorded FCD and metrics. No live traffic or browser vehicle playback is connected.</p></section>}
      </details>

      {data.messages.length > 0 && (
        <details className="city-view-notices">
          <summary><AlertTriangle size={12} /> View notices <span>{data.messages.length}</span></summary>
          <div className="city-data-messages" role="status">
            {data.messages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        </details>
      )}
      </div>
      {data.config && (
        <div className={`city-provider-notice${visualizationMode === "realistic" && !data.config.ionPublicToken && !isSynthetic ? " city-provider-unavailable" : ""}`}>
          <Globe2 size={15} />
          <div>
            {visualizationMode === "realistic" && !data.config.ionPublicToken && !isSynthetic && <strong>Aerial imagery unavailable — configure public ion access. </strong>}
            {imageryDescription(data.config,isSynthetic === true,visualizationMode)}.
            {!data.config.ionPublicToken && <> <strong>Cesium ion building tiles unavailable:</strong> configure NEXT_PUBLIC_CESIUM_ION_TOKEN.</>}
            {imageryMode === "local-osm" && <> Ellipsoid terrain; OSM tagged-height buildings cover only part of the source area.</>}
            {providerErrors.map(({name,message}) => <span role="alert" key={name}> {name}: {message}</span>)}
            {visualizationMode === "realistic" && !data.config.ionPublicToken && !isSynthetic && (
              <details className="city-access-help">
                <summary>Access requirements</summary>
                <p>Configure NEXT_PUBLIC_CESIUM_ION_TOKEN with read-only access to the authorized aerial imagery asset and Cesium OSM Buildings. Set CESIUM_ION_IMAGERY_ASSET_ID to that asset, then recreate the web service. Token values stay outside source control.</p>
              </details>
            )}
          </div>
        </div>
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
