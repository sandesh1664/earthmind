import assert from "node:assert/strict";
import test from "node:test";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {DEFAULT_DEMAND,DemandSchema,MetricSchema,ScenarioInputSchema,RunSchema,effectiveTripCount,metricValue,runIsActive,scenarioFingerprint,sampleUpperBound,simulationJSON,simulationPost,simulationLog} from "../lib/simulation";
import {ActiveVehicleCounts,activeCountPath} from "../components/simulation/SimulationAnalytics";
import {MetricGrid,RunStatus,SyntheticNotice} from "../components/simulation/shared";

const network="4aa62897-1a54-546c-a390-ddb156838f8e";
const runId="10000000-0000-4000-8000-000000000001";
const input={name:"Unit test synthetic scenario",network_version_id:network,demand:{...DEFAULT_DEMAND}};

test("scenario controls enforce the canonical bounded synthetic passenger contract",()=>{
 assert.equal(ScenarioInputSchema.parse(input).demand.trip_target,1_000);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,trip_target:5_000,demand_multiplier:3}).success,false);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,duration_seconds:3_601}).success,false);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,seed:-1}).success,false);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,sample_interval_seconds:1.5}).success,false);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,vehicle_class:"truck"}).success,false);
 assert.equal(ScenarioInputSchema.safeParse({...input,name:"invalid\nname"}).success,false);
 for(const distribution of ["uniform","poisson","burst"])assert.equal(DemandSchema.parse({...DEFAULT_DEMAND,departure_distribution:distribution}).departure_distribution,distribution);
});

test("effective trip estimates match Python half-even rounding and reject rounded-zero demand",()=>{
 assert.equal(effectiveTripCount({trip_target:5,demand_multiplier:0.1}),0);
 assert.equal(effectiveTripCount({trip_target:15,demand_multiplier:0.1}),2);
 assert.equal(effectiveTripCount({trip_target:25,demand_multiplier:0.1}),2);
 assert.equal(DemandSchema.safeParse({...DEFAULT_DEMAND,trip_target:5,demand_multiplier:0.1}).success,false);
 assert.equal(sampleUpperBound({...DEFAULT_DEMAND,trip_target:500,duration_seconds:600}),150_500);
});

test("changed configuration invalidates its saved validation identity",()=>{
 assert.equal(scenarioFingerprint(input),scenarioFingerprint({...input,name:` ${input.name} `}));
 assert.notEqual(scenarioFingerprint(input),scenarioFingerprint({...input,demand:{...input.demand,seed:43}}));
 assert.notEqual(scenarioFingerprint(input),scenarioFingerprint({...input,demand:{...input.demand,trip_target:1_200}}));
});

test("unavailable metrics remain null and zero stays a measured value",()=>{
 const zero=MetricSchema.parse({metric_name:"completed_trips",value:0,unit:"trips",aggregation:"run",calculation_version:"unit-fixture-only"});
 const unavailable={...zero,metric_name:"mean_trip_duration",value:null};
 assert.equal(metricValue(null),"—");assert.equal(metricValue(0),"0");assert.equal(metricValue(Number.POSITIVE_INFINITY),"—");assert.equal(metricValue(8.177659110721789e-10),"8.18e-10");assert.equal(metricValue(-0.0001),"-1.00e-4");
 assert.equal(MetricSchema.safeParse({...zero,value:Number.NaN}).success,false);
 const html=renderToStaticMarkup(createElement(MetricGrid,{metrics:[zero,unavailable]}));
 assert.match(html,/metric-completed_trips/);assert.match(html,/0 <small>trips/);assert.match(html,/No qualifying measurement/);assert.match(html,/Mean completed-trip duration/);
});

test("run status and actual progress reject impossible measurements",()=>{
 const run={id:runId,scenario_id:runId,network_version_id:network,scenario_name:"Unit fixture",status:"running",seed:42,created_at:"2026-10-27T12:00:00Z",started_at:"2026-10-27T12:00:01Z",finished_at:null,worker_id:"unit-fixture-only",engine_version:"unit-fixture-only",input_sha256:"a".repeat(64),error_code:null,error_message:null,progress:{simulated_seconds:30,duration_seconds:600,departed:10,completed:2,active:8},cancel_requested:false,attempt_number:1,retry_of:null,synthetic:true};
 assert.equal(RunSchema.parse(run).progress.simulated_seconds,30);
 assert.equal(RunSchema.safeParse({...run,progress:{...run.progress,completed:11}}).success,false);
 assert.equal(RunSchema.safeParse({...run,progress:{...run.progress,simulated_seconds:601}}).success,false);
 assert.equal(RunSchema.safeParse({...run,status:"complete"}).success,false);
 assert.equal(runIsActive("queued"),true);assert.equal(runIsActive("failed"),false);assert.equal(runIsActive("cancelled"),false);
 const html=renderToStaticMarkup(createElement(RunStatus,{status:"failed"}));assert.match(html,/sim-status-failed/);assert.doesNotMatch(html,/succeeded/);
});

test("count visualization draws only provided samples and handles an empty or zero series",()=>{
 assert.equal(activeCountPath([]),"");
 const zeros=[{time:0,active:0,departed:0,arrived:0}];assert.doesNotMatch(activeCountPath(zeros),/NaN|Infinity/);
 const samples=[{time:0,active:1,departed:1,arrived:0},{time:2,active:3,departed:3,arrived:0}];
 assert.equal((activeCountPath(samples).match(/[ML]/g)??[]).length,samples.length);
 const empty=renderToStaticMarkup(createElement(ActiveVehicleCounts,{points:[]}));assert.match(empty,/No recorded vehicle-count samples/);assert.doesNotMatch(empty,/<svg/);
 const recorded=renderToStaticMarkup(createElement(ActiveVehicleCounts,{points:samples}));assert.match(recorded,/Peak recorded active vehicles/);assert.match(recorded,/>3<\/strong>/);
 const notice=renderToStaticMarkup(createElement(SyntheticNotice));assert.match(notice,/not observed Dubai traffic or RTA data/);
});

test("mutation transport supplies the local intent and stable caller idempotency key without browser credentials",async context=>{
 const original=globalThis.fetch;context.after(()=>{globalThis.fetch=original;});
 let request:RequestInit|undefined;let address:unknown;
 globalThis.fetch=async(url,options)=>{address=url;request=options;return new Response(JSON.stringify(input),{headers:{"Content-Type":"application/json"}});};
 const result=await simulationPost("/scenarios",ScenarioInputSchema,input,"unit-key-only");
 assert.deepEqual(result,input);assert.equal(address,"/api/simulation/scenarios");assert.equal(request?.method,"POST");
 const headers=new Headers(request?.headers);assert.equal(headers.get("X-Earthmind-Intent"),"simulation-write");assert.equal(headers.get("Idempotency-Key"),"unit-key-only");assert.equal(headers.has("Authorization"),false);
});

test("malformed or oversized API bodies and sensitive native error details never become accepted results",async context=>{
 const original=globalThis.fetch;context.after(()=>{globalThis.fetch=original;});
 globalThis.fetch=async()=>new Response(JSON.stringify({detail:"token=not-a-working-unit-secret"}),{status:500});
 await assert.rejects(()=>simulationJSON("/scenarios",ScenarioInputSchema),error=>{assert.ok(error instanceof Error);assert.match(error.message,/HTTP 500/);assert.doesNotMatch(error.message,/not-a-working-unit-secret/);return true;});
 globalThis.fetch=async()=>new Response("{}",{headers:{"Content-Length":String(4*1024*1024+1)}});
 await assert.rejects(()=>simulationJSON("/scenarios",ScenarioInputSchema),/display limit/);
 globalThis.fetch=async()=>new Response(JSON.stringify({unexpected:"unit fixture"}));
 await assert.rejects(()=>simulationJSON("/scenarios",ScenarioInputSchema),/invalid response/);
});


test("published engine logs remain plain bounded text and reject arbitrary run identifiers",async context=>{
 const original=globalThis.fetch;context.after(()=>{globalThis.fetch=original;});
 globalThis.fetch=async()=>new Response("<script>unit fixture</script>\u0000 SUMO ended",{headers:{"Content-Type":"text/plain"}});
 const result=await simulationLog(runId);assert.equal(result,"<script>unit fixture</script> SUMO ended");
 globalThis.fetch=async()=>new Response("<html>invalid</html>",{headers:{"Content-Type":"text/html"}});
 await assert.rejects(()=>simulationLog(runId),/not plain text/);
 await assert.rejects(()=>simulationLog("../../private"),/Invalid simulation run/);
});
