import {
  Cesium3DTileStyle, CesiumTerrainProvider, Color, Credit, EllipsoidTerrainProvider,
  ImageryLayer, Ion, IonImageryProvider, TileMapServiceImageryProvider,
  createOsmBuildingsAsync, type Cesium3DTileset, type Viewer,
} from "cesium";
import type { CityConfig, LayerSettings, ProviderState } from "../../../lib/city/types";
import { ResourceGeneration } from "./lifecycle";

type ProviderName = "buildings" | "imagery" | "terrain";
export class ProviderLayers {
  private generations = { imagery: new ResourceGeneration(), buildings: new ResourceGeneration(), terrain: new ResourceGeneration() };
  private flags: LayerSettings | null = null;
  private imagery: ImageryLayer | null = null;
  private buildings: Cesium3DTileset | null = null;
  private imageryError: (() => void) | null = null;
  private terrainError: (() => void) | null = null;
  private buildingError: (() => void) | null = null;
  private alive = true;
  constructor(private viewer: Viewer, private config: CityConfig, private report: (name: ProviderName,state: ProviderState) => void) {
    // Never use Cesium's bundled evaluation token. This is an intentionally public,
    // developer-scoped visualization token supplied by runtime configuration.
    Ion.defaultAccessToken = config.ionPublicToken ?? "";
  }
  update(flags: LayerSettings): void {
    if (flags.imagery !== this.flags?.imagery) void this.setImagery(flags.imagery);
    if (flags.buildings !== this.flags?.buildings) void this.setBuildings(flags.buildings);
    if (flags.terrain !== this.flags?.terrain) void this.setTerrain(flags.terrain);
    this.flags = flags;
  }
  private async setImagery(enabled: boolean): Promise<void> {
    const generation = this.generations.imagery.next();
    this.imageryError?.(); this.imageryError = null;
    if (this.imagery) this.viewer.imageryLayers.remove(this.imagery,true);
    this.imagery = null;
    if (!enabled) { this.report("imagery",{status:"off",message:"Basemap imagery hidden"}); return; }
    this.report("imagery",{status:"loading",message:"Loading geographic imagery"});
    try {
      const provider = this.config.ionPublicToken
        ? await IonImageryProvider.fromAssetId(this.config.imageryAssetId,{ accessToken: this.config.ionPublicToken })
        : await TileMapServiceImageryProvider.fromUrl("/cesium/Assets/Textures/NaturalEarthII", { credit: new Credit("Made with Natural Earth · public domain", true) });
      if (!this.generations.imagery.current(generation)) return;
      this.imagery = new ImageryLayer(provider);
      this.viewer.imageryLayers.add(this.imagery);
      this.imageryError = provider.errorEvent.addEventListener(() => {
        if (this.alive) this.report("imagery",{status:"error",message:"Imagery tiles could not load; globe and stored overlays remain usable"});
      });
      this.report("imagery",{status:"ready",message:this.config.ionPublicToken ? "Cesium ion imagery · provider attribution retained" : "Natural Earth II · local low-resolution reference imagery"});
      this.viewer.scene.requestRender();
    } catch {
      if (this.generations.imagery.current(generation)) this.report("imagery",{status:"error",message:"Imagery provider unavailable; globe and backend overlays remain usable"});
    }
  }
  private async setBuildings(enabled: boolean): Promise<void> {
    const generation = this.generations.buildings.next();
    this.buildingError?.(); this.buildingError = null;
    if (this.buildings) this.viewer.scene.primitives.remove(this.buildings);
    this.buildings = null;
    if (!this.config.ionPublicToken) {
      this.report("buildings",{status:"blocked",message:"3D buildings require a configured public Cesium ion token with asset access"}); return;
    }
    if (!enabled) { this.report("buildings",{status:"off",message:"Cesium OSM Buildings disabled"}); return; }
    this.report("buildings",{status:"loading",message:"Loading optional Cesium OSM Buildings"});
    try {
      const tileset = await createOsmBuildingsAsync({
        defaultColor: Color.fromCssColorString("#a1c2cb"), enableShowOutline: false,
        style: new Cesium3DTileStyle({color:"color('#a1c2cb',0.94)"}),
      });
      if (!this.generations.buildings.current(generation)) { tileset.destroy(); return; }
      tileset.maximumScreenSpaceError = 24;
      tileset.cacheBytes = 96 * 1024 * 1024;
      tileset.maximumCacheOverflowBytes = 48 * 1024 * 1024;
      this.buildings = this.viewer.scene.primitives.add(tileset) as Cesium3DTileset;
      this.buildingError = tileset.tileFailed.addEventListener(() => {
        if (this.alive) this.report("buildings",{status:"error",message:"Some building tiles failed; coverage and metadata depend on the provider"});
      });
      this.report("buildings",{status:"ready",message:"Cesium OSM Buildings enabled · coverage varies; attribution retained"});
      this.viewer.scene.requestRender();
    } catch {
      if (this.generations.buildings.current(generation)) this.report("buildings",{status:"error",message:"Building provider unavailable or token lacks access; stored geographic layers remain usable"});
    }
  }
  private async setTerrain(enabled: boolean): Promise<void> {
    const generation = this.generations.terrain.next();
    this.terrainError?.(); this.terrainError = null;
    this.viewer.terrainProvider = new EllipsoidTerrainProvider();
    if (!enabled) { this.report("terrain",{status:"off",message:"WGS84 ellipsoid surface"}); return; }
    if (!this.config.ionPublicToken) { this.report("terrain",{status:"blocked",message:"World terrain requires a configured Cesium ion token; using the ellipsoid"}); return; }
    this.report("terrain",{status:"loading",message:"Loading optional Cesium terrain"});
    try {
      const provider = await CesiumTerrainProvider.fromIonAssetId(this.config.terrainAssetId);
      if (!this.generations.terrain.current(generation)) return;
      this.viewer.terrainProvider = provider;
      this.terrainError = provider.errorEvent.addEventListener(() => {
        if (this.alive) this.report("terrain",{status:"error",message:"Terrain tiles failed; disable terrain to return to the ellipsoid"});
      });
      this.report("terrain",{status:"ready",message:"Cesium ion terrain · provider attribution retained"});
      this.viewer.scene.requestRender();
    } catch {
      if (this.generations.terrain.current(generation)) this.report("terrain",{status:"error",message:"Terrain provider unavailable; using the WGS84 ellipsoid"});
    }
  }
  visibilitySnapshot(): {buildings:boolean;imagery:boolean;terrain:boolean} {
    return {buildings:this.buildings?.show ?? false,imagery:this.imagery?.show ?? false,terrain:!(this.viewer.terrainProvider instanceof EllipsoidTerrainProvider)};
  }
  destroy(): void {
    this.alive = false;
    Object.values(this.generations).forEach((generation) => generation.dispose());
    this.imageryError?.(); this.terrainError?.(); this.buildingError?.();
    if (this.imagery) this.viewer.imageryLayers.remove(this.imagery,true);
    if (this.buildings) this.viewer.scene.primitives.remove(this.buildings);
    this.imagery = null; this.buildings = null;
    Ion.defaultAccessToken = "";
  }
}
