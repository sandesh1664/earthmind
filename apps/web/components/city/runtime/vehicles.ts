import {BillboardCollection,Cartesian3,Cartographic,Color,EllipsoidTerrainProvider,HeadingPitchRange,BoundingSphere,NearFarScalar,PointPrimitiveCollection,SceneTransforms,type Billboard,type PointPrimitive,type Viewer} from "cesium";
import type {ReplaySceneState,ReplayVehicle} from "../../../lib/replay";

type Marker={billboard:Billboard;point:PointPrimitive;sample:ReplayVehicle};
export class VehicleReplayLayer{
 private readonly billboards:BillboardCollection;
 private readonly points:PointPrimitiveCollection;
 private readonly markers=new Map<string,Marker>();
 private state:ReplaySceneState|null=null;
 private followedId:string|null=null;
 private followedPosition:Cartesian3|null=null;
 private hasRendered=false;
 private lastFar=false;
 private lastTerrain:unknown=null;
 private terrainDirty=false;
 private lastPending=0;
 private readonly removeTerrain:()=>void;
 constructor(private readonly viewer:Viewer){this.billboards=viewer.scene.primitives.add(new BillboardCollection({scene:viewer.scene})) as BillboardCollection;this.points=viewer.scene.primitives.add(new PointPrimitiveCollection()) as PointPrimitiveCollection;this.removeTerrain=viewer.scene.globe.tileLoadProgressEvent.addEventListener((pending:number)=>{const refresh=this.lastPending>0&&pending===0;this.lastPending=pending;if(refresh&&this.state){this.terrainDirty=true;this.update(this.state);}});}
 update(state:ReplaySceneState|null):void{
  const far=this.viewer.camera.positionCartographic.height>8000;
  if(!state&&!this.state&&!this.markers.size)return;
  if(state&&this.state&&state.vehicles===this.state.vehicles&&state.time===this.state.time&&state.selectedId===this.state.selectedId&&state.follow===this.state.follow&&far===this.lastFar&&this.lastTerrain===this.viewer.terrainProvider&&!this.terrainDirty)return;
  this.hasRendered=false;this.state=state;const samples=state?.vehicles??[];const current=new Set(samples.map(sample=>sample.id));
  for(const [id,marker] of this.markers)if(!current.has(id)){this.billboards.remove(marker.billboard);this.points.remove(marker.point);this.markers.delete(id);}
  for(const sample of samples){let marker=this.markers.get(sample.id);const selected=state?.selectedId===sample.id;const identity={kind:"simulation-vehicle",id:sample.id};
   if(!marker){marker={sample,billboard:this.billboards.add({id:identity,position:new Cartesian3(),image:"/vehicles/passenger.svg",width:14,height:24,scaleByDistance:new NearFarScalar(200,1.1,15000,0.35),disableDepthTestDistance:0}),point:this.points.add({id:identity,pixelSize:4,outlineWidth:1,outlineColor:Color.fromCssColorString("#12222b")})};this.markers.set(sample.id,marker);}
   marker.sample=sample;const ground=this.viewer.terrainProvider instanceof EllipsoidTerrainProvider?0:this.viewer.scene.globe.getHeight(Cartographic.fromDegrees(sample.longitude,sample.latitude))??0;
   // Display-only glyph offset, not a recorded/surveyed vehicle elevation.
   const position=Cartesian3.fromDegrees(sample.longitude,sample.latitude,ground+1.2);marker.billboard.position=position;marker.point.position=position;
   marker.billboard.color=selected?Color.WHITE:Color.fromCssColorString("#77ece2");marker.billboard.width=selected?19:14;marker.billboard.height=selected?31:24;marker.point.color=selected?Color.WHITE:Color.fromCssColorString("#77ece2");marker.point.pixelSize=selected?8:4;
   const radians=sample.heading*Math.PI/180;const ahead=Cartesian3.fromDegrees(sample.longitude+Math.sin(radians)*0.00002/Math.cos(sample.latitude*Math.PI/180),sample.latitude+Math.cos(radians)*0.00002,ground+1.2);
   marker.billboard.alignedAxis=Cartesian3.normalize(Cartesian3.subtract(ahead,position,new Cartesian3()),new Cartesian3());
  }
  this.lastFar=far;this.lastTerrain=this.viewer.terrainProvider;this.terrainDirty=false;this.points.show=far;this.billboards.show=!far;
  const target=state?.follow&&state.selectedId?this.markers.get(state.selectedId):undefined;
  if(target){const position=target.point.position;if(this.followedId!==state!.selectedId){this.viewer.camera.flyToBoundingSphere(new BoundingSphere(position,0),{duration:0,offset:new HeadingPitchRange(this.viewer.camera.heading,-Math.PI/3,160)});}
   else if(this.followedPosition){const difference=Cartesian3.subtract(position,this.followedPosition,new Cartesian3());this.viewer.camera.setView({destination:Cartesian3.add(this.viewer.camera.positionWC,difference,new Cartesian3()),orientation:{direction:this.viewer.camera.directionWC,up:this.viewer.camera.upWC}});}
   this.followedId=state!.selectedId;this.followedPosition=Cartesian3.clone(position);
  }else{this.followedId=null;this.followedPosition=null;}
  this.viewer.scene.requestRender();
 }
 selectFromPicks(values:readonly unknown[]):string|null{
  for(const value of values){if(typeof value!=="object"||value===null||!("id" in value))continue;const id=value.id;if(typeof id==="object"&&id!==null&&"kind" in id&&id.kind==="simulation-vehicle"&&"id" in id&&typeof id.id==="string"&&this.markers.has(id.id))return id.id;}return null;
 }
 select(id:string):void{if(this.markers.has(id))this.state?.onSelect(id);}
 count():number{return this.markers.size;}
 rendered():void{this.hasRendered=true;}
 readyCount():number{return this.hasRendered?(this.points.show?this.markers.size:[...this.markers.values()].filter(marker=>marker.billboard.ready).length):0;}
 inViewCount():number{let count=0;for(const marker of this.markers.values()){const point=SceneTransforms.worldToWindowCoordinates(this.viewer.scene,marker.point.position);if(point&&point.x>=0&&point.y>=0&&point.x<=this.viewer.canvas.clientWidth&&point.y<=this.viewer.canvas.clientHeight)count++;}return count;}
 probe():{id:string;x:number;y:number;longitude:number;latitude:number;time:number}|null{
  const preferred=this.state?.selectedId?this.markers.get(this.state.selectedId):undefined;
  for(const marker of preferred?[preferred,...this.markers.values()]:this.markers.values()){
   const point=SceneTransforms.worldToWindowCoordinates(this.viewer.scene,marker.point.position);const canvas=this.viewer.canvas,bounds=canvas.getBoundingClientRect();
   if(!point||point.x<10||point.y<10||point.x>canvas.clientWidth-10||point.y>canvas.clientHeight-10||document.elementFromPoint(bounds.left+point.x,bounds.top+point.y)!==canvas)continue;
   return {id:marker.sample.id,x:point.x,y:point.y,longitude:marker.sample.longitude,latitude:marker.sample.latitude,time:this.state?.time??0};
  }return null;
 }
 destroy():void{this.removeTerrain();this.markers.clear();this.viewer.scene.primitives.remove(this.billboards);this.viewer.scene.primitives.remove(this.points);this.state=null;this.followedPosition=null;}
}
