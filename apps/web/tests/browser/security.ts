/** Public visualization tokens still must never enter logs or retained evidence. */
export function safeBrowserURL(value: string): string {
  try { const url=new URL(value); return `${url.origin}${url.pathname}`; }
  catch { return "[non-URL]"; }
}
export function safeBrowserText(value: string): string {
  return value.replace(/https?:\/\/[^\s"'<>]+/g,safeBrowserURL)
    .replace(/(["']?\b(?:access_?token|token|authorization|api_?key)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&}]+)/gi,"$1[REDACTED]")
    .replace(/\bBearer\s+[A-Za-z0-9._~-]+/gi,"Bearer [REDACTED]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g,"[REDACTED]");
}
