import assert from "node:assert/strict";
import test from "node:test";
import {safeBrowserText,safeBrowserURL} from "./browser/security";

test("browser evidence removes URL query credentials and bearer/JWT values",()=>{
 const example="eyJhbGciOiJub25lIn0.eyJleGFtcGxlIjp0cnVlfQ.exampleSignature";
 const output=safeBrowserText(`GET https://api.cesium.com/v1/assets/2/endpoint?access_token=${example} HTTP 403; Bearer opaque-example-value; {\"accessToken\":\"opaque-example-value\"}`);
 assert.equal(output.includes(example),false);
 assert.equal(output.includes("opaque-example-value"),false);
 assert.match(output,/HTTP 403/);
 assert.equal(safeBrowserURL("https://assets.example/tileset.json?token=opaque-value#secret"),"https://assets.example/tileset.json");
});
