import type {ReplaySceneState} from "../replay";
import type { Network, Region, RegionFeature } from "../geospatial";

export type Position = [number, number];
export type Bounds = [number, number, number, number];
export type VisualizationMode = "engineering" | "realistic";
export interface RoadFeature {
  type: "Feature";
  id: string;
  geometry: { type: "LineString"; coordinates: Position[] };
  properties: {
    network_version_id: string;
    metadata?: Record<string, string | string[] | number | boolean | null | undefined>;
    sumo_edge_id: string;
    source_edge_id?: string | null;
    name?: string | null;
    road_class: string;
    lane_count: number;
    speed_limit_mps?: number | null;
    length_m: number;
    is_one_way: boolean;
    is_synthetic: boolean;
    start_intersection_id?: string;
    end_intersection_id?: string;
  };
}
export interface IntersectionFeature {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: Position };
  properties: {
    network_version_id: string;
    metadata?: Record<string, string | string[] | number | boolean | null | undefined>;
    source_node_id: string;
    sumo_node_id?: string | null;
    intersection_type: string;
    is_signalized?: boolean;
    is_synthetic: boolean;
  };
}
export type FeatureSelection =
  | { kind: "road" | "intersection"; id: string }
  | { kind: "building"; id: string; properties: Record<string, string | number | boolean> }
  | null;
export interface LayerSettings {
  boundary: boolean;
  roads: boolean;
  intersections: boolean;
  buildings: boolean;
  imagery: boolean;
  terrain: boolean;
  highlight: boolean;
  centroid: boolean;
}
export const DEFAULT_LAYERS: LayerSettings = {
  boundary: false, roads: true, intersections: false, buildings: true,
  imagery: true, terrain: false, highlight: true, centroid: false,
};
export interface CityConfig {
  ionPublicToken: string | null;
  imageryMode?: "local-osm" | "ion" | "natural-earth";
  imageryAssetId: number;
  terrainAssetId: number;
  diagnosticsEnabled: boolean;
}
export interface SceneData {
  region: Region | null;
  boundary: RegionFeature | null;
  network: Network | null;
  roads: RoadFeature[];
  intersections: IntersectionFeature[];
}
export type CameraPreset = "dubai" | "downtown" | "business-bay" | "region" | "feature" | "top-down" | "perspective" | "reset" | "zoom-in" | "zoom-out";
export interface CameraCommand { preset: CameraPreset; sequence: number }
export interface CameraSnapshot {
  longitude: number; latitude: number; height: number;
  heading: number; pitch: number; bounds: Bounds | null;
  groundFocus?: Position | null;
}
export interface ProviderState {
  status: "off" | "loading" | "ready" | "blocked" | "error";
  message: string;
}
export interface ViewerStatus {
  phase: "loading" | "ready" | "error" | "webgl-unavailable";
  message: string;
  buildings: ProviderState; imagery: ProviderState; terrain: ProviderState;
  roadCount: number; intersectionCount: number;
  visualizationMode?: VisualizationMode;
  viewerInstanceId?: number;
  localBuildingCount?: number;
  replayVehicleCount?:number;
  replayReadyCount?:number;
  replayInViewCount?:number;
  replayProbe?:{id:string;x:number;y:number;longitude:number;latitude:number;time:number}|null;
  geometryReady?: boolean;
  cameraMoving?: boolean;
  renderDiagnostics?: {
    globeVisible: boolean; globeTilesLoaded: boolean; imageryLayerCount: number;
    boundaryFillAlpha: number | null;
  };
  layerVisibility?: Record<keyof LayerSettings, boolean>;
  pickProbe?: { kind: "road"; id: string; x: number; y: number } | null;
  renderedFrames?: number; sampleFps?: number | null; heapBytes?: number | null;
}
export interface CesiumViewerProps {
  data: SceneData;
  config: CityConfig;
  visualizationMode?: VisualizationMode;
  replay?:ReplaySceneState|null;
  layers: LayerSettings;
  selection: FeatureSelection;
  cameraCommand: CameraCommand;
  onSelect: (selection: FeatureSelection) => void;
  onCameraChange: (camera: CameraSnapshot) => void;
  onStatus: (status: ViewerStatus) => void;
}
