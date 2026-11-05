import { z } from "zod";

const UUID=z.uuid();
const finite=z.number().finite();
const timestamp=z.iso.datetime({offset:true});
const checksum=z.string().regex(/^[a-f0-9]{64}$/);
export const RUN_STATUSES=["queued","running","succeeded","failed","cancelled"] as const;
export const RunStatusSchema=z.enum(RUN_STATUSES);
/** Match Python round() for nonnegative demand products, including half ties. */
export function effectiveTripCount(value:{trip_target:number;demand_multiplier:number}){const product=value.trip_target*value.demand_multiplier,lower=Math.floor(product);return product-lower===0.5?(lower%2===0?lower:lower+1):Math.round(product);}
export const DemandSchema=z.object({
  trip_target:z.number().int().min(1).max(5_000),
  duration_seconds:z.number().int().min(30).max(3_600),
  seed:z.number().int().min(0).max(2_147_483_647),
  departure_distribution:z.enum(["uniform","poisson","burst"]),
  vehicle_class:z.literal("passenger"),
  od_policy:z.literal("reachable_uniform"),
  demand_multiplier:finite.min(0.1).max(3),
  sample_interval_seconds:finite.int().min(1).max(10),
}).strict().refine(value=>effectiveTripCount(value)>=1&&effectiveTripCount(value)<=5_000,{message:"The effective demand must remain between 1 and 5,000 trips.",path:["demand_multiplier"]});
export const ScenarioInputSchema=z.object({name:z.string().trim().min(1).max(200).refine(value=>!/[\u0000-\u001F]/.test(value),"Scenario name must contain printable text"),network_version_id:UUID,demand:DemandSchema}).strict();
export const ValidationSchema=z.object({
  valid:z.boolean(),errors:z.array(z.string().max(5_000)).max(100),warnings:z.array(z.string().max(5_000)).max(100),
  network_artifact_sha256:checksum.nullish(),mapped_edge_count:z.number().int().nonnegative().nullish(),engine_version:z.string().max(100).nullish(),
}).strip();
export const ScenarioSchema=ScenarioInputSchema.extend({
  id:UUID,configuration_checksum:checksum,created_at:timestamp,synthetic:z.literal(true),network_version_label:z.string().max(200),validation:ValidationSchema,
}).strip();
export const RunSchema=z.object({
  id:UUID,scenario_id:UUID,network_version_id:UUID,scenario_name:z.string().max(200),status:RunStatusSchema,seed:z.number().int(),
  created_at:timestamp,started_at:timestamp.nullable(),finished_at:timestamp.nullable(),worker_id:z.string().max(200).nullable(),engine_version:z.string().max(100).nullable(),
  input_sha256:checksum,error_code:z.string().max(100).nullable(),error_message:z.string().max(5_000).nullable(),
  progress:z.object({simulated_seconds:finite.min(0).max(3_600),duration_seconds:finite.int().min(1).max(3_600),departed:z.number().int().min(0).max(5_000),completed:z.number().int().min(0).max(5_000),active:z.number().int().min(0).max(5_000)}).refine(value=>value.simulated_seconds<=value.duration_seconds&&value.completed<=value.departed,"Simulation progress is inconsistent"),
  cancel_requested:z.boolean(),attempt_number:z.number().int().positive(),retry_of:UUID.nullable(),synthetic:z.literal(true),
}).strip();
export const MetricSchema=z.object({metric_name:z.string().max(100),value:finite.nullable(),unit:z.string().max(64),aggregation:z.string().max(64),calculation_version:z.string().max(64)}).strip();
export const MetricsSchema=z.object({run_id:UUID,metrics:z.array(MetricSchema).max(100),vehicle_counts:z.array(z.object({time:finite.nonnegative(),active:z.number().int().nonnegative(),departed:z.number().int().nonnegative(),arrived:z.number().int().nonnegative()})).max(10_000)}).strip();
export const EventSchema=z.object({id:UUID,run_id:UUID,event_type:z.string().max(100),message:z.string().max(5_000),progress_seconds:finite.nullable(),created_at:timestamp}).strip();
function page<T extends z.ZodType>(schema:T){return z.object({items:z.array(schema).max(100),total:z.number().int().nonnegative(),limit:z.number().int().positive().max(100),offset:z.number().int().nonnegative()}).strip();}
export const ScenarioListSchema=page(ScenarioSchema);
export const RunListSchema=page(RunSchema);
export const EventsSchema=page(EventSchema);
export const SimulationNetworkSchema=z.object({
  id:UUID,version_label:z.string().max(200),name:z.string().max(255).optional(),region_name:z.string().max(255).optional(),
  is_synthetic:z.boolean(),source_checksum:checksum.nullish(),network_artifact_sha256:checksum.nullish(),engine_version:z.string().max(100).nullish(),
  mapped_edge_count:z.number().int().nonnegative().nullish(),validation:ValidationSchema,
}).strip();
export const SimulationNetworkListSchema=page(SimulationNetworkSchema);
export const ComparisonMetricSchema=z.object({metric_name:z.string().max(100),unit:z.string().max(64),baseline_value:finite.nullable(),modified_value:finite.nullable(),absolute_change:finite.nullable(),percentage_change:finite.nullable()}).strip();
export const ComparisonSchema=z.object({id:UUID,baseline_run_id:UUID,modified_run_id:UUID,network_version_id:UUID,created_at:timestamp,metrics:z.array(ComparisonMetricSchema).max(100),warnings:z.array(z.string().max(5_000)).max(100)}).strip();
export type Demand=z.output<typeof DemandSchema>;
export type ScenarioInput=z.output<typeof ScenarioInputSchema>;
export type Scenario=z.output<typeof ScenarioSchema>;
export type SimulationRun=z.output<typeof RunSchema>;
export type SimulationMetrics=z.output<typeof MetricsSchema>;
export type Metric=z.output<typeof MetricSchema>;
export type SimulationNetwork=z.output<typeof SimulationNetworkSchema>;
export type Validation=z.output<typeof ValidationSchema>;
export type Comparison=z.output<typeof ComparisonSchema>;

export const DEFAULT_DEMAND:Demand={trip_target:1_000,duration_seconds:900,seed:42,departure_distribution:"uniform",vehicle_class:"passenger",od_policy:"reachable_uniform",demand_multiplier:1,sample_interval_seconds:2};
export const DEMAND_PRESETS=[{label:"Light",trips:500},{label:"Normal",trips:1_000},{label:"Heavy",trips:2_000}] as const;
export function runIsActive(status:SimulationRun["status"]){return status==="queued"||status==="running";}
export function metricValue(value:number|null|undefined,maximumFractionDigits=2){
 if(value===null||value===undefined||!Number.isFinite(value))return "—";
 if(value!==0&&Math.abs(value)<10**(-maximumFractionDigits))return value.toExponential(maximumFractionDigits);
 return value.toLocaleString("en",{maximumFractionDigits});
}
export function metricName(name:string){return ({generated_trips:"Generated trips",departed_trips:"Departed trips",completed_trips:"Completed trips",incomplete_trips:"Incomplete trips",mean_trip_duration:"Mean completed-trip duration",mean_trip_duration_seconds:"Mean completed-trip duration",mean_time_loss:"Mean completed-trip time loss",mean_time_loss_seconds:"Mean completed-trip time loss",mean_moving_speed:"Mean moving speed",mean_moving_speed_mps:"Mean moving speed",mean_waiting_time:"Mean waiting time",mean_waiting_time_seconds:"Mean waiting time",teleports:"Teleports",simulation_duration:"Simulated duration",simulation_duration_seconds:"Simulated duration",worker_execution_time:"Worker wall-clock time",worker_execution_seconds:"Worker wall-clock time",throughput:"Throughput",completed_throughput:"Completed-trip throughput",sumo_execution_time:"SUMO wall-clock time",maximum_active_vehicles:"Peak active vehicles",worker_child_peak_rss:"Worker process peak RSS",sumo_peak_rss:"SUMO process peak RSS",native_children_peak_rss:"Native child process peak RSS",invalid_trajectory_samples:"Omitted invalid position samples",projection_crosschecks:"Projection cross-checks",maximum_projection_error:"Maximum projection error"} as Record<string,string>)[name]??name.replaceAll("_"," ");}
export function sampleUpperBound(demand:Demand){return (Math.floor(demand.duration_seconds/demand.sample_interval_seconds)+1)*effectiveTripCount(demand);}
export function scenarioFingerprint(input:ScenarioInput){return JSON.stringify({name:input.name.trim(),network_version_id:input.network_version_id,demand:input.demand});}

/** Same-origin allowlisted proxy owns credentials. No browser token fields exist. */
export async function simulationJSON<T extends z.ZodType>(path:string,schema:T,options:RequestInit={}):Promise<z.output<T>>{
  if(!/^\/(?:simulation-networks|scenarios|simulations|comparisons)(?:[/?]|$)/.test(path))throw new Error("Unsupported simulation resource.");
  const response=await fetch(`/api/simulation${path}`,{...options,cache:"no-store",headers:{Accept:"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...options.headers},signal:options.signal?AbortSignal.any([options.signal,AbortSignal.timeout(15_000)]):AbortSignal.timeout(15_000)});
  if(!response.ok){
    let message=response.status===403?"Simulation access is disabled. Configure the server-only local write gate and recreate web/API.":response.status===409?"This operation conflicts with the run state or network. Refresh and validate the scenario.":response.status===429?"The bounded simulation queue is full. Retry after a run finishes.":`Simulation request failed (HTTP ${response.status}).`;
    try{const body=await response.json() as {detail?:unknown;error?:unknown};const detail=body.detail??body.error;if(typeof detail==="string"&&detail.length<=1_000&&!/https?:|(?:token|password|secret)\s*[:=]|\beyJ[A-Za-z0-9_-]+\./i.test(detail))message=detail;else if(Array.isArray(detail))message="Scenario parameters are invalid. Check trip, duration, multiplier and seed limits.";}catch{/* Preserve bounded status-based errors. */}
    throw new Error(message);
  }
  const declared=Number(response.headers.get("content-length"));if(declared>4*1024*1024){await response.body?.cancel();throw new Error("Simulation response exceeds the browser display limit.");}
  const reader=response.body?.getReader();if(!reader)throw new Error("Simulation response has no body.");
  const chunks:Uint8Array[]=[];let bytes=0;
  try{while(true){const next=await reader.read();if(next.done)break;bytes+=next.value.byteLength;if(bytes>4*1024*1024)throw new Error("Simulation response exceeds the browser display limit.");chunks.push(next.value);}}catch(error){await reader.cancel();throw error;}finally{reader.releaseLock();}
  const payload=new Uint8Array(bytes);let at=0;for(const chunk of chunks){payload.set(chunk,at);at+=chunk.byteLength;}
  try{return schema.parse(JSON.parse(new TextDecoder().decode(payload)));}catch{throw new Error("The simulation service returned an invalid response. Refresh and inspect server verification logs.");}
}
export const simulationGet=<T extends z.ZodType>(path:string,schema:T,signal?:AbortSignal)=>simulationJSON(path,schema,signal?{signal}:{});
export const simulationPost=<T extends z.ZodType>(path:string,schema:T,body:unknown={},key?:string)=>simulationJSON(path,schema,{method:"POST",body:JSON.stringify(body),headers:{"X-Earthmind-Intent":"simulation-write",...(key?{"Idempotency-Key":key}:{})}});

/** Published engine logs are verified server-side and rendered as bounded text. */
export async function simulationLog(runId:string,signal?:AbortSignal):Promise<string>{
  if(!UUID.safeParse(runId).success)throw new Error("Invalid simulation run identifier.");
  const response=await fetch(`/api/simulation/simulations/${runId}/logs`,{cache:"no-store",headers:{Accept:"text/plain"},signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15_000)]):AbortSignal.timeout(15_000)});
  if(!response.ok)throw new Error(`Verified SUMO log unavailable (HTTP ${response.status}).`);
  if(!response.headers.get("content-type")?.toLowerCase().startsWith("text/plain")){await response.body?.cancel();throw new Error("The simulation log response is not plain text.");}
  const budget=2*1024*1024;if(Number(response.headers.get("content-length"))>budget){await response.body?.cancel();throw new Error("The SUMO log exceeds the 2 MiB display budget.");}
  const reader=response.body?.getReader();if(!reader)throw new Error("The SUMO log has no body.");
  const chunks:Uint8Array[]=[];let bytes=0;
  try{while(true){const next=await reader.read();if(next.done)break;bytes+=next.value.byteLength;if(bytes>budget)throw new Error("The SUMO log exceeds the 2 MiB display budget.");chunks.push(next.value);}}catch(error){await reader.cancel();throw error;}finally{reader.releaseLock();}
  const payload=new Uint8Array(bytes);let offset=0;for(const chunk of chunks){payload.set(chunk,offset);offset+=chunk.byteLength;}
  return new TextDecoder().decode(payload).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g,"");
}
