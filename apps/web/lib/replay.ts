import {z} from "zod";

export const REPLAY_LIMITS={chunkBytes:4*1024*1024,manifestBytes:1024*1024,cachedChunks:3,visibleVehicles:1000,maxVehicles:5000} as const;
const identifier=z.string().min(1).max(128).regex(/^[A-Za-z0-9_.:#-]+$/);
const seconds=z.number().finite().min(0).max(3600);
export const ReplayVehicleSchema=z.object({id:identifier,longitude:z.number().finite().min(-180).max(180),latitude:z.number().finite().min(-90).max(90),heading:z.number().finite().min(0).max(360),speed:z.number().finite().min(0).max(200),vehicle_class:z.literal("passenger"),segment_id:z.number().int().min(0).max(100000)}).strict();
export const ReplayEventSchema=z.object({id:identifier,time:seconds,type:z.enum(["departed","arrived","teleport_start","teleport_end"])}).strict();
export const ReplayFrameSchema=z.object({time:seconds,vehicles:z.array(ReplayVehicleSchema).max(5000),departed:z.array(identifier).max(5000),arrived:z.array(identifier).max(5000),teleported:z.array(identifier).max(5000)}).strict().superRefine((frame,context)=>{if(new Set(frame.vehicles.map(vehicle=>vehicle.id)).size!==frame.vehicles.length)context.addIssue({code:"custom",message:"Duplicate replay vehicle"});});
export const ReplayChunkSchema=z.object({schema_version:z.literal(1),run_id:z.uuid(),chunk_id:z.string().regex(/^\d{6}$/),frames:z.array(ReplayFrameSchema).min(1).max(3601),events:z.array(ReplayEventSchema).max(30000)}).strict().superRefine((chunk,context)=>{if(chunk.frames.some((frame,index)=>index>0&&frame.time<=chunk.frames[index-1]!.time))context.addIssue({code:"custom",message:"Replay timestamps must increase"});});
const descriptor=z.object({id:z.string().regex(/^\d{6}$/),start_time:seconds,end_time:seconds,sample_count:z.number().int().nonnegative().max(100000),sha256:z.string().regex(/^[a-f0-9]{64}$/),size_bytes:z.number().int().min(1).max(REPLAY_LIMITS.chunkBytes)}).strict();
export const ReplayManifestSchema=z.object({schema_version:z.literal(1),run_id:z.uuid(),network_version_id:z.uuid(),duration_seconds:z.number().int().min(1).max(3600),sample_interval_seconds:z.number().int().min(1).max(10),vehicle_class:z.literal("passenger"),synthetic:z.literal(true),coordinate_reference_system:z.literal("EPSG:4326"),chunks:z.array(descriptor).min(1).max(2048),counts:z.array(z.object({time:seconds,active:z.number().int().nonnegative().max(5000),departed:z.number().int().nonnegative().max(5000),arrived:z.number().int().nonnegative().max(5000)}).strict()).max(3601)}).strict().superRefine((manifest,context)=>{
 const ids=new Set<string>();
 for(let index=0;index<manifest.chunks.length;index++){const chunk=manifest.chunks[index]!;if(ids.has(chunk.id)||chunk.start_time>chunk.end_time||chunk.end_time>manifest.duration_seconds||(index>0&&chunk.start_time<manifest.chunks[index-1]!.start_time))context.addIssue({code:"custom",message:"Invalid replay chunk bounds or identity"});ids.add(chunk.id);}
 if(manifest.counts.some((count,index)=>count.time>manifest.duration_seconds||(index>0&&count.time<=manifest.counts[index-1]!.time)))context.addIssue({code:"custom",message:"Invalid recorded count timeline"});
});
export type ReplayVehicle=z.infer<typeof ReplayVehicleSchema>;
export type ReplayFrame=z.infer<typeof ReplayFrameSchema>;
export type ReplayEvent=z.infer<typeof ReplayEventSchema>;
export type ReplayChunk=z.infer<typeof ReplayChunkSchema>;
export type ReplayManifest=z.infer<typeof ReplayManifestSchema>;
export type ReplayDescriptor=z.infer<typeof descriptor>;
export type ReplaySceneState={vehicles:readonly ReplayVehicle[];time:number;selectedId:string|null;follow:boolean;onSelect:(id:string)=>void};

export async function readReplayJSON<T>(url:string,schema:z.ZodType<T>,signal:AbortSignal,maximum:number,checksum?:string,fetcher:typeof fetch=fetch):Promise<T>{
 const response=await fetcher(url,{signal:AbortSignal.any([signal,AbortSignal.timeout(15000)]),cache:"no-store",headers:{Accept:"application/json"}});
 if(!response.ok)throw new Error(response.status===409?"Replay is available only after a successful run has published verified artifacts.":"Replay request failed (HTTP "+response.status+"). Retry the recorded run.");
 if(Number(response.headers.get("content-length"))>maximum){await response.body?.cancel();throw new Error("Replay artifact exceeds the response budget.");}
 const reader=response.body?.getReader();if(!reader)throw new Error("Replay response has no data.");
 const parts:Uint8Array[]=[];let size=0;
 try{while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>maximum){await reader.cancel();throw new Error("Replay artifact exceeds the response budget.");}parts.push(next.value);}}finally{reader.releaseLock();}
 const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.byteLength;}
 if(checksum){const digest=new Uint8Array(await crypto.subtle.digest("SHA-256",bytes));const actual=Array.from(digest,value=>value.toString(16).padStart(2,"0")).join("");if(actual!==checksum)throw new Error("Replay checksum verification failed; recorded positions were not adopted.");}
 let value:unknown;try{value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));}catch{throw new Error("Replay artifact is not valid UTF-8 JSON.");}
 const parsed=schema.safeParse(value);if(!parsed.success)throw new Error("Replay artifact does not match the bounded trajectory contract.");return parsed.data;
}

export function replayChunkIndex(manifest:ReplayManifest,time:number):number{
 let index=manifest.chunks.findIndex(chunk=>time>=chunk.start_time&&time<=chunk.end_time);
 if(index<0)index=manifest.chunks.findIndex(chunk=>chunk.start_time>time);
 return index<0?manifest.chunks.length-1:index;
}
export function replayFrames(chunks:readonly ReplayChunk[]):ReplayFrame[]{
 const frames=new Map<number,ReplayFrame>();for(const chunk of chunks)for(const frame of chunk.frames)frames.set(frame.time,frame);return [...frames.values()].sort((a,b)=>a.time-b.time);
}
export function replayEvents(chunks:readonly ReplayChunk[]):ReplayEvent[]{
 const events=new Map<string,ReplayEvent>();for(const chunk of chunks)for(const event of chunk.events)events.set(event.id+":"+event.time+":"+event.type,event);return [...events.values()].sort((a,b)=>a.time-b.time);
}
/** Only interpolate two real samples in one uninterrupted recorded segment. */
export function interpolateReplay(frames:readonly ReplayFrame[],events:readonly ReplayEvent[],time:number,maximumGap:number):ReplayVehicle[]{
 if(!frames.length)return [];
 let low=0,high=frames.length-1;while(low<=high){const middle=(low+high)>>1;if(frames[middle]!.time<=time)low=middle+1;else high=middle-1;}
 const left=frames[high];if(!left)return [];
 if(Math.abs(left.time-time)<1e-7)return left.vehicles.slice();
 const right=frames[high+1];if(!right||right.time-left.time>maximumGap+1e-7)return [];
 const next=new Map(right.vehicles.map(vehicle=>[vehicle.id,vehicle]));const fraction=(time-left.time)/(right.time-left.time);
 const discontinuities=new Map<string,ReplayEvent[]>();for(const event of events)if(event.time>left.time&&event.time<=right.time&&event.type!=="departed"){const list=discontinuities.get(event.id)??[];list.push(event);discontinuities.set(event.id,list);}
 const result:ReplayVehicle[]=[];
 for(const vehicle of left.vehicles){const stops=discontinuities.get(vehicle.id)??[];if(stops.some(event=>event.time<=time&&(event.type==="arrived"||event.type==="teleport_start")))continue;const target=next.get(vehicle.id);
  if(!target||target.segment_id!==vehicle.segment_id||stops.some(event=>event.type.startsWith("teleport"))){if(stops.some(event=>event.time>time&&(event.type==="arrived"||event.type==="teleport_start")))result.push(vehicle);continue;}
  const angle=((target.heading-vehicle.heading+540)%360)-180;
  result.push({...vehicle,longitude:vehicle.longitude+(target.longitude-vehicle.longitude)*fraction,latitude:vehicle.latitude+(target.latitude-vehicle.latitude)*fraction,heading:(vehicle.heading+angle*fraction+360)%360,speed:vehicle.speed+(target.speed-vehicle.speed)*fraction});
 }
 return result;
}
export function boundedReplayVehicles(vehicles:readonly ReplayVehicle[],selectedId:string|null):ReplayVehicle[]{
 if(vehicles.length<=REPLAY_LIMITS.visibleVehicles)return vehicles.slice();const shown=vehicles.slice(0,REPLAY_LIMITS.visibleVehicles);const selected=selectedId?vehicles.find(vehicle=>vehicle.id===selectedId):undefined;if(selected&&!shown.some(vehicle=>vehicle.id===selected.id))shown[shown.length-1]=selected;return shown;
}
