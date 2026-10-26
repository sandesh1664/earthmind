import type { Bounds, Position } from "../city/types";

export function validPosition(value: readonly number[]): value is Position {
  return value.length === 2 && value.every(Number.isFinite) && Math.abs(value[0] ?? 181) <= 180 && Math.abs(value[1] ?? 91) <= 90;
}
export function flatDegrees(positions: readonly Position[]): number[] {
  if (positions.length < 2 || positions.length > 5_000 || positions.some((p) => !validPosition(p)))
    throw new Error("Geometry has invalid longitude/latitude positions");
  return positions.flatMap(([longitude, latitude]) => [longitude, latitude]);
}
export function positionBounds(positions: readonly Position[]): Bounds {
  if (!positions.length || positions.some((p) => !validPosition(p))) throw new Error("Geometry has no valid positions");
  const xs = positions.map((p) => p[0]), ys = positions.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
export function extentCenter(bounds: Bounds): Position {
  return [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
}
