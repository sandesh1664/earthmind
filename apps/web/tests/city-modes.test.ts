import assert from "node:assert/strict";
import test from "node:test";
import { effectiveImageryMode, imageryDescription, ionProviderFailure } from "../lib/city/provider-policy";
import type { CityConfig } from "../lib/city/types";

const configured: CityConfig = {imageryMode:"local-osm",ionPublicToken:"public-scoped-test-token",imageryAssetId:3812,terrainAssetId:1,diagnosticsEnabled:false};

test("visualization modes choose their own provider while preserving synthetic scope isolation",()=>{
  assert.equal(effectiveImageryMode(configured,false,"engineering"),"local-osm");
  assert.equal(effectiveImageryMode(configured,false,"realistic"),"ion");
  assert.equal(effectiveImageryMode({...configured,imageryMode:"ion"},false,"engineering"),"local-osm");
  assert.equal(effectiveImageryMode(configured,true,"realistic"),"natural-earth");
  assert.equal(effectiveImageryMode(configured,true,"engineering"),"natural-earth");
  assert.match(imageryDescription({...configured,ionPublicToken:null},false,"realistic"),/blocked: public token missing/);
  assert.match(imageryDescription(configured,false,"engineering"),/no satellite imagery/);
});

test("ion failures distinguish rejected credentials, forbidden assets, unavailable assets and quotas without forwarding secrets",()=>{
  const secret="private-value-must-never-be-shown";
  for(const [status,pattern] of [[401,/token rejected/],[403,/access denied/],[404,/configured asset unavailable/],[410,/configured asset unavailable/],[429,/quota exceeded/]] as const){
    const failure=ionProviderFailure("imagery",{error:{response:{status}},message:`https://provider.invalid/?access_token=${secret}`});
    assert.equal(failure.status,"error");assert.match(failure.message,pattern);assert.match(failure.message,new RegExp(`HTTP ${status}`));
    assert.doesNotMatch(failure.message,new RegExp(secret));assert.doesNotMatch(failure.message,/provider\.invalid/);
  }
  assert.match(ionProviderFailure("buildings",{message:"Request failed with status code: 403"}).message,/access denied/);
  assert.match(ionProviderFailure("terrain",new Error(secret)).message,/unavailable/);
  assert.doesNotMatch(ionProviderFailure("terrain",new Error(secret)).message,new RegExp(secret));
});
