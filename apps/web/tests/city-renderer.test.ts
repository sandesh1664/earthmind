import assert from "node:assert/strict";
import test from "node:test";
import { CameraSettlement, type CameraPoseSample } from "../components/city/runtime/camera-settlement";
import { destroyWithOwnedContext, destroyWithOwnedInputHandler, ownedCreditStyles, ResourceGeneration } from "../components/city/runtime/lifecycle";
import { flatDegrees, validPosition, positionBounds, extentCenter } from "../lib/geo/coordinates";
import { buildingSelectionId, preferredSelection, publicBuildingProperties, selectionKey } from "../lib/geo/selection";
import { ScreenSpaceEventHandler, ScreenSpaceEventType } from "cesium";
import { CAMERA_PRESETS } from "../lib/geo/camera-presets";

test("renderer adapters preserve longitude then latitude and calculate only degree bounds", () => {
  assert.deepEqual(flatDegrees([[55.27,25.192],[55.274,25.192]]),[55.27,25.192,55.274,25.192]);
  assert.deepEqual(positionBounds([[55.27,25.192],[55.274,25.198]]),[55.27,25.192,55.274,25.198]);
  const center = extentCenter([55.27,25.19,55.28,25.20]);
  assert.ok(Math.abs(center[0]-55.275)<1e-10);
  assert.ok(Math.abs(center[1]-25.195)<1e-10);
});
test("renderer adapters reject unsupported dimensionality and invalid geographic positions", () => {
  for (const position of [[180.1,0],[0,90.1],[55,25,2],[Infinity,25],[NaN,25],[]]) assert.equal(validPosition(position),false);
  assert.throws(() => flatDegrees([[55,25]]));
  assert.throws(() => flatDegrees([[55,25],[55,91]]));
  assert.throws(() => positionBounds([]));
});
test("pick priority is deterministic for overlapping intersections, roads and buildings", () => {
  const building = {kind:"building" as const,id:"b",properties:{name:"Actual provider name"}};
  const road = {kind:"road" as const,id:"r"};
  const node = {kind:"intersection" as const,id:"n"};
  assert.deepEqual(preferredSelection([building,road,node]),node);
  assert.deepEqual(preferredSelection([building,road]),road);
  assert.deepEqual(preferredSelection([null,building]),building);
  assert.equal(preferredSelection([null]),null);
  assert.equal(selectionKey(road),"road:r");
  assert.equal(selectionKey(null),null);
});
test("building metadata copies only actual bounded primitive values and excludes credential keys", () => {
  const metadata: Record<string,unknown> = {name:"Provider building",height:24,unknown:null,nested:{name:"fake"},token:"private",infinite:Infinity,html:"<script>doNotRenderHTML()</script>"};
  const properties = publicBuildingProperties(Object.keys(metadata),key => metadata[key]);
  assert.deepEqual(properties,{name:"Provider building",height:24,html:"<script>doNotRenderHTML()</script>"});
  assert.equal("token" in properties,false);
  assert.equal("unknown" in properties,false);
});
test("async native resources cannot be adopted after a toggle or disposal", async () => {
  const lifetime = new ResourceGeneration();
  const first = lifetime.next();
  let resolve: (() => void) | undefined;
  const pending = new Promise<void>(done => {resolve=done;});
  const adopted: number[] = [];
  const attempt = pending.then(() => {if (lifetime.current(first)) adopted.push(first);});
  const second = lifetime.next();
  resolve!(); await attempt;
  assert.deepEqual(adopted,[]);
  assert.equal(lifetime.current(second),true);
  lifetime.dispose();
  assert.equal(lifetime.current(second),false);
  assert.equal(lifetime.current(lifetime.next()),false);
});
test("strict-mode cleanup prevents stale import initialization while allowing a fresh mount", () => {
  const firstMount = new ResourceGeneration();
  const firstImport=firstMount.next(); firstMount.dispose();
  const nextMount=new ResourceGeneration(); const nextImport=nextMount.next();
  assert.equal(firstMount.current(firstImport),false);
  assert.equal(nextMount.current(nextImport),true);
});
test("Dubai reference presets are geographic cameras rather than study boundaries", () => {
  assert.equal(CAMERA_PRESETS.downtown.longitude,55.2744);
  assert.equal(CAMERA_PRESETS.downtown.latitude,25.1972);
  assert.ok(CAMERA_PRESETS.dubai.height > CAMERA_PRESETS.downtown.height);
  assert.ok(Object.values(CAMERA_PRESETS).every(p => p.height>0 && p.pitch<0 && p.pitch>=-90));
});


test("building identifiers preserve OSM element namespaces and opaque local fallbacks", () => {
  assert.equal(buildingSelectionId({elementType:"node",elementId:42},"fallback"),"node:42");
  assert.equal(buildingSelectionId({elementType:"way",elementId:42},"fallback"),"way:42");
  assert.equal(buildingSelectionId({osm_type:"relation",osm_id:42},"fallback"),"relation:42");
  assert.notEqual(buildingSelectionId({elementType:"node",elementId:42},"fallback"),buildingSelectionId({elementType:"way",elementId:42},"fallback"));
  assert.equal(buildingSelectionId({elementId:42},"local-viewer:1:content:2:feature:42"),"local-viewer:1:content:2:feature:42");
  assert.notEqual(buildingSelectionId({},"local-viewer:1:content:1:feature:0"),buildingSelectionId({},"local-viewer:1:content:2:feature:0"));
});


function pose(x=0,direction=0,width=800):CameraPoseSample {
  return {position:[x,0,6_378_137],direction:[direction,0,-1],up:[0,1,0],viewport:[width,600]};
}
test("camera settlement requires measured stability rather than a fixed flight timeout", () => {
  const monitor=new CameraSettlement();
  assert.deepEqual(monitor.observe(pose(),0),{moving:false,settledNow:false});
  assert.deepEqual(monitor.observe(pose(1),100),{moving:true,settledNow:false});
  assert.deepEqual(monitor.observe(pose(2),400),{moving:true,settledNow:false});
  assert.deepEqual(monitor.observe(pose(3),700),{moving:true,settledNow:false});
  assert.deepEqual(monitor.observe(pose(3),1049),{moving:true,settledNow:false});
  assert.deepEqual(monitor.observe(pose(3),1050),{moving:false,settledNow:true});
  assert.deepEqual(monitor.observe(pose(3),2000),{moving:false,settledNow:false});
});
test("camera settlement tolerates subdisplay numeric jitter while accumulating physical movement", () => {
  const monitor=new CameraSettlement(); monitor.observe(pose(),0);
  monitor.observe(pose(1),100);
  assert.equal(monitor.observe(pose(1.000001,1e-12),450).settledNow,true);
  assert.equal(monitor.observe(pose(1.02),500).moving,false);
  assert.equal(monitor.observe(pose(1.04),600).moving,false);
  assert.equal(monitor.observe(pose(1.06),700).moving,true);
});
test("camera rotations and viewport changes are observed even without a position change", () => {
  const monitor=new CameraSettlement(); monitor.observe(pose(),0);
  assert.equal(monitor.observe(pose(0,0.0001),50).moving,true);
  assert.equal(monitor.observe(pose(0,0.0001),400).settledNow,true);
  assert.equal(monitor.observe(pose(0,0.0001,900),500).moving,true);
});


test("owned WebGL disposal destroys native resources before releasing the canvas context", () => {
  const order:string[]=[];
  destroyWithOwnedContext(() => order.push("destroy-sdk"),{
    isContextLost:() => false,
    getExtension:(name) => {assert.equal(name,"WEBGL_lose_context");return {loseContext:() => order.push("release-context")};},
  });
  assert.deepEqual(order,["destroy-sdk","release-context"]);
});
test("owned WebGL disposal tolerates missing extensions and already-lost contexts", () => {
  let destroyed=0;
  destroyWithOwnedContext(() => {destroyed++;},null);
  destroyWithOwnedContext(() => {destroyed++;},{isContextLost:() => false,getExtension:() => null});
  destroyWithOwnedContext(() => {destroyed++;},{isContextLost:() => true,getExtension:() => {throw new Error("must not access a lost context");}});
  assert.equal(destroyed,3);
});


test("actual Cesium input-handler destruction removes retained DOM listeners before viewer disposal", () => {
  class TrackedTarget extends EventTarget {
    active=new Set<EventListenerOrEventListenerObject>();
    override addEventListener(type:string,callback:EventListenerOrEventListenerObject | null,options?:AddEventListenerOptions | boolean):void {
      super.addEventListener(type,callback,options); if (callback) this.active.add(callback);
    }
    override removeEventListener(type:string,callback:EventListenerOrEventListenerObject | null,options?:EventListenerOptions | boolean):void {
      super.removeEventListener(type,callback,options); if (callback) this.active.delete(callback);
    }
  }
  const documentTarget=new TrackedTarget(),canvas=new TrackedTarget();
  const original=Object.getOwnPropertyDescriptor(globalThis,"document");
  Object.defineProperty(globalThis,"document",{value:documentTarget,configurable:true});
  try {
    const handler=new ScreenSpaceEventHandler(canvas as unknown as HTMLCanvasElement);
    const registered=canvas.active.size+documentTarget.active.size;
    assert.ok(registered>0,"actual SDK must register listeners for this regression");
    handler.setInputAction(() => undefined,ScreenSpaceEventType.LEFT_CLICK);
    handler.removeInputAction(ScreenSpaceEventType.LEFT_CLICK);
    assert.equal(canvas.active.size+documentTarget.active.size,registered,"removing actions alone retains SDK listeners");
    let viewerDisposed=false;
    destroyWithOwnedInputHandler(handler,() => {
      assert.equal(handler.isDestroyed(),true);
      assert.equal(canvas.active.size+documentTarget.active.size,0);
      viewerDisposed=true;
    });
    assert.equal(viewerDisposed,true);
    assert.doesNotThrow(() => destroyWithOwnedInputHandler(handler,() => undefined));
  } finally {
    if (original) Object.defineProperty(globalThis,"document",original);
    else Reflect.deleteProperty(globalThis,"document");
  }
});


test("credit style ownership excludes shared and unrelated CSS", () => {
  const removed:string[]=[];
  const existing={textContent:".cesium-credit-lightbox {color:white}",remove:() => removed.push("shared")};
  const own={textContent:".cesium-credit-lightbox {color:white}",remove:() => removed.push("owned")};
  const unrelated={textContent:".application-panel {color:white}",remove:() => removed.push("unrelated")};
  const owned=ownedCreditStyles(new Set([existing]),[existing,own,unrelated]);
  owned.forEach(style => style.remove());
  assert.deepEqual(owned,[own]);
  assert.deepEqual(removed,["owned"]);
});
