"use client";

import {useState} from "react";
import {useMutation,useQuery} from "@tanstack/react-query";
import {ArrowLeftRight,ChartNoAxesCombined,Download,LoaderCircle} from "lucide-react";
import {ComparisonSchema,MetricsSchema,RunListSchema,RunSchema,metricName,metricValue,simulationGet,simulationPost,type SimulationMetrics} from "../../lib/simulation";
import {DefinitionList,MetricGrid,SimulationError,SyntheticNotice} from "./shared";

export function activeCountPath(points:SimulationMetrics["vehicle_counts"],width=960,height=160){
  if(!points.length)return "";
  const duration=Math.max(1,...points.map(point=>point.time)),peak=Math.max(1,...points.map(point=>point.active));
  return points.map((point,index)=>`${index===0?"M":"L"}${(12+point.time/duration*(width-24)).toFixed(2)},${(height-12-point.active/peak*(height-24)).toFixed(2)}`).join(" ");
}
export function ActiveVehicleCounts({points}:{points:SimulationMetrics["vehicle_counts"]}){
  if(!points.length)return <p className="sim-empty">No recorded vehicle-count samples are available.</p>;
  const peak=Math.max(...points.map(point=>point.active)),end=points.at(-1)!.time;
  return <div data-testid="simulation-count-chart"><p className="sim-chart-summary">Peak recorded active vehicles: <strong>{peak.toLocaleString("en")}</strong></p><svg className="sim-count-chart" viewBox="0 0 960 160" role="img" aria-label="Recorded active vehicle count over simulation time" preserveAspectRatio="none"><line x1="12" y1="148" x2="948" y2="148" stroke="#294556"/><path d={activeCountPath(points)} fill="none" stroke="#71d4df" strokeWidth="2" vectorEffect="non-scaling-stroke"/></svg><div className="sim-chart-caption"><span>0 simulated s</span><span>{points.length.toLocaleString("en")} actual samples</span><span>{metricValue(end)} simulated s</span></div></div>;
}

export function SimulationAnalytics({selectedRunId,onSelectRun}:{selectedRunId:string|null;onSelectRun:(id:string)=>void}){
  const runs=useQuery({queryKey:["simulation","analytics-runs"],queryFn:({signal})=>simulationGet("/simulations?limit=100&offset=0",RunListSchema,signal),staleTime:5_000,refetchOnWindowFocus:true});
  const completed=runs.data?.items.filter(run=>run.status==="succeeded")??[];
  const id=selectedRunId??completed[0]?.id??null;
  const run=useQuery({queryKey:["simulation","run",id],enabled:Boolean(id),queryFn:({signal})=>simulationGet(`/simulations/${id}`,RunSchema,signal)});
  const metrics=useQuery({queryKey:["simulation","metrics",id],enabled:run.data?.status==="succeeded",queryFn:({signal})=>simulationGet(`/simulations/${id}/metrics`,MetricsSchema,signal)});
  const [baselineId,setBaselineId]=useState("");const [modifiedId,setModifiedId]=useState("");const [comparisonId,setComparisonId]=useState<string|null>(null);
  const baseline=baselineId||completed[1]?.id||completed[0]?.id||"",modified=modifiedId||completed[0]?.id||"";
  const baseRun=completed.find(item=>item.id===baseline),modifiedRun=completed.find(item=>item.id===modified);
  const compare=useMutation({mutationFn:()=>simulationPost("/comparisons",ComparisonSchema,{baseline_run_id:baseline,modified_run_id:modified}),onSuccess:result=>setComparisonId(result.id)});
  const comparison=useQuery({queryKey:["simulation","comparison",comparisonId],enabled:Boolean(comparisonId),queryFn:({signal})=>simulationGet(`/comparisons/${comparisonId}`,ComparisonSchema,signal)});
  const report=comparison.data??compare.data;
  const differentNetworks=Boolean(baseRun&&modifiedRun&&baseRun.network_version_id!==modifiedRun.network_version_id);
  return <section className="sim-workspace" aria-label="Traffic simulation analytics">
    <div className="sim-heading"><div><p className="sim-kicker">M04 / OUTPUT-BASED ANALYTICS</p><h2>Traffic simulation analytics</h2><p>Inspect actual SUMO measurements and compare controlled synthetic-demand experiments. Completed-trip averages are conditional on completion and are not Dubai traffic predictions.</p></div></div>
    <SyntheticNotice/>
    {runs.error&&<SimulationError error={runs.error} retry={()=>void runs.refetch()}/>}
    <section className="sim-card"><h3><ChartNoAxesCombined size={18}/>Completed run measurements</h3><label className="sim-select-label">Select completed run<select aria-label="Analytics run" value={id??""} onChange={event=>onSelectRun(event.target.value)} disabled={!completed.length}>{!completed.length&&<option value="">{runs.isPending?"Loading persisted runs…":"No successful runs available"}</option>}{completed.map(item=><option key={item.id} value={item.id}>{item.scenario_name} · seed {item.seed} · {item.id.slice(0,8)}</option>)}</select></label>
      {!id?<p className="sim-empty">Run a validated scenario before opening analytics. No results exist until real SUMO output is successfully published.</p>:run.error?<SimulationError error={run.error} retry={()=>void run.refetch()}/>:run.data&&run.data.status!=="succeeded"?<p className="sim-warning">The selected run is {run.data.status}. Completed-run metrics are unavailable; no successful result is inferred.</p>:metrics.isPending?<p className="sim-loading"><LoaderCircle size={15} className="spin"/>Loading recorded run measurements…</p>:metrics.error?<SimulationError error={metrics.error} retry={()=>void metrics.refetch()}/>:metrics.data?<><div style={{marginTop:20}}><MetricGrid metrics={metrics.data.metrics}/></div><p className="sim-note">Values marked — have no qualifying observations. Generated demand, actual departures, completions and incompletes are distinct quantities. Waiting time and time loss come from the declared SUMO calculation version.</p><div className="sim-actions"><a href={`/api/simulation/simulations/${id}/export?format=json`} className="action-button secondary" download><Download size={14}/>Export reproducibility JSON</a><a href={`/api/simulation/simulations/${id}/export?format=csv`} className="action-button secondary" download><Download size={14}/>Export metrics CSV</a></div><h3 style={{marginTop:25}}>Recorded vehicle counts</h3><ActiveVehicleCounts points={metrics.data.vehicle_counts}/>{run.data&&<div style={{marginTop:20}}><DefinitionList items={[["Run",run.data.id],["Engine",run.data.engine_version??"Not recorded"],["Seed",String(run.data.seed)],["Input checksum",<span key="checksum" className="sim-mono">{run.data.input_sha256}</span>]]}/></div>}</>:null}
    </section>
    <section className="sim-card"><h3><ArrowLeftRight size={18}/>Baseline vs modified demand</h3><p className="sim-card-description">Use the same network, engine, seed, simulation duration, departure model and sampling rules. Baseline and modified templates target 1,000 and 1,200 synthetic trips. The service rejects incompatible comparisons.</p>
      <div className="sim-comparison-controls"><label className="sim-select-label">Baseline run<select aria-label="Baseline run" value={baseline} disabled={!completed.length||compare.isPending} onChange={event=>setBaselineId(event.target.value)}>{!completed.length&&<option value="">No successful runs</option>}{completed.map(item=><option value={item.id} key={item.id}>{item.scenario_name} · seed {item.seed} · {item.id.slice(0,8)}</option>)}</select></label><label className="sim-select-label">Modified run<select aria-label="Modified run" value={modified} disabled={!completed.length||compare.isPending} onChange={event=>setModifiedId(event.target.value)}>{!completed.length&&<option value="">No successful runs</option>}{completed.map(item=><option value={item.id} key={item.id}>{item.scenario_name} · seed {item.seed} · {item.id.slice(0,8)}</option>)}</select></label><button type="button" className="action-button" disabled={!baseline||!modified||baseline===modified||differentNetworks||compare.isPending} onClick={()=>compare.mutate()}>{compare.isPending?<LoaderCircle size={15} className="spin"/>:<ArrowLeftRight size={15}/>}Compare runs</button></div>
      {differentNetworks&&<p className="sim-warning" role="status">These runs use different network versions and cannot be compared.</p>}
      {baseRun&&modifiedRun&&baseRun.seed!==modifiedRun.seed&&<p className="sim-warning" role="status">Selected run seeds differ. Choose compatible controlled inputs before comparing.</p>}
      {(compare.error||comparison.error)&&<div style={{marginTop:15}}><SimulationError error={compare.error??comparison.error}/></div>}
      {report&&<div data-testid="simulation-comparison" style={{marginTop:20}}><p className="sim-mono">Comparison {report.id}</p>{report.warnings.map(warning=><p className="sim-warning" key={warning}>{warning}</p>)}<div className="sim-table-scroll"><table className="sim-table"><thead><tr><th scope="col">Metric</th><th scope="col">Baseline</th><th scope="col">Modified</th><th scope="col">Absolute change</th><th scope="col">Percentage change</th></tr></thead><tbody>{report.metrics.map(metric=><tr key={metric.metric_name}><th scope="row">{metricName(metric.metric_name)} <small>({metric.unit})</small></th><td>{metricValue(metric.baseline_value)}</td><td>{metricValue(metric.modified_value)}</td><td>{metricValue(metric.absolute_change)}</td><td>{metric.baseline_value===0||metric.baseline_value===null||metric.modified_value===null?"—":`${metricValue(metric.percentage_change)}${metric.percentage_change===null?"":"%"}`}</td></tr>)}</tbody></table></div><p className="sim-note"><strong>Interpretation:</strong> compare completion and incomplete counts alongside trip averages. A smaller average among fewer completed trips does not establish an improvement. Differences describe this synthetic model and seed; they do not establish causal certainty or predict real-world congestion. Multiple-seed replication remains an extensible research step.</p></div>}
      {!report&&<p className="sim-empty">Select two actual successful runs to compute a persisted comparison. No sample baseline metrics are prefilled.</p>}
    </section>
  </section>;
}
export default SimulationAnalytics;
