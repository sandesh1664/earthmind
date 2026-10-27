/** Reproducible local copy of the pinned npm package; never downloads provider tiles. */
import { access, cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageRoot = path.dirname(require.resolve("cesium/package.json"));
const dependency = JSON.parse(await readFile(path.join(root, "apps/web/package.json"), "utf8"));
const metadata = JSON.parse(await readFile(path.join(packageRoot, "package.json"), "utf8"));
if (metadata.version !== dependency.dependencies.cesium) {
  throw new Error("Cesium package version differs from the exact workspace dependency");
}
const engineRoot = path.dirname(require.resolve("@cesium/engine/package.json"));
const engine = JSON.parse(await readFile(path.join(engineRoot, "package.json"), "utf8"));
const engineSource = await readFile(path.join(engineRoot, "Source/Scene/GlobeSurfaceTile.js"));
const expectedPatchedSource = "8753d08f6374a2a3e1d1e836c15bcdf4cd8b77d5517236048b5817b91f12ce1c";
if (engine.version !== "26.4.0" || createHash("sha256").update(engineSource).digest("hex") !== expectedPatchedSource) {
  throw new Error("Cesium lifecycle patch is absent or incompatible. Run npm ci; review ADR0011 before upgrading.");
}
const destination = path.join(root, "apps/web/public/cesium");
await mkdir(destination, { recursive: true });
for (const directory of ["Workers", "ThirdParty", "Assets", "Widgets"]) {
  const target = path.join(destination, directory);
  await rm(target, { recursive: true, force: true });
  await cp(path.join(packageRoot, "Build/Cesium", directory), target, { recursive: true });
}
for (const notice of ["LICENSE.md", "ThirdParty.json", "ThirdParty.extra.json"]) {
  await cp(path.join(packageRoot, notice), path.join(destination, notice));
}
await writeFile(path.join(destination, "manifest.json"), JSON.stringify({
  version: metadata.version,
  baseUrl: "/cesium/",
  directories: ["Workers", "ThirdParty", "Assets", "Widgets"],
}, null, 2) + "\n");
console.log(`Verified engine ${engine.version} patch ${expectedPatchedSource}; copied Cesium ${metadata.version} static assets and notices to apps/web/public/cesium`);

// Docker mounts these generated provider artifacts at runtime. Direct Next.js
// development/builds copy only the three public context files, never raw OSM or SUMO data.
const contextRoot=path.join(root,"data/dubai-osm/recovery-v1/context");
let hasContext=true;
try {await access(path.join(contextRoot,"manifest.json"));} catch(error) {
 if(error?.code!=="ENOENT")throw error;
 hasContext=false;
}
if(hasContext){
 const publicContext=path.join(root,"apps/web/public/geography");
 await mkdir(publicContext,{recursive:true});
 for(const name of ["manifest.json","context.geojson","buildings.geojson"]){
  await cp(path.join(contextRoot,name),path.join(publicContext,name));
 }
 console.log("Prepared checksum-validated local OSM context for direct Next.js development");
}
