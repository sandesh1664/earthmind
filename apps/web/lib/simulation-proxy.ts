import {z} from "zod";
import {ComparisonSchema,DemandSchema,EventsSchema,MetricsSchema,RunListSchema,RunSchema,ScenarioInputSchema,ScenarioListSchema,ScenarioSchema,SimulationNetworkListSchema,ValidationSchema} from "./simulation";
import {REPLAY_LIMITS,ReplayChunkSchema,ReplayManifestSchema} from "./replay";

const uuid=z.uuid(),checksum=z.string().regex(/^[a-f0-9]{64}$/);
const runInput=z.object({scenario_id:uuid,seed:z.number().int().min(0).max(2147483647).optional(),retry_of:uuid.optional()}).strict();
const comparisonInput=z.object({baseline_run_id:uuid,modified_run_id:uuid}).strict();
const immutableInput=z.object({schema_version:z.literal(1),network_version_id:uuid,network_artifact:z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/),network_sha256:checksum,source_sha256:checksum,mapping_sha256:checksum,demand:DemandSchema});
const exportSchema=z.object({schema_version:z.literal(1),synthetic:z.literal(true),disclosure:z.string().max(1000),run:RunSchema,scenario:ScenarioSchema,reproducibility:z.object({input_sha256:checksum,configuration_checksum:checksum,engine_version:z.string().max(100).nullable(),input:immutableInput}),metrics:MetricsSchema,artifacts:z.array(z.object({category:z.string().max(100),sha256:checksum,size_bytes:z.number().int().nonnegative(),content_type:z.string().max(100)})).max(2000)});
function failure(status:number,message:string):Response{return Response.json({error:message},{status,headers:{"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}});}
async function boundedBytes(response:Response,maximum:number):Promise<Uint8Array>{
 if(Number(response.headers.get("content-length"))>maximum){await response.body?.cancel();throw new Error("Response too large");}
 const reader=response.body?.getReader();if(!reader)throw new Error("Missing response body");const parts:Uint8Array[]=[];let size=0;
 try{while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>maximum){await reader.cancel();throw new Error("Response too large");}parts.push(next.value);}}finally{reader.releaseLock();}
 const data=new Uint8Array(size);let at=0;for(const part of parts){data.set(part,at);at+=part.length;}return data;
}
function browserFacingOrigin(request:Request):string|null{
 const url=new URL(request.url),host=request.headers.get("host")??url.host;
 const match=/^(localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?$/i.exec(host);
 if(!match||!["http:","https:"].includes(url.protocol)||(match[2]&&(Number(match[2])<1||Number(match[2])>65535)))return null;
 return new URL(url.protocol+"//"+host).origin;
}
export async function proxySimulation(request:Request,path:readonly string[],fetcher:typeof fetch=fetch,environment:Record<string,string|undefined>=process.env):Promise<Response>{
 const method=request.method;const [resource,id,operation,subresource,chunkId]=path;const source=new URL(request.url);
 const expectedOrigin=browserFacingOrigin(request);
 if(expectedOrigin===null||request.headers.get("sec-fetch-site")==="cross-site")return failure(403,"Simulation access requires the local EARTHMIND origin.");
 const suppliedOrigin=request.headers.get("origin");if(suppliedOrigin&&suppliedOrigin!==expectedOrigin)return failure(403,"Cross-origin simulation access is not permitted.");
 let schema:z.ZodType|undefined,input:z.ZodType|undefined,raw:"chunk"|"text"|"csv"|null=null;
 const allowed=new Set<string>();let isMutation=false;
 if(path.length===1&&method==="GET"){
  if(resource==="simulation-networks")schema=SimulationNetworkListSchema;else if(resource==="scenarios")schema=ScenarioListSchema;else if(resource==="simulations")schema=RunListSchema;else return failure(404,"Simulation resource not found.");allowed.add("limit");allowed.add("offset");
 }else if(path.length===1&&method==="POST"){
  isMutation=true;if(resource==="scenarios"){schema=ScenarioSchema;input=ScenarioInputSchema.extend({demand:DemandSchema.strict()}).strict();}else if(resource==="simulations"){schema=RunSchema;input=runInput;}else if(resource==="comparisons"){schema=ComparisonSchema;input=comparisonInput;}else return failure(404,"Simulation resource not found.");
 }else if(uuid.safeParse(id).success){
  if(path.length===2&&method==="GET"){if(resource==="scenarios")schema=ScenarioSchema;else if(resource==="simulations")schema=RunSchema;else if(resource==="comparisons")schema=ComparisonSchema;}
  else if(path.length===3&&method==="POST"){
   isMutation=true;input=z.object({}).strict();if(resource==="scenarios"&&operation==="validate")schema=ValidationSchema;else if(resource==="simulations"&&operation==="cancel")schema=RunSchema;
  }else if(resource==="simulations"&&method==="GET"){
   if(path.length===3&&operation==="events"){schema=EventsSchema;allowed.add("limit");allowed.add("offset");}
   else if(path.length===3&&operation==="metrics")schema=MetricsSchema;
   else if(path.length===3&&operation==="logs"){raw="text";}
   else if(path.length===3&&operation==="export"){schema=exportSchema;allowed.add("format");}
   else if(path.length===4&&operation==="replay"&&subresource==="manifest")schema=ReplayManifestSchema;
   else if(path.length===5&&operation==="replay"&&subresource==="chunks"&&/^\d{6}$/.test(chunkId??"")){schema=ReplayChunkSchema;raw="chunk";}
  }
 }
 if(!schema&&raw!=="text")return failure(["GET","POST"].includes(method)?404:405,"Unsupported simulation resource or operation.");
 const query=new URLSearchParams();for(const [name,value] of source.searchParams){if(!allowed.has(name)||query.has(name))return failure(422,"Unsupported simulation query parameter.");
  if(name==="format"){if(!["json","csv"].includes(value))return failure(422,"Export format must be json or csv.");if(value==="csv")raw="csv";}
  else if(!/^\d+$/.test(value)||!Number.isSafeInteger(Number(value))||(name==="limit"?(Number(value)<1||Number(value)>100):Number(value)>100000))return failure(422,"Simulation pagination exceeds its budget.");query.set(name,value);
 }
 const headers:Record<string,string>={Accept:raw==="text"?"text/plain":raw==="csv"?"text/csv":"application/json"};let body:string|undefined;
 if(isMutation){
  if(suppliedOrigin!==expectedOrigin||request.headers.get("x-earthmind-intent")!=="simulation-write")return failure(403,"Simulation writes require the local origin and explicit application intent.");
  if(request.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase()!=="application/json")return failure(415,"Simulation writes require application/json.");
  const token=environment.EARTHMIND_DEV_WRITE_TOKEN;if(!token||token.length<32)return failure(503,"Local simulation writes are disabled; configure the server-side write gate.");
  if(resource==="simulations"&&path.length===1){const key=request.headers.get("idempotency-key");if(!key||!/^[A-Za-z0-9_.:-]{1,128}$/.test(key))return failure(422,"A valid Idempotency-Key is required for run submission.");headers["Idempotency-Key"]=key;}
  let bytes:Uint8Array;try{bytes=await boundedBytes(new Response(request.body,{headers:request.headers}),64*1024);}catch{return failure(413,"Simulation request exceeds the 64 KiB body limit.");}
  let supplied:unknown;try{supplied=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));}catch{return failure(422,"Simulation request must contain valid UTF-8 JSON.");}
  const parsed=input!.safeParse(supplied);if(!parsed.success)return failure(422,"Simulation parameters are invalid or exceed the configured limits.");body=JSON.stringify(parsed.data);
  headers["Content-Type"]="application/json";headers["X-Earthmind-Dev-Token"]=token;
 }
 const origin=environment.API_INTERNAL_URL??"http://127.0.0.1:8000";
 try{
  const suffix=query.size?"?"+query.toString():"";const response=await fetcher(origin.replace(/\/$/,"")+"/api/v1/"+path.map(encodeURIComponent).join("/")+suffix,{method,headers,...(body===undefined?{}:{body}),signal:AbortSignal.any([request.signal,AbortSignal.timeout(15000)]),cache:"no-store"});
  if(!response.ok){const status=[400,403,404,409,413,422,429,503].includes(response.status)?response.status:503;let message=status===409?"Operation conflicts with the recorded run state, idempotency key, or comparison parameters.":status===403?"Simulation authorization is required.":status===404?"Simulation resource not found.":status===429?"The bounded simulation queue is full; retry after a run finishes.":status===422?"Simulation validation failed; check the scenario and network compatibility.":"Simulation service unavailable.";
   try{const bytes=await boundedBytes(response,8192);const value=JSON.parse(new TextDecoder().decode(bytes)) as {detail?:unknown};if(typeof value.detail==="string"&&value.detail.length<=1000&&!/https?:|\beyJ[A-Za-z0-9_-]+\.|password|secret|credential|authorization\s*[:=]|token\s*[:=]|\/simulation-/i.test(value.detail))message=value.detail;}catch{/* Return bounded status facts without upstream payloads. */}return failure(status,message);
  }
  const maximum=raw==="text"?2*1024*1024:path.includes("manifest")?REPLAY_LIMITS.manifestBytes:4*1024*1024;const bytes=await boundedBytes(response,maximum);
  const common={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"};
  if(raw==="text"||raw==="csv"){const mime=raw==="text"?"text/plain; charset=utf-8":"text/csv; charset=utf-8";if(!(response.headers.get("content-type")??"").startsWith(raw==="text"?"text/plain":"text/csv"))throw new Error("Invalid artifact MIME");return new Response(new TextDecoder("utf-8",{fatal:true}).decode(bytes),{status:response.status,headers:{...common,"Content-Type":mime,...(raw==="csv"?{"Content-Disposition":"attachment; filename=earthmind-"+id+".csv"}:{})}});}
  const parsed=schema!.safeParse(JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes)));if(!parsed.success)throw new Error("Invalid simulation response");
  if(raw==="chunk"){const chunk=ReplayChunkSchema.parse(parsed.data);if(chunk.run_id!==id||chunk.chunk_id!==chunkId)throw new Error("Mismatched replay identity");return new Response(bytes as BodyInit,{status:response.status,headers:{...common,"Content-Type":"application/json"}});}
  if(path.includes("manifest")&&ReplayManifestSchema.parse(parsed.data).run_id!==id)throw new Error("Mismatched manifest identity");
  if(id&&path.length===2&&(parsed.data as {id?:string}).id!==id)throw new Error("Mismatched resource identity");
  if(id&&operation==="metrics"&&(parsed.data as {run_id?:string}).run_id!==id)throw new Error("Mismatched metrics identity");
  if(id&&operation==="events"&&EventsSchema.parse(parsed.data).items.some(event=>event.run_id!==id))throw new Error("Mismatched event identity");
  if(operation==="export"){
   const output=exportSchema.parse(parsed.data),input=output.reproducibility.input;
   if(output.run.id!==id||output.run.status!=="succeeded"||output.metrics.run_id!==id||output.scenario.id!==output.run.scenario_id||output.scenario.network_version_id!==output.run.network_version_id||input.network_version_id!==output.run.network_version_id||output.reproducibility.input_sha256!==output.run.input_sha256||output.reproducibility.configuration_checksum!==output.scenario.configuration_checksum||output.reproducibility.engine_version!==output.run.engine_version||input.demand.seed!==output.run.seed)throw new Error("Mismatched export provenance");
   for(const key of Object.keys(output.scenario.demand) as (keyof typeof output.scenario.demand)[])if(key!=="seed"&&input.demand[key]!==output.scenario.demand[key])throw new Error("Mismatched export demand");
  }
  return Response.json(parsed.data,{status:response.status,headers:{...common,...(operation==="export"?{"Content-Disposition":"attachment; filename=earthmind-"+id+".json"}:{})}});
 }catch{return failure(503,"Simulation response is unavailable, invalid, or exceeds its bounded artifact budget.");}
}
