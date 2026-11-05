import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import test from "node:test";
import {z} from "zod";
import {REPLAY_LIMITS,ReplayChunkSchema,ReplayManifestSchema,boundedReplayVehicles,interpolateReplay,readReplayJSON,replayChunkIndex,replayEvents,replayFrames,type ReplayChunk,type ReplayEvent,type ReplayFrame,type ReplayManifest,type ReplayVehicle} from "../lib/replay";

// Small synthetic unit fixtures only: never evidence of a native SUMO execution.
const runId="11111111-1111-4111-8111-111111111111",networkId="22222222-2222-4222-8222-222222222222";
function vehicle(id="unit-car",values:Partial<ReplayVehicle>={}):ReplayVehicle{return {id,longitude:10,latitude:20,heading:350,speed:5,vehicle_class:"passenger",segment_id:0,...values};}
function frame(time:number,vehicles:ReplayVehicle[]):ReplayFrame{return {time,vehicles,departed:[],arrived:[],teleported:[]};}
function chunk(frames:ReplayFrame[],events:ReplayEvent[]=[],id="000000"):ReplayChunk{return {schema_version:1,run_id:runId,chunk_id:id,frames,events};}
function manifest():ReplayManifest{return {schema_version:1,run_id:runId,network_version_id:networkId,duration_seconds:4,sample_interval_seconds:2,vehicle_class:"passenger",synthetic:true,coordinate_reference_system:"EPSG:4326",chunks:[{id:"000000",start_time:0,end_time:2,sample_count:2,sha256:"a".repeat(64),size_bytes:100},{id:"000001",start_time:2,end_time:4,sample_count:2,sha256:"b".repeat(64),size_bytes:100}],counts:[{time:0,active:1,departed:1,arrived:0},{time:2,active:1,departed:1,arrived:0},{time:4,active:0,departed:1,arrived:1}]};}
const signal=()=>new AbortController().signal;
const fetchResponse=(response:()=>Response):typeof fetch=>async()=>response();

test("replay uses a real bracketing pair and never extrapolates before, after or over a missing interval",()=>{
 const frames=[frame(2,[vehicle()]),frame(4,[vehicle("unit-car",{longitude:12})])];
 assert.deepEqual(interpolateReplay(frames,[],1,2),[]);
 assert.deepEqual(interpolateReplay(frames,[],5,2),[]);
 assert.deepEqual(interpolateReplay(frames,[],3,1),[]);
 assert.deepEqual(interpolateReplay([],[],3,2),[]);
 assert.equal(interpolateReplay(frames,[],2,2)[0]?.longitude,10);
 assert.equal(interpolateReplay(frames,[],4,2)[0]?.longitude,12);
});

test("same-segment interpolation preserves identifier/class and takes the shortest heading path",()=>{
 const a=vehicle(),b=vehicle("unit-car",{longitude:12,latitude:24,heading:10,speed:9});
 const midpoint=interpolateReplay([frame(0,[a]),frame(2,[b])],[],1,2)[0]!;
 assert.deepEqual(midpoint,{...a,longitude:11,latitude:22,heading:0,speed:7});
 assert.equal(a.longitude,10);assert.equal(b.longitude,12);
 const reverse=interpolateReplay([frame(0,[vehicle("unit-car",{heading:10})]),frame(2,[vehicle("unit-car",{heading:350})])],[],1,2)[0]!;
 assert.equal(reverse.heading,0);
});

test("exact arrival events remove a marker at its lifecycle end without inventing a final position",()=>{
 const frames=[frame(0,[vehicle()]),frame(2,[])],events:ReplayEvent[]=[{id:"unit-car",time:1,type:"arrived"}];
 assert.deepEqual(interpolateReplay(frames,events,0.5,2),[vehicle()]);
 assert.deepEqual(interpolateReplay(frames,events,1,2),[]);
 assert.deepEqual(interpolateReplay(frames,events,1.9,2),[]);
 assert.deepEqual(interpolateReplay(frames,events,2,2),[]);
});

test("new appearances, missing samples, segment changes and teleports cannot be joined into an invented journey",()=>{
 const a=vehicle(),b=vehicle("unit-car",{longitude:40,segment_id:1});
 assert.deepEqual(interpolateReplay([frame(0,[]),frame(2,[a])],[],1,2),[]);
 assert.deepEqual(interpolateReplay([frame(0,[a]),frame(2,[])],[],1,2),[]);
 assert.deepEqual(interpolateReplay([frame(0,[a]),frame(2,[b])],[],1,2),[]);
 const events:ReplayEvent[]=[{id:a.id,time:0.5,type:"teleport_start"},{id:a.id,time:1.5,type:"teleport_end"}];
 const frames=[frame(0,[a]),frame(2,[b])];
 assert.deepEqual(interpolateReplay(frames,events,0.25,2),[a]);
 assert.deepEqual(interpolateReplay(frames,events,0.5,2),[]);
 assert.deepEqual(interpolateReplay(frames,events,1.7,2),[]);
 assert.deepEqual(interpolateReplay(frames,events,2,2),[b]);
});

test("bounded replay rejects duplicate IDs, unordered frames, invalid geography and unexpected sample fields",()=>{
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(0,[vehicle()]),frame(2,[vehicle()])])).success,true);
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(0,[vehicle(),vehicle()])])).success,false);
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(2,[vehicle()]),frame(2,[vehicle()])])).success,false);
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(2,[vehicle()]),frame(1,[vehicle()])])).success,false);
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(0,[vehicle("unit-car",{longitude:181})])])).success,false);
 assert.equal(ReplayChunkSchema.safeParse(chunk([frame(0,[vehicle("unit-car",{latitude:Number.NaN})])])).success,false);
 assert.equal(ReplayChunkSchema.safeParse({...chunk([frame(0,[vehicle()])]),private_uri:"unit-not-a-real-uri"}).success,false);
});

test("manifest bounds, IDs, units and recorded count order are validated before chunk selection",()=>{
 const valid=manifest();assert.equal(ReplayManifestSchema.safeParse(valid).success,true);
 assert.equal(ReplayManifestSchema.safeParse({...valid,duration_seconds:0}).success,false);
 assert.equal(ReplayManifestSchema.safeParse({...valid,sample_interval_seconds:1.5}).success,false);
 assert.equal(ReplayManifestSchema.safeParse({...valid,coordinate_reference_system:"EPSG:3857"}).success,false);
 assert.equal(ReplayManifestSchema.safeParse({...valid,chunks:[valid.chunks[0],valid.chunks[0]]}).success,false);
 assert.equal(ReplayManifestSchema.safeParse({...valid,chunks:[{...valid.chunks[0],end_time:5}]}).success,false);
 assert.equal(ReplayManifestSchema.safeParse({...valid,counts:[valid.counts[1],valid.counts[0]]}).success,false);
 assert.equal(replayChunkIndex(valid,0),0);assert.equal(replayChunkIndex(valid,3),1);assert.equal(replayChunkIndex(valid,100),1);
});

test("overlapping identical chunk endpoints and exact events are deduplicated without altering source frames",()=>{
 const shared=frame(2,[vehicle()]);const event:ReplayEvent={id:"unit-car",time:2,type:"departed"};
 const a=chunk([frame(0,[]),shared],[event]),b=chunk([shared,frame(4,[vehicle()])],[event],"000001");
 assert.deepEqual(replayFrames([b,a]).map(item=>item.time),[0,2,4]);
 assert.deepEqual(replayEvents([b,a]),[event]);assert.equal(a.frames.length,2);assert.equal(b.frames.length,2);
});

test("the explicit thousand-marker budget retains the selected recorded vehicle without mutating the recording",()=>{
 const all=Array.from({length:REPLAY_LIMITS.visibleVehicles+5},(_,index)=>vehicle(`unit-${index}`));
 const selected=all.at(-1)!;const bounded=boundedReplayVehicles(all,selected.id);
 assert.equal(bounded.length,1_000);assert.equal(new Set(bounded.map(item=>item.id)).size,1_000);assert.equal(bounded.at(-1)?.id,selected.id);
 assert.equal(all.length,1_005);assert.equal(all[999]?.id,"unit-999");
 assert.equal(boundedReplayVehicles(all,"unit-absent").length,1_000);
 const subset=all.slice(0,2),small=boundedReplayVehicles(subset,null);assert.equal(small.length,2);assert.notEqual(small,subset);small.pop();assert.equal(subset.length,2);
});

test("streamed replay verification hashes the exact bytes and rejects corrupted or malformed artifacts",async()=>{
 const value=chunk([frame(0,[vehicle()]),frame(2,[vehicle("unit-car",{longitude:11})])]);
 const body=JSON.stringify(value,null,2)+"\n";const digest=createHash("sha256").update(body).digest("hex");
 const parsed=await readReplayJSON("/unit-replay",ReplayChunkSchema,signal(),REPLAY_LIMITS.chunkBytes,digest,fetchResponse(()=>new Response(body)));
 assert.deepEqual(parsed,value);
 await assert.rejects(()=>readReplayJSON("/unit-replay",ReplayChunkSchema,signal(),REPLAY_LIMITS.chunkBytes,"0".repeat(64),fetchResponse(()=>new Response(body))),/checksum verification failed/);
 await assert.rejects(()=>readReplayJSON("/unit-replay",ReplayChunkSchema,signal(),1_024,undefined,fetchResponse(()=>new Response("not JSON"))),/valid UTF-8 JSON/);
 await assert.rejects(()=>readReplayJSON("/unit-replay",ReplayChunkSchema,signal(),1_024,undefined,fetchResponse(()=>Response.json({wrong:"unit fixture"}))),/bounded trajectory contract/);
 await assert.rejects(()=>readReplayJSON("/unit-replay",ReplayChunkSchema,signal(),1_024,undefined,fetchResponse(()=>new Response(new Uint8Array([0xff,0xfe])))),/valid UTF-8 JSON/);
});

test("both declared and streaming replay byte budgets stop and cancel rejected downloads",async()=>{
 let declaredCancelled=false;
 const declared=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new Uint8Array([1]));},cancel(){declaredCancelled=true;}});
 await assert.rejects(()=>readReplayJSON("/unit-replay",z.unknown(),signal(),REPLAY_LIMITS.chunkBytes,undefined,fetchResponse(()=>new Response(declared,{headers:{"Content-Length":String(REPLAY_LIMITS.chunkBytes+1)}}))),/response budget/);
 assert.equal(declaredCancelled,true);
 let streamedCancelled=false;
 const streamed=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new Uint8Array(REPLAY_LIMITS.chunkBytes));controller.enqueue(new Uint8Array([1]));},cancel(){streamedCancelled=true;}});
 await assert.rejects(()=>readReplayJSON("/unit-replay",z.unknown(),signal(),REPLAY_LIMITS.chunkBytes,undefined,fetchResponse(()=>new Response(streamed))),/response budget/);
 assert.equal(streamedCancelled,true);
});

test("unpublished or failed remote replay remains an explicit error rather than an empty successful recording",async()=>{
 await assert.rejects(()=>readReplayJSON("/unit-replay",z.unknown(),signal(),1_024,undefined,fetchResponse(()=>new Response("unit unavailable",{status:409}))),/only after a successful run/);
 await assert.rejects(()=>readReplayJSON("/unit-replay",z.unknown(),signal(),1_024,undefined,fetchResponse(()=>new Response("unit failure",{status:500}))),/HTTP 500/);
});
