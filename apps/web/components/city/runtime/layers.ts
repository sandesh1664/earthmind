import {
  Cartesian3, Color, ColorGeometryInstanceAttribute, DistanceDisplayCondition,
  GeometryInstance, GroundPolylineGeometry, GroundPolylinePrimitive,
  PointPrimitiveCollection, PolygonHierarchy, PolylineColorAppearance,
  type Entity, type PointPrimitive, type Viewer,
} from "cesium";
import type { FeatureSelection, LayerSettings, SceneData, VisualizationMode } from "../../../lib/city/types";
import { flatDegrees, validPosition } from "../../../lib/geo/coordinates";

export interface PickIdentity { kind: "road" | "intersection"; id: string }
const CYAN = Color.fromCssColorString("#51cfe2");
const SELECTED = Color.fromCssColorString("#f2fbff");
function roadColor(roadClass: string): Color {
  if (/motorway|trunk/.test(roadClass)) return Color.fromCssColorString("#789bff");
  if (/primary|secondary/.test(roadClass)) return Color.fromCssColorString("#8ab8ff");
  return CYAN;
}
function roadPrimitive(data: SceneData["roads"], highlight = false, mode: VisualizationMode = "engineering"): GroundPolylinePrimitive {
  return new GroundPolylinePrimitive({
    geometryInstances: data.map((road) => new GeometryInstance({
      id: { kind: "road", id: road.id } satisfies PickIdentity,
      geometry: new GroundPolylineGeometry({ positions: Cartesian3.fromDegreesArray(flatDegrees(road.geometry.coordinates)), width: highlight ? (mode === "realistic" ? 6 : 8) : mode === "realistic" ? 2 : 4 }),
      attributes: { color: ColorGeometryInstanceAttribute.fromColor(highlight ? SELECTED : mode === "realistic" ? Color.fromCssColorString("#d6c9ac") : roadColor(road.properties.road_class)) },
    })),
    appearance: new PolylineColorAppearance({ translucent: false }),
    asynchronous: true,
    allowPicking: !highlight,
  });
}

/** Batched native objects remain owned by a single viewer mount. */
export class GeographicLayers {
  private roads: GroundPolylinePrimitive | null = null;
  private highlight: GroundPolylinePrimitive | null = null;
  private nodes: PointPrimitiveCollection;
  private points = new Map<string, PointPrimitive>();
  private regionEntities: Entity[] = [];
  private centroid: Entity | null = null;
  private previousData: SceneData | null = null;
  private selection: FeatureSelection = null;
  private flags: LayerSettings | null = null;
  private roadCount = 0;
  private nodeCount = 0;
  private mode: VisualizationMode = "engineering";
  constructor(private viewer: Viewer) {
    this.nodes = viewer.scene.primitives.add(new PointPrimitiveCollection()) as PointPrimitiveCollection;
  }
  update(data: SceneData, flags: LayerSettings, selection: FeatureSelection, mode: VisualizationMode = "engineering"): void {
    const modeChanged = mode !== this.mode;
    if (data.roads !== this.previousData?.roads || modeChanged) {
      if (this.roads) this.viewer.scene.groundPrimitives.remove(this.roads);
      this.roads = data.roads.length ? this.viewer.scene.groundPrimitives.add(roadPrimitive(data.roads,false,mode)) as GroundPolylinePrimitive : null;
      this.roadCount = data.roads.length;
    }
    if (data.intersections !== this.previousData?.intersections) {
      this.nodes.removeAll(); this.points.clear();
      for (const node of data.intersections) {
        if (!validPosition(node.geometry.coordinates)) throw new Error("Intersection position is invalid");
        const signal = node.properties.is_signalized === true;
        const point = this.nodes.add({
          id: { kind: "intersection", id: node.id } satisfies PickIdentity,
          position: Cartesian3.fromDegrees(...node.geometry.coordinates, 12),
          color: signal ? Color.fromCssColorString("#e7b866") : CYAN,
          pixelSize: signal ? 11 : 8,
          outlineWidth: 2, outlineColor: Color.fromCssColorString("#102b3c"),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new DistanceDisplayCondition(0, 60_000),
        });
        this.points.set(node.id,point);
      }
      this.nodeCount = data.intersections.length;
    }
    if (data.boundary !== this.previousData?.boundary || data.region !== this.previousData?.region) {
      for (const entity of this.regionEntities) this.viewer.entities.remove(entity);
      this.regionEntities = [];
      if (this.centroid) this.viewer.entities.remove(this.centroid);
      this.centroid = null;
      if (data.boundary && data.region) {
        data.boundary.geometry.coordinates.forEach((polygon, polygonIndex) => {
          const outer = polygon[0];
          if (!outer) return;
          const hierarchy = new PolygonHierarchy(
            Cartesian3.fromDegreesArray(flatDegrees(outer.slice(0,-1))),
            polygon.slice(1).map((ring) => new PolygonHierarchy(Cartesian3.fromDegreesArray(flatDegrees(ring.slice(0,-1))))),
          );
          this.regionEntities.push(this.viewer.entities.add({
            id: `region:${data.region!.id}:${polygonIndex}`,
            polygon: { hierarchy, material: CYAN.withAlpha(0.13), outline: false },
          }));
          polygon.forEach((ring,ringIndex) => {
            this.regionEntities.push(this.viewer.entities.add({
              id: `region-outline:${data.region!.id}:${polygonIndex}:${ringIndex}`,
              polyline: { positions: Cartesian3.fromDegreesArray(flatDegrees(ring)), width: 2, material: CYAN.withAlpha(0.9), clampToGround: true },
            }));
          });
        });
        this.centroid = this.viewer.entities.add({
          id: `centroid:${data.region.id}`,
          position: Cartesian3.fromDegrees(...data.region.centroid, 10),
          point: { pixelSize: 8, color: Color.WHITE, outlineColor: CYAN, outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        });
      }
    }
    if (modeChanged || selection?.id !== this.selection?.id || selection?.kind !== this.selection?.kind || data.roads !== this.previousData?.roads) {
      if (this.highlight) this.viewer.scene.groundPrimitives.remove(this.highlight);
      this.highlight = null;
      if (selection?.kind === "road") {
        const road = data.roads.find((value) => value.id === selection.id);
        if (road) this.highlight = this.viewer.scene.groundPrimitives.add(roadPrimitive([road],true,mode)) as GroundPolylinePrimitive;
      }
      if (this.selection?.kind === "intersection") {
        const old = this.points.get(this.selection.id);
        if (old) { old.outlineColor = Color.fromCssColorString("#102b3c"); old.outlineWidth = 2; }
      }
    }
    this.selection = selection; this.flags = flags; this.previousData = data;this.mode = mode;
    this.visibility();
    this.viewer.scene.requestRender();
  }
  visibility(): void {
    const flags = this.flags;
    if (!flags) return;
    if (this.roads) this.roads.show = flags.roads;
    if (this.highlight) this.highlight.show = flags.highlight && flags.roads;
    this.nodes.show = flags.intersections;
    for (const entity of this.regionEntities) entity.show = flags.boundary;
    if (this.centroid) this.centroid.show = flags.centroid;
    if (this.selection?.kind === "intersection") {
      const point = this.points.get(this.selection.id);
      if (point) { point.outlineColor = flags.highlight ? SELECTED : Color.fromCssColorString("#102b3c"); point.outlineWidth = flags.highlight ? 4 : 2; }
    }
  }
  counts(): {roadCount: number; intersectionCount: number} {
    return {
      roadCount: this.flags?.roads && this.roads?.ready ? this.roadCount : 0,
      intersectionCount: this.flags?.intersections && this.viewer.camera.positionCartographic.height < 60_000 ? this.nodeCount : 0,
    };
  }
  visibilitySnapshot(): Record<keyof LayerSettings, boolean> {
    return {
      boundary: this.regionEntities.some((entity) => entity.show),
      roads: !!this.roads?.show && this.roads.ready,
      intersections: this.nodes.show && this.viewer.camera.positionCartographic.height < 60_000 && this.nodeCount > 0,
      centroid: this.centroid?.show ?? false,
      highlight: !!this.highlight?.show && this.highlight.ready || this.selection?.kind === "intersection" && !!this.flags?.highlight && this.nodes.show,
      // Optional provider layers are observed by their own manager.
      buildings: false, imagery: false, terrain: false,
    };
  }
  pending(): boolean { return !!this.roads?.show && !this.roads.ready || !!this.highlight?.show && !this.highlight.ready; }
  boundaryFillAlpha(): number | null {
    const polygon = this.regionEntities.find(entity => entity.polygon)?.polygon;
    const color = polygon?.material?.getValue(this.viewer.clock.currentTime) as { color?: Color } | undefined;
    return color?.color?.alpha ?? null;
  }
  destroy(): void {
    if (this.roads) this.viewer.scene.groundPrimitives.remove(this.roads);
    if (this.highlight) this.viewer.scene.groundPrimitives.remove(this.highlight);
    this.viewer.scene.primitives.remove(this.nodes);
    for (const entity of this.regionEntities) this.viewer.entities.remove(entity);
    if (this.centroid) this.viewer.entities.remove(this.centroid);
    this.points.clear(); this.regionEntities = []; this.previousData = null;
  }
}
