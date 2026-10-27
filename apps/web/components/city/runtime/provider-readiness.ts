/** A failed load stays failed until the user starts a new provider generation. */
export class ProviderReadiness {
  private failed = false;
  private ready = false;

  get hasFailed(): boolean { return this.failed; }

  fail(): boolean {
    if (this.failed) return false;
    this.failed = true;
    return true;
  }

  commitReady(): boolean {
    if (this.failed || this.ready) return false;
    this.ready = true;
    return true;
  }
}

/** Require actual geometry and a further frame after its native preparation. */
export class RenderedGeometryReadiness {
  private settledFrames = 0;
  observe(geometryCount: number, pending: boolean): boolean {
    this.settledFrames = geometryCount > 0 && !pending ? this.settledFrames + 1 : 0;
    return this.settledFrames >= 2;
  }
}

/** A visible tileset's JSON/root metadata alone is not rendered building content. */
export function hasBuildingTileContent(content: unknown): boolean {
  if (typeof content !== "object" || content === null) return false;
  const value = content as Record<string, unknown>;
  if ([value.featuresLength, value.trianglesLength, value.geometryByteLength].some(
    count => typeof count === "number" && Number.isFinite(count) && count > 0,
  )) return true;
  // Composite contents expose their concrete child contents through this public API.
  return Array.isArray(value.innerContents) && value.innerContents.some(hasBuildingTileContent);
}
