import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import test from "node:test";
import {proxySimulation} from "../lib/simulation-proxy";
import {DEFAULT_DEMAND} from "../lib/simulation";

// Isolated proxy contract fixtures. No working credentials or native run results.
const runId="11111111-1111-4111-8111-111111111111",scenarioId="22222222-2222-4222-8222-222222222222",networkId="33333333-3333-4333-8333-333333333333",otherId="44444444-4444-4444-8444-444444444444";
const checksum="a".repeat(64),timestamp="2026-10-27T12:00:00Z";
const privateGate="unit-fixture-server-write-token-not-a-working-credential";
const environment={API_INTERNAL_URL:"http://api.unit.invalid:8000",EARTHMIND_DEV_WRITE_TOKEN:privateGate,CESIUM_ION_SECRET_TOKEN:"unit-fixture-private-gis-not-a-working-credential"};
const validation={valid:true,errors:[],warnings:[],network_artifact_sha256:checksum,mapped_edge_count:5,engine_version:"unit-fixture-only"};
const scenario={id:scenarioId,name:"Synthetic proxy unit fixture",network_version_id:networkId,network_version_label:"unit-fixture-only",demand:{...DEFAULT_DEMAND},configuration_checksum:checksum,created_at:timestamp,synthetic:true,validation};
const run={id:runId,scenario_id:scenarioId,network_version_id:networkId,scenario_name:scenario.name,status:"queued",seed:42,created_at:timestamp,started_at:null,finished_at:null,worker_id:null,engine_version:null,input_sha256:checksum,error_code:null,error_message:null,progress:{simulated_seconds:0,duration_seconds:900,departed:0,completed:0,active:0},cancel_requested:false,attempt_number:1,retry_of:null,synthetic:true};
const metrics={run_id:runId,metrics:[{metric_name:"generated_trips",value:1_000,unit:"trips",aggregation:"run",calculation_version:"unit-fixture-only"}],vehicle_counts:[]};
const publishedRun={...run,status:"succeeded",started_at:timestamp,finished_at:timestamp,engine_version:"unit-fixture-only"};
const exportValue={schema_version:1,synthetic:true,disclosure:"Synthetic unit fixture, not SUMO evidence",run:publishedRun,scenario,reproducibility:{input_sha256:checksum,configuration_checksum:checksum,engine_version:"unit-fixture-only",input:{schema_version:1,network_version_id:networkId,network_artifact:"recovery-v1",network_sha256:checksum,source_sha256:checksum,mapping_sha256:checksum,demand:{...DEFAULT_DEMAND}}},metrics,artifacts:[]};
function request(path:readonly string[],options:{method?:string;headers?:Record<string,string>;body?:unknown;raw?:string;query?:string;url?:string}={}){
 const method=options.method??"GET";
 return new Request(options.url??`http://localhost:3000/api/simulation/${path.join("/")}${options.query??""}`,{method,headers:{Host:"localhost:3000",...(method==="POST"?{Origin:"http://localhost:3000","Content-Type":"application/json","X-Earthmind-Intent":"simulation-write"}:{}),...options.headers},...(method==="POST"?{body:options.raw??JSON.stringify(options.body??{})}:{})});
}
function mockResponse(value:unknown,status=200){
 const calls:{url:string;options:RequestInit|undefined}[]=[];
 const fetcher:typeof fetch=async(url,options)=>{calls.push({url:String(url),options});return Response.json(value,{status});};
 return {calls,fetcher};
}
const runPath=["simulations",runId] as const;

test("normal reads reach only the configured API prefix and project the allowlisted run schema",async()=>{
 const mock=mockResponse({...run,private_config:privateGate,internal_file:"unit-private-file"});
 const response=await proxySimulation(request(runPath),runPath,mock.fetcher,environment);
 assert.equal(response.status,200);const body=await response.json();assert.deepEqual(body,run);
 assert.equal(mock.calls[0]?.url,`http://api.unit.invalid:8000/api/v1/simulations/${runId}`);
 assert.equal(response.headers.get("Cache-Control"),"no-store");assert.equal(response.headers.get("X-Content-Type-Options"),"nosniff");
 const headers=new Headers(mock.calls[0]?.options?.headers);assert.equal(headers.has("X-Earthmind-Dev-Token"),false);assert.equal(headers.has("Authorization"),false);
 assert.equal(JSON.stringify(body).includes(privateGate),false);
});

test("private write authorization is injected once only after same-origin JSON intent validation",async()=>{
 const mock=mockResponse(run,202),path=["simulations"];
 const response=await proxySimulation(request(path,{method:"POST",body:{scenario_id:scenarioId,seed:42},headers:{"Idempotency-Key":"unit-idempotency-1"}}),path,mock.fetcher,environment);
 assert.equal(response.status,202);assert.equal(mock.calls.length,1);
 const headers=new Headers(mock.calls[0]!.options?.headers);assert.equal(headers.get("X-Earthmind-Dev-Token"),privateGate);assert.equal(headers.get("Idempotency-Key"),"unit-idempotency-1");
 assert.equal(headers.has("X-Earthmind-Intent"),false);assert.equal(headers.has("Authorization"),false);
 assert.deepEqual(JSON.parse(String(mock.calls[0]!.options?.body)),{scenario_id:scenarioId,seed:42});
 assert.equal(String(mock.calls[0]!.options?.body).includes(privateGate),false);assert.equal(mock.calls[0]!.url.includes(privateGate),false);
 assert.equal((await response.text()).includes(privateGate),false);
});

test("missing intent, cross-site requests and unconfigured local authorization cannot create expensive work",async()=>{
 const path=["simulations"],body={scenario_id:scenarioId};
 for(const headers of [{"X-Earthmind-Intent":""},{Origin:"http://foreign.unit.invalid"},{"Sec-Fetch-Site":"cross-site"},{Origin:"null"},{Origin:""}]){
  const mock=mockResponse(run,202);const response=await proxySimulation(request(path,{method:"POST",body,headers:{"Idempotency-Key":"unit-key",...headers}}),path,mock.fetcher,environment);
  assert.equal(response.status,403);assert.equal(mock.calls.length,0);
 }
 const missing=mockResponse(run,202);const disabled=await proxySimulation(request(path,{method:"POST",body,headers:{"Idempotency-Key":"unit-key"}}),path,missing.fetcher,{API_INTERNAL_URL:environment.API_INTERNAL_URL});
 assert.equal(disabled.status,503);assert.equal(missing.calls.length,0);assert.equal((await disabled.text()).includes(privateGate),false);
});

test("unsupported mutation MIME remains HTTP415 before any expensive upstream request",async()=>{
 const path=["scenarios"],mock=mockResponse(scenario,201);
 const response=await proxySimulation(request(path,{method:"POST",raw:"unit plain payload",headers:{"Content-Type":"text/plain"}}),path,mock.fetcher,environment);
 assert.equal(response.status,415);assert.equal(mock.calls.length,0);
});

test("Next standalone bind URLs use the validated browser-facing loopback Host and ignore forwarded hosts",async()=>{
 const path=["scenarios"],mock=mockResponse(scenario,201);
 const response=await proxySimulation(request(path,{url:"http://0.0.0.0:3000/api/simulation/scenarios",method:"POST",body:{name:scenario.name,network_version_id:networkId,demand:DEFAULT_DEMAND},headers:{Host:"127.0.0.1:3000",Origin:"http://127.0.0.1:3000","X-Forwarded-Host":"foreign.unit.invalid"}}),path,mock.fetcher,environment);
 assert.equal(response.status,201);assert.equal(mock.calls.length,1);
 for(const host of ["foreign.unit.invalid","localhost:70000","localhost:0","localhost.attacker.invalid","localhost@foreign.unit.invalid","localhost:3000,foreign.unit.invalid"]){
  const blocked=mockResponse(scenario,201);const denied=await proxySimulation(request(path,{url:"http://0.0.0.0:3000/api/simulation/scenarios",method:"POST",body:{},headers:{Host:host,Origin:"http://localhost:3000","X-Forwarded-Host":"localhost:3000"}}),path,blocked.fetcher,environment);
  assert.equal(denied.status,403,host);assert.equal(blocked.calls.length,0);
 }
});

test("the local read boundary rejects DNS rebinding and cross-origin reads too",async()=>{
 for(const headers of [{Host:"foreign.unit.invalid"},{Origin:"http://foreign.unit.invalid"},{"Sec-Fetch-Site":"cross-site"}]){
  const mock=mockResponse(run);const response=await proxySimulation(request(runPath,{headers}),runPath,mock.fetcher,environment);
  assert.equal(response.status,403);assert.equal(mock.calls.length,0);
 }
});

test("strict nested scenario validation rejects arbitrary commands and unrecognized configuration",async()=>{
 const path=["scenarios"],body={name:scenario.name,network_version_id:networkId,demand:{...DEFAULT_DEMAND}};
 for(const input of [{...body,command:"unit-disallowed"},{...body,demand:{...body.demand,command:"unit-disallowed"}},{...body,demand:{...body.demand,trip_target:5_000,demand_multiplier:3}},{...body,network_version_id:"../../unit"}]){
  const mock=mockResponse(scenario,201);const response=await proxySimulation(request(path,{method:"POST",body:input}),path,mock.fetcher,environment);
  assert.equal(response.status,422);assert.equal(mock.calls.length,0);
 }
});

test("malformed JSON is HTTP422 while byte-budget excess is HTTP413, with no upstream call",async()=>{
 const path=["scenarios"];
 const malformed=mockResponse(scenario,201);const invalid=await proxySimulation(request(path,{method:"POST",raw:"{unit malformed"}),path,malformed.fetcher,environment);
 assert.equal(invalid.status,422);assert.equal(malformed.calls.length,0);
 const excessive=mockResponse(scenario,201);const oversized=await proxySimulation(request(path,{method:"POST",raw:JSON.stringify({name:"🚗".repeat(20_000)})}),path,excessive.fetcher,environment);
 assert.equal(oversized.status,413);assert.equal(excessive.calls.length,0);
 const declared=mockResponse(scenario,201);const overdeclared=await proxySimulation(request(path,{method:"POST",body:{},headers:{"Content-Length":String(64*1024+1)}}),path,declared.fetcher,environment);
 assert.equal(overdeclared.status,413);assert.equal(declared.calls.length,0);
});

test("run submission requires a bounded safe idempotency key before contacting the queue API",async()=>{
 const path=["simulations"];
 for(const key of ["","../unit-key","unit key","x".repeat(129)]){
  const mock=mockResponse(run,202);const response=await proxySimulation(request(path,{method:"POST",body:{scenario_id:scenarioId},headers:{"Idempotency-Key":key}}),path,mock.fetcher,environment);
  assert.equal(response.status,422);assert.equal(mock.calls.length,0);
 }
});

test("arbitrary paths, file references, unsupported verbs and unbounded queries never become upstream URLs",async()=>{
 const invalidPaths=[["private"],["simulations","../../unit"],["simulations",runId,"replay","chunks","../unit"],["simulations",runId,"replay","chunks","000000","extra"],["scenarios",scenarioId,"logs"]];
 for(const path of invalidPaths){const mock=mockResponse(run);const response=await proxySimulation(request(path),path,mock.fetcher,environment);assert.equal(response.status,404);assert.equal(mock.calls.length,0);}
 const unsupported=mockResponse(run);const deleted=await proxySimulation(new Request("http://localhost:3000/api/simulation/simulations",{method:"DELETE"}),["simulations"],unsupported.fetcher,environment);assert.equal(deleted.status,405);assert.equal(unsupported.calls.length,0);
 for(const query of ["?limit=101","?limit=0","?offset=100001","?offset=-1","?limit=10&limit=11","?url=http://foreign.unit.invalid","?format=csv"]){const mock=mockResponse({items:[],total:0,limit:25,offset:0});const response=await proxySimulation(request(["simulations"],{query}),["simulations"],mock.fetcher,environment);assert.equal(response.status,422,query);assert.equal(mock.calls.length,0);}
});

test("valid bounded pagination remains explicit in the allowlisted backend URL",async()=>{
 const mock=mockResponse({items:[],total:0,limit:100,offset:100});const response=await proxySimulation(request(["simulations"],{query:"?limit=100&offset=100"}),["simulations"],mock.fetcher,environment);
 assert.equal(response.status,200);assert.equal(mock.calls[0]?.url,"http://api.unit.invalid:8000/api/v1/simulations?limit=100&offset=100");
});

test("resource, metric and event identities must match the requested recorded run",async()=>{
 const wrongRun=mockResponse({...run,id:otherId});assert.equal((await proxySimulation(request(runPath),runPath,wrongRun.fetcher,environment)).status,503);
 const wrongScenario=mockResponse({...scenario,id:otherId});const scenarioPath=["scenarios",scenarioId];assert.equal((await proxySimulation(request(scenarioPath),scenarioPath,wrongScenario.fetcher,environment)).status,503);
 const metricPath=[...runPath,"metrics"],wrongMetrics=mockResponse({...metrics,run_id:otherId});assert.equal((await proxySimulation(request(metricPath),metricPath,wrongMetrics.fetcher,environment)).status,503);
 const eventPath=[...runPath,"events"],wrongEvents=mockResponse({items:[{id:otherId,run_id:otherId,event_type:"unit",message:"Synthetic unit event",progress_seconds:0,created_at:timestamp}],total:1,limit:25,offset:0});assert.equal((await proxySimulation(request(eventPath),eventPath,wrongEvents.fetcher,environment)).status,503);
});

function replayChunk(){return {schema_version:1,run_id:runId,chunk_id:"000000",frames:[{time:0,vehicles:[{id:"unit-car",longitude:10,latitude:20,heading:350,speed:1.25,vehicle_class:"passenger",segment_id:0}],departed:["unit-car"],arrived:[],teleported:[]}],events:[]};}

test("raw replay delivery validates identity yet preserves the exact checksum-bearing source bytes",async()=>{
 const chunk=replayChunk(),raw=" \n"+JSON.stringify(chunk,null,2).replace('"speed": 1.25','"speed": 1.2500')+"\n";
 const path=[...runPath,"replay","chunks","000000"],fetcher:typeof fetch=async()=>new Response(raw,{headers:{"Content-Type":"application/json"}});
 const response=await proxySimulation(request(path),path,fetcher,environment);assert.equal(response.status,200);
 const returned=new Uint8Array(await response.arrayBuffer());assert.deepEqual(returned,new TextEncoder().encode(raw));
 assert.equal(createHash("sha256").update(returned).digest("hex"),createHash("sha256").update(raw).digest("hex"));
 for(const bad of [{...chunk,run_id:otherId},{...chunk,chunk_id:"000001"},{...chunk,extra_field:privateGate}]){const mock=mockResponse(bad);const invalid=await proxySimulation(request(path),path,mock.fetcher,environment);assert.equal(invalid.status,503);assert.equal((await invalid.text()).includes(privateGate),false);}
});

test("upstream authorization, incompatibility and quota failures stay failures without exposing private details",async()=>{
 for(const status of [403,404,409,422,429,500]){
  const mock=mockResponse({detail:`unit secret=${privateGate} http://api.unit.invalid/private`},status);const response=await proxySimulation(request(runPath),runPath,mock.fetcher,environment);
  assert.equal(response.status,status===500?503:status);const body=await response.text();assert.equal(body.includes(privateGate),false);assert.equal(body.includes("api.unit.invalid"),false);
 }
});

test("published JSON exports are projected, retain reproducibility identity and hide unapproved metadata",async()=>{
 const path=[...runPath,"export"],mock=mockResponse({...exportValue,private_credentials:privateGate,reproducibility:{...exportValue.reproducibility,private_path:"unit-private-path"}});
 const response=await proxySimulation(request(path),path,mock.fetcher,environment);assert.equal(response.status,200);
 const body=await response.json();assert.equal(body.run.id,runId);assert.equal(body.reproducibility.input_sha256,checksum);assert.equal(body.metrics.run_id,runId);
 assert.equal(JSON.stringify(body).includes(privateGate),false);assert.equal(JSON.stringify(body).includes("unit-private-path"),false);
 assert.match(response.headers.get("Content-Disposition")??"",/^attachment;/);
 for(const invalidValue of [
  {...exportValue,run:{...publishedRun,id:otherId}},
  {...exportValue,metrics:{...metrics,run_id:otherId}},
  {...exportValue,scenario:{...scenario,id:otherId}},
  {...exportValue,scenario:{...scenario,network_version_id:otherId}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,input_sha256:"b".repeat(64)}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,configuration_checksum:"b".repeat(64)}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,engine_version:"different-unit-engine"}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,input:{...exportValue.reproducibility.input,network_version_id:otherId}}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,input:{...exportValue.reproducibility.input,demand:{...DEFAULT_DEMAND,seed:43}}}},
  {...exportValue,reproducibility:{...exportValue.reproducibility,input:{...exportValue.reproducibility.input,demand:{...DEFAULT_DEMAND,trip_target:1_200}}}},
  {...exportValue,run:{...publishedRun,status:"failed",error_code:"unit_failed"}},
 ]){const invalid=mockResponse(invalidValue);assert.equal((await proxySimulation(request(path),path,invalid.fetcher,environment)).status,503);}

});

test("CSV and engine logs require safe MIME and stay text with no-store/nosniff response headers",async()=>{
 for(const [operation,mime,query] of [["logs","text/plain",""],["export","text/csv","?format=csv"]] as const){
  const path=[...runPath,operation],text="<script>synthetic unit text only</script>\n";
  const good:typeof fetch=async()=>new Response(text,{headers:{"Content-Type":mime}});const response=await proxySimulation(request(path,{query}),path,good,environment);
  assert.equal(response.status,200);assert.equal(await response.text(),text);assert.match(response.headers.get("Content-Type")??"",new RegExp(`^${mime}`));assert.equal(response.headers.get("X-Content-Type-Options"),"nosniff");assert.equal(response.headers.get("Cache-Control"),"no-store");
  const bad:typeof fetch=async()=>new Response(text,{headers:{"Content-Type":"text/html"}});assert.equal((await proxySimulation(request(path,{query}),path,bad,environment)).status,503);
 }
 const badFormat=[...runPath,"export"],mock=mockResponse(exportValue);assert.equal((await proxySimulation(request(badFormat,{query:"?format=xml"}),badFormat,mock.fetcher,environment)).status,422);assert.equal(mock.calls.length,0);
});

test("artifact byte ceilings cancel oversize streams for chunks, manifests, logs and exports",async()=>{
 for(const [tail,maximum,query] of [[["replay","chunks","000000"],4*1024*1024,""],[["replay","manifest"],1024*1024,""],[["logs"],2*1024*1024,""],[["export"],4*1024*1024,"?format=csv"]] as const){
  let cancelled=false;const stream=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new Uint8Array([1]));},cancel(){cancelled=true;}});const fetcher:typeof fetch=async()=>new Response(stream,{headers:{"Content-Length":String(maximum+1),"Content-Type":tail[0]==="logs"?"text/plain":"application/json"}});
  const path=[...runPath,...tail],response=await proxySimulation(request(path,{query}),path,fetcher,environment);assert.equal(response.status,503);assert.equal(cancelled,true);
 }
});
