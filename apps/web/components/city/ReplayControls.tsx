"use client";
import {Pause,Play,RotateCcw,Route,Target,X} from "lucide-react";
import type {VehicleReplay} from "../../hooks/use-vehicle-replay";
import {REPLAY_LIMITS} from "../../lib/replay";

export function ReplayControls({replay,onClose,onMatchNetwork}:{replay:VehicleReplay;onClose:()=>void;onMatchNetwork:()=>void}){
 const {manifest,selected}=replay;
 return <section className="city-replay-controls" data-testid="replay-controls" data-cache-size={replay.cacheSize} aria-label="Recorded SUMO vehicle replay">
  <header><div><Route size={16}/><strong>Recorded vehicle replay</strong><span>SYNTHETIC DEMAND · SUMO OUTPUT · NOT LIVE TRAFFIC</span></div><button type="button" aria-label="Close replay" onClick={onClose}><X size={15}/></button></header>
  {replay.loading&&<p role="status">Loading verified replay manifest…</p>}
  {replay.error&&<p role="alert" data-testid="replay-error">{replay.error} <button type="button" onClick={replay.retry}>Retry replay</button></p>}
  {manifest&&!replay.networkMatches&&<p role="alert">This recording belongs to another network. Vehicles stay hidden until the matching network is selected. <button type="button" onClick={onMatchNetwork}>Select run network</button></p>}
  {manifest&&<>
   <div className="city-replay-timeline"><button type="button" aria-label={replay.playing?"Pause replay":"Play replay"} disabled={!replay.networkMatches||Boolean(replay.error)} onClick={()=>replay.setPlaying(!replay.playing)}>{replay.playing?<Pause size={15}/>:<Play size={15}/>}</button><button type="button" aria-label="Reset replay" onClick={replay.reset}><RotateCcw size={15}/></button>
    <label className="city-replay-scrubber"><span className="sr-only">Replay time</span><input aria-label="Replay time" type="range" min="0" max={manifest.duration_seconds} step="0.1" value={replay.time} onChange={event=>replay.seek(Number(event.target.value))}/></label>
    <output data-testid="replay-time" data-seconds={replay.time.toFixed(3)}>{replay.time.toFixed(1)} / {manifest.duration_seconds.toFixed(1)} s</output>
    <label><span className="sr-only">Replay speed</span><select aria-label="Replay speed" data-testid="replay-speed" value={replay.speed} onChange={event=>replay.setSpeed(Number(event.target.value))}>{[0.5,1,2,5].map(speed=><option value={speed} key={speed}>{speed}×</option>)}</select></label>
   </div>
   <div className="city-replay-facts"><span data-testid="replay-active-count">{replay.activeCount} active at recorded {replay.countTime.toFixed(0)} s</span><span data-testid="replay-rendered-count">{replay.vehicles.length} markers</span><span>{replay.cacheSize} / {REPLAY_LIMITS.cachedChunks} chunks cached</span>{replay.buffering&&<span role="status" data-testid="replay-buffering">Buffering recorded samples…</span>}{replay.recordedVehicleCount>REPLAY_LIMITS.visibleVehicles&&<span role="status">Marker budget {REPLAY_LIMITS.visibleVehicles}; active count includes all recorded vehicles.</span>}</div>
   {replay.selectedId&&<div className="city-replay-selection" data-testid="replay-selected-vehicle" data-position={selected?JSON.stringify({id:selected.id,longitude:selected.longitude,latitude:selected.latitude,time:replay.time}):undefined}><div><strong>Vehicle {replay.selectedId}</strong>{selected?<span>{selected.speed.toFixed(2)} m/s · {(selected.speed*3.6).toFixed(1)} km/h · heading {selected.heading.toFixed(1)}° · {selected.vehicle_class} · {selected.longitude.toFixed(6)}, {selected.latitude.toFixed(6)}</span>:<span>No valid sample for this vehicle at the current replay time.</span>}</div><button type="button" aria-label={replay.follow?"Stop following vehicle":"Follow selected vehicle"} disabled={!selected} aria-pressed={replay.follow} onClick={()=>replay.setFollow(!replay.follow)}><Target size={14}/>{replay.follow?"Following":"Follow"}</button></div>}
   <p className="city-replay-source">Run {manifest.run_id} · EPSG:4326 · {manifest.sample_interval_seconds}s samples. Positions interpolate only between uninterrupted recorded samples; markers disappear at recorded arrivals.</p>
  </>}
 </section>;
}
