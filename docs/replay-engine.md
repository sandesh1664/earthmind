# Recorded Cesium vehicle replay

The existing mount-owned Viewer is preserved. Replay adds one batched directional
BillboardCollection and a distant PointPrimitiveCollection, rather than thousands
of glTF models or another globe. Glyphs are lightweight annotations anchored in
3D world coordinates; they are not photorealistic volumetric vehicle models.
All positions come from actual completed SUMO output. No random animation,
intervention movement or live RTA feed is substituted.

## Wire format and ownership

The successful run's manifest identifies run/network, EPSG:4326, simulation duration,
sample interval, actual count timeline and ordered chunk descriptors with hashes,
byte sizes, time bounds and sample counts. Each chunk contains full active sampled
frames, exact per-step departure/arrival/teleport events and per-vehicle segment IDs.
Samples include vehicle ID, longitude, latitude, heading, speed and passenger class.

SUMO XY uses the verified retained projection and network offset. Local projection
conversion is cross-checked with actual TraCI convertGeo. Coordinates describe
SUMO's front-bumper center; PostGIS road lines are derived carriageway centerlines.
Lane offsets and native internal junction curves are expected. A display-only1.2m
surface offset places glyphs above the globe; it is not a surveyed vehicle elevation.
Optional terrain uses the globe's available height. Realistic/Engineering, imagery,
buildings, credits, geographic inspector and road selection remain available.

API chunk responses and the Next proxy preserve original verified bytes. The
browser checks SHA256 before parsing/adopting bounded strict samples. Re-encoding
JSON would change its hash and is intentionally avoided for chunk responses.
No client storage URI, filesystem path or arbitrary time-range expression is used.

## Timeline

Controls support play/pause/resume, reset, seek,0.5×/1×/2×/5× speed, vehicle selection
and following. The timeline is simulated seconds. Monotonic foreground elapsed
time advances playback; buffering pauses progression while nearby recordings load.
A seek loads its bounded window, rather than downloading the entire run first.

Only consecutive valid samples for the same vehicle and segment interpolate.
Heading uses its shortest angular change. No movement is extrapolated outside a
valid bracket, across an absent sample, excessive frame gap or teleport segment.
A last known position may be held until an exact recorded end event; missing
position data is not replaced by an invented path. Arrival removes the marker at
its recorded event time. New appearances wait for their first valid sample.
Incomplete vehicles remain visible at their actual final recorded sample, rather
than being mislabeled as arrived. Linear two-second position interpolation is a
visual approximation, not a recorded subsecond lane path or surveyed accuracy.

React owns playback/configuration/selection and validated chunk data. The native
VehicleReplayLayer owns billboards, points, GPU resources and camera following.
Vehicle picks are native Cesium picks; only typed plain values reach React. The
follow camera moves relative to actual selected positions and stops advancing
when no valid selected sample exists. Changing map mode does not recreate the
Viewer or reset replay time. A mismatched network hides replay until matched.

## Resource bounds and verification

The configured cache holds at most3nearby chunks, each at most4MiB. Prefetches are
bounded and stale requests aborted; decoding/in-flight buffers and the SDK scene
add memory beyond serialized cache bytes. Rapid seeks evict unrelated windows.
No full recording is accumulated in an application store. At most1000native markers
are adopted; the selected vehicle is retained when applying this safeguard and
actual recorded active counts remain separately labeled. The target500case uses
actual recording data, not synthetic benchmark markers.

Public Billboard.ready plus completed native frames establish marker resource
readiness. Optional diagnostics expose plain counts, projected in-canvas count,
recent rendered FPS, frame counter, JS heap and actual pick coordinates. Projected
in-canvas count is not a building-occlusion/pixel-visibility measurement. JS heap
excludes GPU allocations; headless/software observations are not hardware FPS.

Collections, terrain subscriptions, camera-follow state, async loaders and pending
requests are disposed or aborted on close/unmount. No Cesium object or credential
is exposed globally. Screenshots and actual performance results are recorded in
[verification](verification-m04.md), including failed attempts. Browser functional
traces remain disabled because they can retain public ion tokens/signed URLs.
