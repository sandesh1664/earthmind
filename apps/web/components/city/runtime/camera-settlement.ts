/** Public camera-pose samples use ECEF meters and unit direction/up vectors. */
export interface CameraPoseSample {
  position: [number,number,number];
  direction: [number,number,number];
  up: [number,number,number];
  viewport: [number,number];
}
function differs(a:CameraPoseSample,b:CameraPoseSample): boolean {
  const distance = Math.hypot(...a.position.map((value,index) => value-b.position[index]!));
  return distance >= 0.05
    || a.direction.some((value,index) => Math.abs(value-b.direction[index]!) >= 1e-7)
    || a.up.some((value,index) => Math.abs(value-b.up[index]!) >= 1e-7)
    || a.viewport.some((value,index) => value !== b.viewport[index]);
}
/**
 * Cesium's native move events also compare frustum/transform at EPSILON15.
 * Here "moving" means a public pose changed by at least 5cm or 1e-7 in a
 * direction/up component. Settled means 350ms without that meaningful change.
 * The anchor changes only on significant movement, so small deltas accumulate.
 */
export class CameraSettlement {
  private anchor: CameraPoseSample | null = null;
  private lastChange = 0;
  private moving = false;
  observe(sample:CameraPoseSample,time:number): {moving:boolean;settledNow:boolean} {
    const previous = this.moving;
    if (this.anchor === null) { this.anchor=sample; this.lastChange=time; }
    else if (differs(sample,this.anchor)) { this.anchor=sample; this.lastChange=time; this.moving=true; }
    else if (time-this.lastChange >= 350) this.moving=false;
    return {moving:this.moving,settledNow:previous && !this.moving};
  }
}
