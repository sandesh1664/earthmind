import assert from "node:assert/strict";
import test from "node:test";
import { PublicCityConfigurationError, readPublicCityConfig } from "../lib/city/config";

const publicExample = "public-scoped-visualization-example-only";
test("Next public token convention and the legacy alias resolve to the same allowlisted runtime contract",()=>{
 const next=readPublicCityConfig({NEXT_PUBLIC_CESIUM_ION_TOKEN:publicExample});
 const legacy=readPublicCityConfig({CESIUM_ION_PUBLIC_TOKEN:publicExample});
 assert.deepEqual(next,legacy);
 assert.equal(next.ionPublicToken,publicExample);
 assert.deepEqual(Object.keys(next).sort(),["diagnosticsEnabled","imageryAssetId","imageryMode","ionPublicToken","terrainAssetId"]);
 assert.deepEqual(readPublicCityConfig({NEXT_PUBLIC_CESIUM_ION_TOKEN:` ${publicExample} `,CESIUM_ION_PUBLIC_TOKEN:publicExample}),next);
});
test("conflicting public token aliases fail visibly without including their values",()=>{
 const other="another-public-example-not-a-working-token";
 assert.throws(()=>readPublicCityConfig({NEXT_PUBLIC_CESIUM_ION_TOKEN:publicExample,CESIUM_ION_PUBLIC_TOKEN:other}),error=>{
  assert.ok(error instanceof PublicCityConfigurationError);
  assert.match(error.message,/differ/);
  assert.equal(error.message.includes(publicExample),false);
  assert.equal(error.message.includes(other),false);
  return true;
 });
});
test("private token names never populate the browser visualization token",()=>{
 assert.equal(readPublicCityConfig({CESIUM_ION_SECRET_TOKEN:publicExample,CESIUM_ION_TOKEN:publicExample}).ionPublicToken,null);
});
