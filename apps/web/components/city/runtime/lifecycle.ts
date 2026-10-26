/** Cancels async native-resource adoption after unmount or replacement. */
export class ResourceGeneration {
  private generation = 0;
  private disposed = false;
  next(): number { return ++this.generation; }
  current(generation: number): boolean { return !this.disposed && generation === this.generation; }
  dispose(): void { this.disposed = true; this.generation += 1; }
}

interface OwnedWebGLContext {
  isContextLost(): boolean;
  getExtension(name:"WEBGL_lose_context"): {loseContext():void} | null;
}
/** Destroy SDK-owned resources before explicitly releasing our canvas context. */
export function destroyWithOwnedContext(destroy:() => void,context:OwnedWebGLContext | null): void {
  try { destroy(); }
  finally {
    if (context && !context.isContextLost()) context.getExtension("WEBGL_lose_context")?.loseContext();
  }
}

interface OwnedInputHandler { isDestroyed():boolean; destroy():void }
/** The pinned Viewer guards an already-destroyed public input handler. */
export function destroyWithOwnedInputHandler(handler:OwnedInputHandler,destroyViewer:() => void): void {
  try { if (!handler.isDestroyed()) handler.destroy(); }
  finally { destroyViewer(); }
}

interface CreditStyle { textContent:string | null; remove():void }
/** Only styles synchronously added by our own Viewer constructor are owned. */
export function ownedCreditStyles<T extends CreditStyle>(before:ReadonlySet<T>,after:Iterable<T>):T[] {
  return Array.from(after).filter((style) => !before.has(style) && style.textContent?.includes(".cesium-credit-lightbox"));
}
