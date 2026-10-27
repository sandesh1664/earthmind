import { z } from "zod";
import { PositionSchema } from "../../../lib/geospatial";
import { Cartesian3, Cartographic, JulianDate, Color, ColorMaterialProperty, ConstantProperty, Credit, DistanceDisplayCondition, GeoJsonDataSource, HeightReference, LabelGraphics, LabelStyle, NearFarScalar, type Viewer } from "cesium";

const ring = z.array(PositionSchema).min(4).max(5000).refine(points => {
  const first=points[0],last=points.at(-1);return first!==undefined&&last!==undefined&&first[0]===last[0]&&first[1]===last[1];
});
const geometry = z.discriminatedUnion("type",[
 z.object({type:z.literal("Point"),coordinates:PositionSchema}),
 z.object({type:z.literal("LineString"),coordinates:z.array(PositionSchema).min(2).max(5000)}),
 z.object({type:z.literal("MultiLineString"),coordinates:z.array(z.array(PositionSchema).min(2).max(5000)).max(100)}),
 z.object({type:z.literal("Polygon"),coordinates:z.array(ring).min(1).max(128)}),
 z.object({type:z.literal("MultiPolygon"),coordinates:z.array(z.array(ring).min(1).max(128)).max(128)}),
]);
export const OSMContextSchema=z.object({type:z.literal("FeatureCollection"),features:z.array(z.object({
 type:z.literal("Feature"),id:z.string().max(64),geometry,
 properties:z.object({context_kind:z.enum(["building","water","park","road","label"]),elementType:z.literal("way"),elementId:z.string().regex(/^\d+$/).max(24),source:z.literal("OpenStreetMap"),is_synthetic:z.literal(false),name:z.string().max(255).optional(),highway:z.string().max(128).optional(),height:z.number().finite().min(1).max(1000).optional(),height_source:z.string().max(128).optional(),osm_height:z.string().max(128).optional()}).strip()
}).strip()).max(12000)}).strip().refine(data => {
 let positions=0;
 const count=(value:unknown):void=>{if(!Array.isArray(value))return;if(typeof value[0]==="number")positions++;else value.forEach(count);};
 data.features.forEach(feature=>count(feature.geometry.coordinates));return positions<=150000;
},"OSM context exceeds coordinate budget");

/** Self-hosted cartography from retained OSM source, without public raster-tile traffic. */
export async function loadOSMContext(buildings: boolean, signal:AbortSignal): Promise<GeoJsonDataSource> {
  const response = await fetch(`/geography/${buildings ? "buildings" : "context"}.geojson`, {signal:AbortSignal.any([signal,AbortSignal.timeout(15000)])});
  if (!response.ok) throw new Error("Local OSM context is absent. Run the real OSM import and context build workflow.");
  const reader=response.body?.getReader();
  if(!reader) throw new Error("Empty OSM context response");
  let bytes=0,text="";const decoder=new TextDecoder();
  try {while(true){signal.throwIfAborted();const next=await reader.read();if(next.done)break;bytes+=next.value.byteLength;if(bytes>12*1024*1024){await reader.cancel();throw new Error("Local OSM context exceeds rendering budget");}text+=decoder.decode(next.value,{stream:true});}text+=decoder.decode();}finally{reader.releaseLock();}
  signal.throwIfAborted();
  const manifestResponse=await fetch("/geography/manifest.json",{signal});
  if(!manifestResponse.ok)throw new Error("Local OSM source manifest is unavailable");
  const manifestText=await manifestResponse.text();
  if(manifestText.length>65536)throw new Error("Invalid context manifest size");
  const manifest=z.object({source:z.literal("OpenStreetMap"),source_sha256:z.string().regex(/^[a-f0-9]{64}$/),artifacts:z.record(z.string(),z.object({sha256:z.string().regex(/^[a-f0-9]{64}$/),bytes:z.number().int().nonnegative()}))}).parse(JSON.parse(manifestText));
  const artifact=manifest.artifacts[buildings?"buildings.geojson":"context.geojson"];
  const encoded=new TextEncoder().encode(text);
  const hash=[...new Uint8Array(await crypto.subtle.digest("SHA-256",encoded))].map(byte=>byte.toString(16).padStart(2,"0")).join("");
  if(!artifact||artifact.sha256!==hash||artifact.bytes!==bytes)throw new Error("Local OSM artifact checksum differs from its source manifest");
  const data=OSMContextSchema.parse(JSON.parse(text));
  const source = await GeoJsonDataSource.load(data, {clampToGround:false, describe:()=>"", credit:new Credit('© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a> · ODbL',true), markerSize:1, markerColor:Color.TRANSPARENT});
  let validBuildings = 0;
  for (const entity of source.entities.values) {
    const properties = entity.properties?.getValue() as Record<string, unknown> | undefined;
    const kind = properties?.context_kind;
    if (entity.polygon) {
      const polygon = entity.polygon;
      if (buildings) {
        const height = properties?.height;
        if (kind !== "building" || typeof height !== "number" || !Number.isFinite(height) || height < 1 || height > 1000) {entity.show=false;continue;}
        polygon.height = new ConstantProperty(0);
        polygon.heightReference = new ConstantProperty(HeightReference.NONE);
        polygon.extrudedHeight = new ConstantProperty(height);
        polygon.extrudedHeightReference = new ConstantProperty(HeightReference.NONE);
        polygon.material = new ColorMaterialProperty(Color.fromCssColorString(height>300 ? "#95bdd1" : "#6b94a8"));
        polygon.outline = new ConstantProperty(false);
        validBuildings++;
      } else {
        // Display-only offset prevents z-fighting on the intentionally ellipsoid-only local map.
        polygon.height=new ConstantProperty(0.2);
        polygon.heightReference=new ConstantProperty(HeightReference.NONE);
        polygon.material = new ColorMaterialProperty(Color.fromCssColorString(kind === "water" ? "#134d67" : kind === "park" ? "#294f43" : "#34485b"));
        polygon.outline = new ConstantProperty(false);
      }
    }
    if (entity.polyline) {
      const roadClass = properties?.highway;
      entity.polyline.width = new ConstantProperty(["motorway","trunk","primary"].includes(String(roadClass)) ? 4 : 2);
      entity.polyline.material = new ColorMaterialProperty(Color.fromCssColorString(["motorway","trunk","primary"].includes(String(roadClass)) ? "#a3a497" : "#667b87"));
      entity.polyline.clampToGround = new ConstantProperty(false);
      const positions=entity.polyline.positions?.getValue(JulianDate.now()) as Cartesian3[] | undefined;
      if(positions) entity.polyline.positions=new ConstantProperty(positions.map(position=>{
        const point=Cartographic.fromCartesian(position);
        return Cartesian3.fromRadians(point.longitude,point.latitude,0.35);
      }));
    }
    if (kind === "label" && typeof properties?.name === "string") {
      entity.billboard = undefined;
      entity.label = new LabelGraphics({text:properties.name,font:"12px sans-serif",fillColor:Color.fromCssColorString("#e3e9ea"),outlineColor:Color.fromCssColorString("#0b1823"),outlineWidth:3,style:LabelStyle.FILL_AND_OUTLINE,showBackground:false,distanceDisplayCondition:new DistanceDisplayCondition(0,9000),scaleByDistance:new NearFarScalar(500,1,9000,0.65),disableDepthTestDistance:0});

    }
  }
  if (buildings && validBuildings === 0) throw new Error("The extract has no explicit numeric OSM height tags; building heights will not be invented.");
  return source;
}

export function removeOSMContext(viewer: Viewer, source: GeoJsonDataSource | null): void {
  if (source && !viewer.isDestroyed()) viewer.dataSources.remove(source,true);
}
