import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** Keep fresh verification runs separate from the retained recovery evidence. */
export const browserEvidenceDirectory = resolve(
  process.env.EARTHMIND_EVIDENCE_DIR ||
    fileURLToPath(new URL("../../../../docs/evidence/recovery", import.meta.url)),
);

export function browserEvidencePath(filename: string): string {
  mkdirSync(browserEvidenceDirectory, { recursive: true });
  return join(browserEvidenceDirectory, filename);
}
