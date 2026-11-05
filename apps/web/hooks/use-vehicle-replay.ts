"use client";
import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {boundedReplayVehicles,interpolateReplay,readReplayJSON,replayChunkIndex,replayEvents,replayFrames,REPLAY_LIMITS,ReplayChunkSchema,ReplayManifestSchema,type ReplayChunk,type ReplayManifest} from "../lib/replay";

type Loaded={runId:string;manifest:ReplayManifest};
export function useVehicleReplay(runId:string|null,networkId:string){
 const [loaded,setLoaded]=useState<Loaded|null>(null),[error,setError]=useState<string|null>(null),[snapshot,setSnapshot]=useState<{runId:string;chunks:ReplayChunk[]}|null>(null),[reload,setReload]=useState(0);
 const [time,setTime]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[selectedId,setSelectedId]=useState<string|null>(null),[follow,setFollow]=useState(false);
 const cache=useRef(new Map<string,ReplayChunk>()),pending=useRef(new Map<string,AbortController>()),wanted=useRef(new Set<string>()),timeline=useRef(0),canAdvance=useRef(false);
 const manifest=loaded?.runId===runId?loaded.manifest:null;
 useEffect(()=>{
  const abort=new AbortController(),activePending=pending.current,activeCache=cache.current;cache.current.clear();pending.current.forEach(controller=>controller.abort());pending.current.clear();wanted.current.clear();
  if(runId)void readReplayJSON("/api/simulation/simulations/"+encodeURIComponent(runId)+"/replay/manifest",ReplayManifestSchema,abort.signal,REPLAY_LIMITS.manifestBytes).then(value=>{
   if(abort.signal.aborted)return;if(value.run_id!==runId)throw new Error("Replay manifest does not match the requested run.");
   setLoaded({runId,manifest:value});timeline.current=0;setTime(0);setPlaying(false);setSelectedId(null);setFollow(false);setError(null);
  }).catch((cause:unknown)=>{if(!abort.signal.aborted)setError(cause instanceof Error?cause.message:"Replay could not load.");});
  return ()=>{abort.abort();activePending.forEach(controller=>controller.abort());activePending.clear();activeCache.clear();};
 },[runId,reload]);
 const index=manifest?replayChunkIndex(manifest,time):0;
 useEffect(()=>{
  if(!manifest)return;
  const descriptors=manifest.chunks.slice(Math.max(0,index-1),index+2);
  wanted.current=new Set(descriptors.map(item=>item.id));
  for(const [id,controller] of pending.current)if(!wanted.current.has(id)){controller.abort();pending.current.delete(id);}
  for(const id of cache.current.keys())if(!wanted.current.has(id))cache.current.delete(id);
  for(const descriptor of descriptors){if(cache.current.has(descriptor.id)||pending.current.has(descriptor.id))continue;const controller=new AbortController();pending.current.set(descriptor.id,controller);
   void readReplayJSON("/api/simulation/simulations/"+manifest.run_id+"/replay/chunks/"+descriptor.id,ReplayChunkSchema,controller.signal,REPLAY_LIMITS.chunkBytes,descriptor.sha256).then(chunk=>{
    if(controller.signal.aborted||!wanted.current.has(descriptor.id))return;
    if(chunk.run_id!==manifest.run_id||chunk.chunk_id!==descriptor.id||chunk.frames[0]!.time!==descriptor.start_time||chunk.frames[chunk.frames.length-1]!.time!==descriptor.end_time)throw new Error("Replay chunk identity or recorded bounds differ from the manifest.");
    cache.current.set(descriptor.id,chunk);setSnapshot({runId:manifest.run_id,chunks:[...cache.current.values()]});
   }).catch((cause:unknown)=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"Recorded replay chunk unavailable.");}).finally(()=>{if(pending.current.get(descriptor.id)===controller)pending.current.delete(descriptor.id);});
  }
 },[manifest,index,reload]);
 const window=useMemo(()=>snapshot?.runId===runId?snapshot.chunks:[],[snapshot,runId]);
 const frames=useMemo(()=>replayFrames(window),[window]),events=useMemo(()=>replayEvents(window),[window]);
 const first=frames[0],last=frames[frames.length-1];
 const buffering=Boolean(manifest&&(!window.some(chunk=>chunk.chunk_id===manifest.chunks[index]!.id)||!first||!last||time>last.time||(time<first.time&&index>0)));
 const networkMatches=Boolean(manifest&&manifest.network_version_id===networkId);
 useEffect(()=>{canAdvance.current=Boolean(manifest&&networkMatches&&!buffering&&!error);},[manifest,networkMatches,buffering,error]);
 useEffect(()=>{
  if(!playing||!manifest)return;let raf=0,previous=performance.now(),accumulated=0;
  const tick=(now:number)=>{const elapsed=Math.min(0.25,(now-previous)/1000);previous=now;accumulated+=elapsed;
   if(accumulated>=1/30){if(canAdvance.current){const next=Math.min(manifest.duration_seconds,timeline.current+accumulated*speed);timeline.current=next;setTime(next);if(next>=manifest.duration_seconds){setPlaying(false);return;}}accumulated=0;}
   raf=requestAnimationFrame(tick);
  };raf=requestAnimationFrame(tick);return ()=>cancelAnimationFrame(raf);
 },[playing,speed,manifest]);
 const vehicles=useMemo(()=>manifest&&!buffering?interpolateReplay(frames,events,time,manifest.sample_interval_seconds+1e-6):[],[manifest,buffering,frames,events,time]);
 const visibleVehicles=useMemo(()=>boundedReplayVehicles(vehicles,selectedId),[vehicles,selectedId]);
 const selected=selectedId?vehicles.find(vehicle=>vehicle.id===selectedId)??null:null;
 const count=manifest?.counts.findLast(item=>item.time<=time);
 const seek=useCallback((value:number)=>{if(!manifest||!Number.isFinite(value))return;timeline.current=Math.max(0,Math.min(manifest.duration_seconds,value));setTime(timeline.current);},[manifest]);
 const reset=useCallback(()=>{setPlaying(false);seek(0);},[seek]);
 const select=useCallback((id:string)=>{setSelectedId(id);setFollow(false);},[]);
 const retry=useCallback(()=>{setError(null);setLoaded(null);setSnapshot(null);setPlaying(false);setReload(value=>value+1);},[]);
 return {runId,manifest,networkMatches,error,loading:Boolean(runId&&!manifest&&!error),buffering,time,playing,speed,setSpeed,setPlaying,selectedId,selected,select,follow,setFollow,vehicles:visibleVehicles,recordedVehicleCount:vehicles.length,activeCount:count?.active??0,countTime:count?.time??0,cacheSize:window.length,seek,reset,retry};
}
export type VehicleReplay=ReturnType<typeof useVehicleReplay>;
