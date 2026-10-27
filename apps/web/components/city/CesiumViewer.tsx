"use client";

import { useEffect, useRef, useState } from "react";
import type { CesiumViewerProps, ViewerStatus } from "../../lib/city/types";
import type { CitySceneController } from "./runtime/scene-controller";
import { ResourceGeneration } from "./runtime/lifecycle";

const INITIAL_STATUS: ViewerStatus = {
  phase:"loading",message:"Loading the 3D geographic renderer",
  buildings:{status:"off",message:"Optional buildings disabled"},
  imagery:{status:"off",message:"Initializing imagery"},
  terrain:{status:"off",message:"WGS84 ellipsoid"},roadCount:0,intersectionCount:0,
};

export function CesiumViewer(props: CesiumViewerProps) {
  const host = useRef<HTMLDivElement>(null);
  const controller = useRef<CitySceneController | null>(null);
  const latest = useRef(props);
  const reportStatus = useRef<((status: ViewerStatus) => void) | null>(null);
  const [status,setStatus] = useState<ViewerStatus>(INITIAL_STATUS);
  useEffect(() => { latest.current = props; controller.current?.update({...props,onStatus:reportStatus.current ?? props.onStatus}); },[props]);
  useEffect(() => {
    const lifetime = new ResourceGeneration();
    const generation = lifetime.next();
    const element = host.current;
    if (!element) return;
    // This executes before importing the module containing Cesium. Workers,
    // ThirdParty, Assets and Widgets are version-matched, same-origin files.
    (window as Window & {CESIUM_BASE_URL?:string}).CESIUM_BASE_URL = "/cesium/";
    const report = (value: ViewerStatus) => {
      if (!lifetime.current(generation)) return;
      setStatus(value); latest.current.onStatus(value);
    };
    reportStatus.current = report;
    void import("./runtime/scene-controller").then(({CitySceneController: Scene}) => {
      if (!lifetime.current(generation)) return;
      controller.current = new Scene(element,{...latest.current,onStatus:report});
    }).catch((error: unknown) => {
      if (!lifetime.current(generation)) return;
      const graphics = error instanceof Error && /webgl|context|graphics|gpu/i.test(error.message);
      report({...INITIAL_STATUS,phase:graphics ? "webgl-unavailable" : "error",message:graphics ? "WebGL is unavailable. Enable browser hardware acceleration or use a supported browser; geographic metadata remains accessible." : "The 3D renderer could not initialize. Check local Cesium assets and retry."});
    });
    return () => {
      lifetime.dispose();
      controller.current?.destroy(); controller.current = null;
      element.replaceChildren();
    };
  },[]);
  return <div className="city-viewer-surface" data-testid="cesium-viewer" data-visualization-mode={status.visualizationMode ?? props.visualizationMode ?? "engineering"} data-viewer-instance-id={status.viewerInstanceId} data-phase={status.phase} data-imagery-status={status.imagery.status} data-buildings-status={status.buildings.status} data-render-diagnostics={status.renderDiagnostics ? JSON.stringify(status.renderDiagnostics) : undefined} data-local-building-count={status.localBuildingCount ?? 0} data-road-count={status.roadCount} data-intersection-count={status.intersectionCount} data-geometry-ready={status.geometryReady ?? false} data-camera-moving={status.cameraMoving ?? false} data-layer-visibility={JSON.stringify(status.layerVisibility ?? {})} data-pick-x={status.pickProbe?.x} data-pick-y={status.pickProbe?.y} data-pick-id={status.pickProbe?.id}>
    <div ref={host} className="city-cesium-host" aria-label="Interactive 3D geographic globe" />
    {status.phase !== "ready" && <div className="city-viewer-message" role={status.phase === "loading" ? "status" : "alert"}>{status.message}</div>}
  </div>;
}
export default CesiumViewer;
