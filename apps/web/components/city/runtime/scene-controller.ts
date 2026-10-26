import {
  Cartesian3, Cesium3DTileFeature, Color, EllipsoidTerrainProvider,
  Math as CMath, SceneTransforms, ScreenSpaceEventType, Viewer,
} from "cesium";
import type { CesiumViewerProps, FeatureSelection, ProviderState, ViewerStatus } from "../../../lib/city/types";
import { buildingSelectionId, preferredSelection, publicBuildingProperties } from "../../../lib/geo/selection";
import { applyCamera, cameraSnapshot } from "./camera";
import { CameraSettlement } from "./camera-settlement";
import { GeographicLayers } from "./layers";
import { ProviderLayers } from "./providers";
import { destroyWithOwnedContext, destroyWithOwnedInputHandler, ownedCreditStyles } from "./lifecycle";

const INITIAL: ViewerStatus = {
  phase:"loading", message:"Initializing the geographic renderer",
  cameraMoving:false,
  buildings:{status:"off",message:"Optional buildings disabled"},
  imagery:{status:"off",message:"No imagery enabled"},
  terrain:{status:"off",message:"WGS84 ellipsoid"}, roadCount:0, intersectionCount:0,
};
let viewerNamespaceCounter = 0;
function selectionFromPick(value: unknown, contentIdentity: (content:object,featureId:number) => string): FeatureSelection {
  if (value instanceof Cesium3DTileFeature) {
    const properties = publicBuildingProperties(value.getPropertyIds(),(key) => value.getProperty(key) as unknown);
    return {kind:"building",id:buildingSelectionId(properties,contentIdentity(value,value.featureId)),properties};
  }
  if (typeof value !== "object" || value === null || !("id" in value)) return null;
  const identity = value.id;
  if (typeof identity !== "object" || identity === null || !("kind" in identity) || !("id" in identity)) return null;
  if ((identity.kind === "road" || identity.kind === "intersection") && typeof identity.id === "string") return {kind:identity.kind,id:identity.id};
  return null;
}

/** The only owner of Cesium native scene state. It never escapes into React state. */
export class CitySceneController {
  private viewer: Viewer;
  private layers: GeographicLayers;
  private providers: ProviderLayers;
  private readonly creditStyles: HTMLStyleElement[];
  private disposed = false;
  private props: CesiumViewerProps;
  private status: ViewerStatus = {...INITIAL};
  private removeListeners: (() => void)[] = [];
  private lastStatus = "";
  private readonly viewerNamespace = ++viewerNamespaceCounter;
  private readonly featureNamespaces = new WeakMap<object,number>();
  private nextFeatureNamespace = 0;
  private hasUpdated = false;
  private lastRegion: string | null = null;
  private lastCameraSequence = -1;
  private renderedFrames = 0;
  private sampleFrames = 0;
  private sampleStart = performance.now();
  private sampleFps: number | null = null;
  private heapBytes: number | null = null;
  private readonly cameraSettlement = new CameraSettlement();
  private lastCameraSample = Number.NEGATIVE_INFINITY;
  constructor(container: HTMLElement, props: CesiumViewerProps) {
    this.props = props;
    const existingStyles = new Set(document.querySelectorAll("style"));
    try {
    this.viewer = new Viewer(container, {
      animation:false, timeline:false, baseLayerPicker:false, geocoder:false,
      homeButton:false, sceneModePicker:false, navigationHelpButton:false,
      fullscreenButton:false, vrButton:false, infoBox:false, selectionIndicator:false,
      baseLayer:false, terrainProvider:new EllipsoidTerrainProvider(),
      requestRenderMode:true, maximumRenderTimeChange:Number.POSITIVE_INFINITY,
      shadows:false, skyBox:false, useBrowserRecommendedResolution:true,
      automaticallyTrackDataSourceClocks:false,
    });
    } catch (error) {
      // A failed constructor must not leave its dynamically injected SDK CSS.
      ownedCreditStyles(existingStyles,document.querySelectorAll("style")).forEach((style) => style.remove());
      throw error;
    }
    this.creditStyles = ownedCreditStyles(existingStyles,document.querySelectorAll("style"));
    const viewer = this.viewer;
    viewer.clock.shouldAnimate = false;
    viewer.resolutionScale = Math.min(1, 1.5 / (window.devicePixelRatio || 1));
    viewer.scene.backgroundColor = Color.fromCssColorString("#08131f");
    viewer.scene.globe.baseColor = Color.fromCssColorString("#183648");
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.globe.maximumScreenSpaceError = 3;
    viewer.scene.globe.tileCacheSize = 100;
    viewer.camera.setView({ destination:Cartesian3.fromDegrees(55.2744,25.1972,2400), orientation:{heading:0,pitch:CMath.toRadians(-65),roll:0} });
    this.layers = new GeographicLayers(viewer);
    this.providers = new ProviderLayers(viewer,props.config,(name,state) => this.providerState(name,state));
    viewer.screenSpaceEventHandler.removeInputAction(ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
    viewer.screenSpaceEventHandler.setInputAction((movement: {position: import("cesium").Cartesian2}) => {
      if (this.disposed) return;
      const selections = (viewer.scene.drillPick(movement.position,16) as unknown[]).map((value) => selectionFromPick(value,(content,id) => this.localBuildingIdentity(content,id)));
      this.props.onSelect(preferredSelection(selections));
    },ScreenSpaceEventType.LEFT_CLICK);
    this.removeListeners.push(viewer.camera.moveStart.addEventListener(() => this.observeCamera()));
    this.removeListeners.push(viewer.camera.moveEnd.addEventListener(() => this.observeCamera()));
    // postUpdate also runs when request-render mode skips drawing an idle frame.
    this.removeListeners.push(viewer.scene.postUpdate.addEventListener(() => this.observeCamera()));
    this.removeListeners.push(viewer.scene.renderError.addEventListener(() => {
      if (!this.disposed) { this.status = {...this.status,phase:"error",message:"The WebGL renderer stopped. Reload the viewer or check browser graphics support."}; this.emit(); }
    }));
    this.removeListeners.push(viewer.scene.postRender.addEventListener(() => this.afterRender()));
    const lost = (event: Event) => {
      event.preventDefault();
      if (!this.disposed) { this.status = {...this.status,phase:"webgl-unavailable",message:"The browser lost its graphics context. Reload the viewer to recover."}; this.emit(); }
    };
    viewer.canvas.addEventListener("webglcontextlost",lost);
    this.removeListeners.push(() => viewer.canvas.removeEventListener("webglcontextlost",lost));
    this.status = {...this.status,phase:"ready",message:"Interactive WGS84 globe ready"};
    this.update(props);
    this.props.onCameraChange(cameraSnapshot(viewer));
    this.emit();
  }
  private providerState(name:"buildings"|"imagery"|"terrain",state:ProviderState): void {
    if (this.disposed) return;
    this.status = {...this.status,[name]:state}; this.emit();
  }
  update(props: CesiumViewerProps): void {
    if (this.disposed) return;
    const previous = this.props;
    this.props = props;
    const configChanged = props.config.ionPublicToken !== previous.config.ionPublicToken || props.config.imageryAssetId !== previous.config.imageryAssetId || props.config.terrainAssetId !== previous.config.terrainAssetId;
    if (configChanged) {
      this.providers.destroy();
      this.providers = new ProviderLayers(this.viewer,props.config,(name,state) => this.providerState(name,state));
    }
    if (!this.hasUpdated || props.data.roads !== previous.data.roads || props.data.intersections !== previous.data.intersections || props.data.boundary !== previous.data.boundary || props.data.region !== previous.data.region || props.layers !== previous.layers || props.selection !== previous.selection) {
      this.layers.update(props.data,props.layers,props.selection);
      this.hasUpdated = true;
    }
    this.providers.update(props.layers);
    if (props.data.region && props.data.region.id !== this.lastRegion) {
      this.lastRegion = props.data.region.id;
      applyCamera(this.viewer,{preset:"region",sequence:0},props.data,null);
    }
    if (props.cameraCommand.sequence !== this.lastCameraSequence) {
      this.lastCameraSequence = props.cameraCommand.sequence;
      // A first default command must not override automatic selected-region fit.
      if (props.cameraCommand.sequence > 0) applyCamera(this.viewer,props.cameraCommand,props.data,props.selection);
    }
    this.emit();
  }
  private observeCamera(): void {
    if (this.disposed) return;
    const now = performance.now();
    if (now-this.lastCameraSample < 50) return;
    this.lastCameraSample = now;
    const camera = this.viewer.camera;
    const position=camera.positionWC,direction=camera.directionWC,up=camera.upWC;
    const sample = this.cameraSettlement.observe({
      position:[position.x,position.y,position.z],
      direction:[direction.x,direction.y,direction.z],up:[up.x,up.y,up.z],
      viewport:[this.viewer.canvas.clientWidth,this.viewer.canvas.clientHeight],
    },now);
    if (sample.settledNow) this.props.onCameraChange(cameraSnapshot(this.viewer));
    if (sample.moving !== this.status.cameraMoving) {
      this.status={...this.status,cameraMoving:sample.moving}; this.emit();
    }
  }
  private afterRender(): void {
    if (this.disposed) return;
    this.renderedFrames += 1; this.sampleFrames += 1;
    if (this.layers.pending() && this.status.phase === "ready") this.viewer.scene.requestRender();
    const elapsed = performance.now() - this.sampleStart;
    if (this.props.config.diagnosticsEnabled && elapsed >= 1500) {
      this.sampleFps = this.sampleFrames * 1000 / elapsed;
      const memory = (performance as Performance & {memory?:{usedJSHeapSize:number}}).memory;
      this.heapBytes = memory?.usedJSHeapSize ?? null;
      this.sampleFrames = 0; this.sampleStart = performance.now();
      this.status = {...this.status,renderedFrames:this.renderedFrames,sampleFps:this.sampleFps,heapBytes:this.heapBytes};
    }
    this.emit();
  }
  private emit(): void {
    if (this.disposed) return;
    const snapshot: ViewerStatus = {...this.status,...this.layers.counts(),geometryReady:!this.layers.pending(),layerVisibility:{...this.layers.visibilitySnapshot(),...this.providers.visibilitySnapshot()}};
    if (this.props.config.diagnosticsEnabled) {
      // No native object is exposed: this optional local diagnostic is only a
      // projection of a real stored road coordinate into the actual canvas.
      snapshot.pickProbe = this.roadPickProbe();
    }
    const signature = JSON.stringify(snapshot);
    if (signature !== this.lastStatus) { this.lastStatus = signature; this.props.onStatus(snapshot); }
  }
  private localBuildingIdentity(feature:object,featureId:number): string {
    let namespace = this.featureNamespaces.get(feature);
    if (namespace === undefined) {
      namespace = ++this.nextFeatureNamespace;
      this.featureNamespaces.set(feature,namespace);
    }
    // Native picked features stay in this WeakMap, never in React state or URL-derived keys.
    return `local-viewer:${this.viewerNamespace}:object:${namespace}:feature:${featureId}`;
  }
  private roadPickProbe(): NonNullable<ViewerStatus["pickProbe"]> | null {
    const road = this.props.data.roads[0];
    const a = road?.geometry.coordinates[0], b = road?.geometry.coordinates[1];
    if (!road || !a || !b || !this.props.layers.roads || this.layers.pending()) return null;
    const point = SceneTransforms.worldToWindowCoordinates(this.viewer.scene,Cartesian3.fromDegrees((a[0]+b[0])/2,(a[1]+b[1])/2));
    if (!point || point.x < 0 || point.y < 0 || point.x > this.viewer.canvas.clientWidth || point.y > this.viewer.canvas.clientHeight) return null;
    return {kind:"road",id:road.id,x:Math.round(point.x*100)/100,y:Math.round(point.y*100)/100};
  }
  destroy(): void {
    if (this.disposed) return;
    this.disposed = true;
    const canvas = this.viewer.canvas;
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    this.viewer.camera.cancelFlight();
    this.removeListeners.forEach((remove) => remove()); this.removeListeners = [];
    const inputHandler = this.viewer.screenSpaceEventHandler;
    if (!inputHandler.isDestroyed()) inputHandler.removeInputAction(ScreenSpaceEventType.LEFT_CLICK);
    this.providers.destroy(); this.layers.destroy();
    try {
      destroyWithOwnedContext(() => {
        // Cesium 1.146 removes two actions but leaves the widget's input handler
        // alive. Explicitly release its DOM/document listeners via the public API.
        destroyWithOwnedInputHandler(inputHandler,() => {
          if (!this.viewer.isDestroyed()) this.viewer.destroy();
        });
      },context);
    } finally {
      // CreditDisplay appends a per-instance style but its destroy leaves it in
      // document.head. Attribution remains enabled throughout the Viewer lifetime.
      this.creditStyles.forEach((style) => style.remove());
    }
  }
}
