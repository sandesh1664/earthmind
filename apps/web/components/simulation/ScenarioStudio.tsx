"use client";

import {useMemo,useRef,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {CheckCircle2,ClipboardCheck,Database,Layers3,LoaderCircle,Play,Save} from "lucide-react";
import {DEFAULT_DEMAND,DEMAND_PRESETS,ScenarioInputSchema,ScenarioListSchema,ScenarioSchema,SimulationNetworkListSchema,RunSchema,ValidationSchema,scenarioFingerprint,sampleUpperBound,effectiveTripCount,simulationGet,simulationPost,type Demand,type Scenario,type ScenarioInput} from "../../lib/simulation";
import {DefinitionList,localTime,SimulationError,SyntheticNotice} from "./shared";

export function ScenarioStudio({onOpenRun}:{onOpenRun:(id:string)=>void}){
  const client=useQueryClient();
  const networks=useQuery({queryKey:["simulation","networks"],queryFn:({signal})=>simulationGet("/simulation-networks?limit=100&offset=0",SimulationNetworkListSchema,signal),staleTime:30_000,refetchOnWindowFocus:false});
  const scenarios=useQuery({queryKey:["simulation","scenarios"],queryFn:({signal})=>simulationGet("/scenarios?limit=25&offset=0",ScenarioListSchema,signal),refetchOnWindowFocus:false});
  const [draft,setDraft]=useState<ScenarioInput>({name:"Dubai baseline — synthetic demand",network_version_id:"",demand:{...DEFAULT_DEMAND}});
  const [saved,setSaved]=useState<{scenario:Scenario;fingerprint:string}|null>(null);
  const submission=useRef<{scenarioId:string;key:string}|null>(null);
  const defaultNetwork=networks.data?.items.find(value=>value.validation.valid&&!value.is_synthetic)??networks.data?.items[0];
  const form=useMemo(()=>({...draft,network_version_id:draft.network_version_id||defaultNetwork?.id||""}),[draft,defaultNetwork?.id]);
  const selectedNetwork=networks.data?.items.find(value=>value.id===form.network_version_id);
  const fingerprint=scenarioFingerprint(form);
  const parsed=ScenarioInputSchema.safeParse(form);
  const localErrors=parsed.success?[]:[...new Set(parsed.error.issues.map(issue=>issue.message))];
  const savedMatches=saved?.fingerprint===fingerprint;
  const validation=savedMatches?saved?.scenario.validation:null;
  const updateDemand=<K extends keyof Demand>(key:K,value:Demand[K])=>setDraft(previous=>({...previous,demand:{...previous.demand,[key]:value}}));
  const save=useMutation({mutationFn:async()=>{const input=ScenarioInputSchema.parse(form);return {scenario:await simulationPost("/scenarios",ScenarioSchema,input),fingerprint:scenarioFingerprint(input)};},onSuccess:result=>{setSaved(result);void client.invalidateQueries({queryKey:["simulation","scenarios"]});}});
  const validate=useMutation({mutationFn:async()=>{
    const input=ScenarioInputSchema.parse(form),key=scenarioFingerprint(input);
    const scenario=saved?.fingerprint===key?saved.scenario:await simulationPost("/scenarios",ScenarioSchema,input);
    const report=await simulationPost(`/scenarios/${scenario.id}/validate`,ValidationSchema);
    return {scenario:{...scenario,validation:report},fingerprint:key};
  },onSuccess:result=>{setSaved(result);void client.invalidateQueries({queryKey:["simulation","scenarios"]});}});
  const start=useMutation({mutationFn:async()=>{
    if(!savedMatches||!saved?.scenario.validation.valid)throw new Error("Save and validate this exact scenario before starting SUMO.");
    if(submission.current?.scenarioId!==saved.scenario.id)submission.current={scenarioId:saved.scenario.id,key:crypto.randomUUID()};
    return simulationPost("/simulations",RunSchema,{scenario_id:saved.scenario.id,seed:form.demand.seed},submission.current.key);
  },onSuccess:run=>{submission.current=null;void client.invalidateQueries({queryKey:["simulation","runs"]});onOpenRun(run.id);}});
  const busy=save.isPending||validate.isPending||start.isPending;
  const error=save.error??validate.error??start.error;
  function template(trips:1_000|1_200){setDraft(previous=>({...previous,name:trips===1_000?"Dubai baseline — 1,000 synthetic trips":"Dubai modified — 1,200 synthetic trips",demand:{...previous.demand,trip_target:trips,demand_multiplier:1}}));}
  function load(scenario:Scenario){const input={name:scenario.name,network_version_id:scenario.network_version_id,demand:scenario.demand};setDraft(input);setSaved({scenario,fingerprint:scenarioFingerprint(input)});submission.current=null;save.reset();validate.reset();start.reset();}
  return <section className="sim-workspace" aria-label="Scenario Studio">
    <div className="sim-heading"><div><p className="sim-kicker">M04 / CONTROLLED EXPERIMENTS</p><h2>Scenario Studio</h2><p>Configure reproducible synthetic demand on the verified Dubai SUMO network. Validate the retained inputs, then submit a bounded background run.</p></div></div>
    <SyntheticNotice/>
    {networks.isError&&<SimulationError error={networks.error} retry={()=>void networks.refetch()}/>}
    {error&&<SimulationError error={error}/>}
    <div className="sim-grid">
      <div className="sim-card"><h3><Layers3 size={18}/>Demand configuration</h3>
        <div className="sim-preset-row" aria-label="Experiment templates"><button type="button" onClick={()=>template(1_000)} disabled={busy}>Baseline template · 1,000 trips</button><button type="button" onClick={()=>template(1_200)} disabled={busy}>Modified template · 1,200 trips</button></div>
        <form className="sim-form" style={{marginTop:20}} onSubmit={event=>{event.preventDefault();if(!busy&&parsed.success)save.mutate();}}>
          <label className="sim-full">Scenario name<input aria-label="Scenario name" required maxLength={200} value={form.name} disabled={busy} onChange={event=>setDraft(previous=>({...previous,name:event.target.value}))}/></label>
          <label className="sim-full">SUMO-compatible network<select aria-label="Simulation network" value={form.network_version_id} disabled={busy||networks.isPending} onChange={event=>setDraft(previous=>({...previous,network_version_id:event.target.value}))}>
            {!networks.data?.items.length&&<option value="">{networks.isPending?"Inspecting retained networks…":"No compatible network registered"}</option>}
            {networks.data?.items.map(network=><option value={network.id} key={network.id}>{network.region_name??network.version_label} · {network.version_label}{network.validation.valid?"":" · validation required"}</option>)}
          </select></label>
          <div className="sim-full"><div className="sim-preset-row" aria-label="Synthetic demand presets">{DEMAND_PRESETS.map(preset=><button type="button" key={preset.label} disabled={busy} aria-pressed={form.demand.trip_target===preset.trips} onClick={()=>updateDemand("trip_target",preset.trips)}>{preset.label} · {preset.trips.toLocaleString("en")}</button>)}</div></div>
          <label>Trip target<input aria-label="Vehicle trip target" type="number" min={1} max={5_000} step={1} value={form.demand.trip_target} disabled={busy} onChange={event=>updateDemand("trip_target",Number(event.target.value))}/></label>
          <label>Demand multiplier<input aria-label="Demand multiplier" type="number" min={0.1} max={3} step={0.1} value={form.demand.demand_multiplier} disabled={busy} onChange={event=>updateDemand("demand_multiplier",Number(event.target.value))}/></label>
          <label>Simulation duration (seconds)<input aria-label="Simulation duration seconds" type="number" min={30} max={3_600} step={1} value={form.demand.duration_seconds} disabled={busy} onChange={event=>updateDemand("duration_seconds",Number(event.target.value))}/></label>
          <label>Random seed<input aria-label="Random seed" type="number" min={0} max={2_147_483_647} step={1} value={form.demand.seed} disabled={busy} onChange={event=>updateDemand("seed",Number(event.target.value))}/></label>
          <label>Departure distribution<select aria-label="Departure distribution" value={form.demand.departure_distribution} disabled={busy} onChange={event=>updateDemand("departure_distribution",event.target.value as Demand["departure_distribution"])}><option value="uniform">Uniform · first 70% of horizon</option><option value="poisson">Seeded Poisson departures</option><option value="burst">Initial synthetic burst</option></select></label>
          <label>Vehicle class<select aria-label="Vehicle class" value="passenger" disabled={busy} onChange={()=>{}}><option value="passenger">Passenger vehicles</option></select></label>
          <label>Trajectory sample interval (seconds)<input aria-label="Trajectory sample interval seconds" type="number" min={1} max={10} step={1} value={form.demand.sample_interval_seconds} disabled={busy} onChange={event=>updateDemand("sample_interval_seconds",Number(event.target.value))}/></label>
          <label>Origin–destination policy<select aria-label="Origin destination policy" value="reachable_uniform" disabled={busy} onChange={()=>{}}><option value="reachable_uniform">Uniform reachable edge pairs</option></select></label>
          <p className="sim-card-description sim-full">Route generation checks passenger permissions and reachability against the retained SUMO graph. Uniform departures use the first 70% of the horizon; the Poisson rate targets that mean window, with late requests retained as incomplete. Burst requests start at time zero. These are synthetic assumptions, not measured commuting patterns. Road closures and signal interventions are not offered in M04.</p>
          {!parsed.success&&<div className="sim-warning sim-full" role="status">{localErrors.map(message=><p key={message}>{message}</p>)}</div>}
          <div className="sim-actions sim-full" style={{marginTop:0}}><button type="submit" className="action-button secondary" disabled={busy||!parsed.success}>{save.isPending?<LoaderCircle size={15} className="spin"/>:<Save size={15}/>}Save scenario</button><button type="button" className="action-button secondary" disabled={busy||!parsed.success} onClick={()=>validate.mutate()}>{validate.isPending?<LoaderCircle size={15} className="spin"/>:<ClipboardCheck size={15}/>}Run validation</button><button type="button" className="action-button" disabled={busy||!savedMatches||!validation?.valid} onClick={()=>start.mutate()}>{start.isPending?<LoaderCircle size={15} className="spin"/>:<Play size={15}/>}Start simulation</button></div>
        </form>
        {savedMatches&&saved&&<div className={`sim-validation${validation?.valid?"":" invalid"}`} data-testid="scenario-validation" role="status"><strong>{validation?.valid?<><CheckCircle2 size={13} style={{display:"inline",marginRight:6}}/>Scenario validated</>:"Scenario saved; validation did not pass"}</strong><p>Saved ID: <span className="sim-mono" data-testid="saved-scenario-id">{saved.scenario.id}</span></p><p>Configuration checksum: <span className="sim-mono">{saved.scenario.configuration_checksum}</span></p>{validation?.errors.map(message=><p key={message}>{message}</p>)}{validation?.warnings.map(message=><p key={message}>{message}</p>)}</div>}
        {saved&&!savedMatches&&<p className="sim-note" role="status">The form changed after saving. Validate this configuration before starting a run.</p>}
      </div>
      <div style={{display:"grid",gap:20}}>
        <section className="sim-card"><h3><Database size={17}/>Network provenance</h3>{selectedNetwork?<><DefinitionList items={[["Network version",selectedNetwork.version_label],["Study region",selectedNetwork.region_name??"Not recorded"],["SUMO engine",selectedNetwork.engine_version??"Not verified"],["Mapped edges",selectedNetwork.mapped_edge_count?.toLocaleString("en")??"Not verified"],["Geographic source",selectedNetwork.is_synthetic?"Synthetic fixture":"OSM-derived geography"],["OSM SHA256",<span className="sim-mono" key="source">{selectedNetwork.source_checksum??"Not available"}</span>],["SUMO SHA256",<span className="sim-mono" key="net">{selectedNetwork.network_artifact_sha256??"Not available"}</span>]]}/>{selectedNetwork.validation.errors.map(message=><p className="sim-warning" key={message}>{message}</p>)}{selectedNetwork.validation.warnings.map(message=><p className="sim-note" key={message}>{message}</p>)}</>:<p className="sim-empty">No verified network artifact is available. Existing road geometry alone is insufficient for SUMO execution.</p>}</section>
        <section className="sim-card"><h3>Resource estimate</h3><DefinitionList items={[["Effective demand",`${effectiveTripCount(form.demand).toLocaleString("en")} synthetic trips`],["Simulated horizon",`${form.demand.duration_seconds.toLocaleString("en")} s`],["Sample upper bound",`${sampleUpperBound(form.demand).toLocaleString("en")} vehicle samples`],["Worker concurrency","1 run"],["Wall-clock estimate","Unknown until measured"]]}/><p className="sim-note">The sample count is a conservative configured upper bound, not predicted active traffic or a runtime benchmark. Staggered departures, arrivals and output safeguards reduce actual samples. Invalid or over-budget jobs are rejected explicitly.</p></section>
        <section className="sim-card"><h3>Saved scenarios</h3>{scenarios.isError?<SimulationError error={scenarios.error} retry={()=>void scenarios.refetch()}/>:scenarios.isPending?<p className="sim-loading"><LoaderCircle size={15} className="spin"/>Loading persisted scenarios…</p>:!scenarios.data?.items.length?<p className="sim-empty">No scenarios saved. Configure and validate the first synthetic experiment.</p>:<div className="sim-saved-list">{scenarios.data.items.map(scenario=><button type="button" key={scenario.id} disabled={busy} aria-pressed={savedMatches&&saved?.scenario.id===scenario.id} onClick={()=>load(scenario)}><span>{scenario.name}</span><small>{scenario.demand.trip_target.toLocaleString("en")} trips × {scenario.demand.demand_multiplier} · seed {scenario.demand.seed}</small><small>{localTime(scenario.created_at)}</small></button>)}</div>}<p className="sim-note">Showing the latest {scenarios.data?.items.length??0} of {scenarios.data?.total??0} saved scenarios. Each saved configuration is immutable.</p></section>
      </div>
    </div>
  </section>;
}
export default ScenarioStudio;
