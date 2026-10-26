import { BoundingSphere, Cartesian2, Cartesian3, HeadingPitchRange, Math as CMath, Rectangle, type Viewer } from "cesium";
import { CAMERA_PRESETS } from "../../../lib/geo/camera-presets";
import { positionBounds } from "../../../lib/geo/coordinates";
import type { Bounds, CameraCommand, CameraSnapshot, FeatureSelection, SceneData } from "../../../lib/city/types";

function flyBounds(viewer: Viewer, bounds: Bounds, perspective: boolean): void {
  const rectangle = Rectangle.fromDegrees(...bounds);
  const sphere = BoundingSphere.fromRectangle3D(rectangle);
  viewer.camera.flyToBoundingSphere(sphere, {
    duration: 1.15,
    offset: new HeadingPitchRange(0, perspective ? -1.0 : -CMath.PI_OVER_TWO, Math.max(sphere.radius * 3.1, 450)),
  });
}
export function applyCamera(viewer: Viewer, command: CameraCommand, data: SceneData, selection: FeatureSelection): void {
  const preset = command.preset;
  viewer.camera.cancelFlight();
  if (preset === "zoom-in" || preset === "zoom-out") {
    const step = Math.max(50, viewer.camera.positionCartographic.height * 0.35);
    if (preset === "zoom-in") viewer.camera.zoomIn(step); else viewer.camera.zoomOut(step);
  } else if (preset === "region" && data.region) flyBounds(viewer, data.region.bounds, true);
  else if (preset === "feature" && selection?.kind === "road") {
    const road = data.roads.find((value) => value.id === selection.id);
    if (road) flyBounds(viewer, positionBounds(road.geometry.coordinates), true);
  } else if (preset === "feature" && selection?.kind === "intersection") {
    const node = data.intersections.find((value) => value.id === selection.id);
    if (node) {
      const [x,y] = node.geometry.coordinates;
      flyBounds(viewer, [x-0.0006,y-0.0006,x+0.0006,y+0.0006], true);
    }
  } else if (preset === "feature") {
    // Buildings expose provider metadata only; no invented feature bounds.
    return;
  } else if (preset === "top-down" || preset === "perspective") {
    const screenCenter = new Cartesian2(viewer.canvas.clientWidth / 2, viewer.canvas.clientHeight / 2);
    const ray = viewer.camera.getPickRay(screenCenter);
    // Orbit the actual visible ground focus. Rotating in place at the camera's
    // cartographic position would shift a perspective view away from the study.
    const target = (ray ? viewer.scene.globe.pick(ray,viewer.scene) : undefined)
      ?? viewer.camera.pickEllipsoid(screenCenter,viewer.scene.globe.ellipsoid)
      ?? (data.region ? Cartesian3.fromDegrees(...data.region.centroid) : undefined);
    if (!target) return;
    const range = Math.max(150,Cartesian3.distance(viewer.camera.positionWC,target));
    viewer.camera.flyToBoundingSphere(new BoundingSphere(target,0),{
      duration:0.75,
      offset:new HeadingPitchRange(viewer.camera.heading,preset === "top-down" ? -CMath.PI_OVER_TWO : -CMath.toRadians(55),range),
    });
  } else {
    const target = preset in CAMERA_PRESETS ? CAMERA_PRESETS[preset as keyof typeof CAMERA_PRESETS] : CAMERA_PRESETS.downtown;
    viewer.camera.flyTo({ destination: Cartesian3.fromDegrees(target.longitude,target.latitude,target.height), orientation: { heading: 0, pitch: CMath.toRadians(target.pitch), roll: 0 }, duration: 1.25 });
  }
  viewer.scene.requestRender();
}
export function cameraSnapshot(viewer: Viewer): CameraSnapshot {
  const current = viewer.camera.positionCartographic;
  const rectangle = viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);
  const bounds: Bounds | null = rectangle ? [CMath.toDegrees(rectangle.west), CMath.toDegrees(rectangle.south), CMath.toDegrees(rectangle.east), CMath.toDegrees(rectangle.north)] : null;
  return { longitude: CMath.toDegrees(current.longitude), latitude: CMath.toDegrees(current.latitude), height: current.height, heading: CMath.toDegrees(viewer.camera.heading), pitch: CMath.toDegrees(viewer.camera.pitch), bounds };
}
