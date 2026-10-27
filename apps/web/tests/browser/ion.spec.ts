import {expect,test,type Page} from "@playwright/test";
import {writeFile} from "node:fs/promises";
import {browserEvidencePath} from "./evidence";
import {safeBrowserText,safeBrowserURL} from "./security";

type Camera={longitude:number;latitude:number;height:number;heading:number;pitch:number;groundFocus:[number,number]|null};
type ProviderResponse={url:string;status:number;contentType:string;resourceType:string;kind:"endpoint"|"imagery-tile"|"building-content"|"external"};
function observe(page:Page,token:string|null){
 const redact=(value:string)=>safeBrowserText(token?value.replaceAll(token,"[REDACTED]"):value);
 const result={consoleErrors:[] as string[],pageErrors:[] as string[],failedRequests:[] as {url:string;error:string}[],responses:[] as ProviderResponse[]};
 page.on("console",message=>{if(message.type()==="error")result.consoleErrors.push(redact(message.text()));});
 page.on("pageerror",error=>result.pageErrors.push(redact(error.message)));
 page.on("requestfailed",request=>result.failedRequests.push({url:safeBrowserURL(request.url()),error:redact(request.failure()?.errorText??"Unknown")}));
 page.on("response",response=>{
  const url=new URL(response.url());
  if(!/^https?:$/.test(url.protocol)||["localhost","127.0.0.1"].includes(url.hostname))return;
  const contentType=response.headers()["content-type"]??"";
  const kind=/\/v1\/assets\/\d+\/endpoint$/.test(url.pathname)?"endpoint"
   :/\.(?:b3dm|glb|cmpt|pnts)$/i.test(url.pathname)||/gltf-binary|cesium\.b3dm/.test(contentType)?"building-content"
   :/^image\//.test(contentType)&&!/logo|credit|badge|icon/i.test(url.pathname)?"imagery-tile":"external";
  result.responses.push({url:safeBrowserURL(response.url()),status:response.status(),contentType:contentType.slice(0,100),resourceType:response.request().resourceType(),kind});
 });
 return result;
}
async function config(page:Page){
 const response=await page.request.get("/api/city/config");expect(response.status()).toBe(200);
 return await response.json() as {ionPublicToken:string|null;imageryAssetId:number;terrainAssetId:number;diagnosticsEnabled:boolean};
}
async function openEngineering(page:Page){
 await page.goto("/");const scene=page.getByTestId("cesium-viewer");
 await expect(page.getByRole("button",{name:"Engineering mode",exact:true})).toHaveAttribute("aria-pressed","true");
 await expect(scene).toHaveAttribute("data-visualization-mode","engineering");
 await expect(scene).toHaveAttribute("data-imagery-status","ready",{timeout:60_000});
 await expect(scene).toHaveAttribute("data-buildings-status","ready",{timeout:60_000});
 await expect.poll(async()=>Number(await scene.getAttribute("data-road-count")),{timeout:60_000}).toBeGreaterThan(0);
 await expect(scene).toHaveAttribute("data-camera-moving","false");return scene;
}
async function pose(page:Page):Promise<Camera>{return JSON.parse(await page.getByTestId("camera-position").getAttribute("data-camera")??"null") as Camera;}
function samePose(a:Camera,b:Camera){
 expect(b.longitude).toBeCloseTo(a.longitude,6);expect(b.latitude).toBeCloseTo(a.latitude,6);
 expect(b.height).toBeCloseTo(a.height,2);expect(b.heading).toBeCloseTo(a.heading,4);expect(b.pitch).toBeCloseTo(a.pitch,4);
}

test("actual ion aerial and OSM building tiles render while mode changes preserve viewer, camera and inspector",async({page},info)=>{
 test.setTimeout(180_000);
 const settings=await config(page);
 test.skip(!settings.ionPublicToken,"Live provider verification is BLOCKED without a locally configured public token; no mocked tiles are substituted.");
 expect(settings.diagnosticsEnabled).toBe(true);
 const observation=observe(page,settings.ionPublicToken);
 let before:Camera|null=null,realistic:Camera|null=null,after:Camera|null=null,selectedId:string|null=null;
 let instance:string|null=null;
 let creditText:string|null=null;
 try{
  const scene=await openEngineering(page);
  expect(observation.responses).toEqual([]);
  instance=await scene.getAttribute("data-viewer-instance-id");expect(instance).toMatch(/^\d+$/);
  let probe:{id:string|null;x:number;y:number;left:number;top:number;width:number;height:number;ready:boolean}|null=null;
  await expect.poll(async()=>{
   probe=await scene.evaluate(element=>{const bounds=element.querySelector("canvas")?.getBoundingClientRect();return {id:element.getAttribute("data-pick-id"),x:Number(element.getAttribute("data-pick-x")),y:Number(element.getAttribute("data-pick-y")),left:bounds?.left??0,top:bounds?.top??0,width:bounds?.width??0,height:bounds?.height??0,ready:element.getAttribute("data-geometry-ready")==="true"&&element.getAttribute("data-camera-moving")==="false"};});
   return probe.ready&&/^[0-9a-f-]{36}$/.test(probe.id??"")&&probe.x>0&&probe.y>0&&probe.x<probe.width&&probe.y<probe.height;
  },{timeout:30_000}).toBe(true);
  if(!probe)throw new Error("Actual native road probe unavailable");
  const point=probe as {x:number;y:number;left:number;top:number};
  await page.mouse.click(point.left+point.x,point.top+point.y);
  await expect(page.getByTestId("selected-feature-id")).toBeVisible();selectedId=await page.getByTestId("selected-feature-id").innerText();
  before=await pose(page);expect(before.groundFocus).not.toBeNull();expect(before.groundFocus![0]).toBeCloseTo(55.2744,3);expect(before.groundFocus![1]).toBeCloseTo(25.1972,3);
  await page.getByRole("button",{name:"Realistic city mode",exact:true}).click();
  await expect(scene).toHaveAttribute("data-visualization-mode","realistic");
  await expect(scene).toHaveAttribute("data-imagery-status","ready",{timeout:100_000});
  await expect(scene).toHaveAttribute("data-buildings-status","ready",{timeout:100_000});
  await expect(scene).toHaveAttribute("data-viewer-instance-id",instance!);
  await expect(scene.locator("canvas")).toHaveCount(1);
  realistic=await pose(page);samePose(before,realistic);
  await expect(page.getByTestId("selected-feature-id")).toHaveText(selectedId);
  await expect(scene).toHaveAttribute("data-local-building-count","0");
  await expect.poll(()=>observation.responses.filter(item=>item.kind==="imagery-tile"&&item.status>=200&&item.status<300).length,{timeout:30_000}).toBeGreaterThan(0);
  await expect.poll(()=>observation.responses.filter(item=>item.kind==="building-content"&&item.status>=200&&item.status<300).length,{timeout:30_000}).toBeGreaterThan(0);
  const credits=page.locator(".cesium-widget-credits");
  await expect(credits).toBeVisible();
  await expect(credits).toContainText("OpenStreetMap contributors");
  if(settings.imageryAssetId===2)await expect(credits).toContainText("Microsoft");
  creditText=safeBrowserText(await credits.innerText());
  if(info.project.name==="mobile"){
   const creditBox=await credits.boundingBox(),inspectorBox=await page.getByTestId("feature-inspector").boundingBox();
   if(!creditBox||!inspectorBox)throw new Error("Actual mobile credits/inspector layout unavailable");
   expect(creditBox.y+creditBox.height).toBeLessThanOrEqual(inspectorBox.y+1);
   await page.screenshot({path:browserEvidencePath("ion-realistic-inspector-mobile.png"),fullPage:true});
  }
  await page.getByRole("button",{name:"Close feature inspector",exact:true}).click();
  await page.screenshot({path:browserEvidencePath(`ion-realistic-${info.project.name}.png`),fullPage:true});
  await page.getByRole("button",{name:"Engineering mode",exact:true}).click();
  await expect(scene).toHaveAttribute("data-visualization-mode","engineering");
  await expect(scene).toHaveAttribute("data-buildings-status","ready",{timeout:60_000});
  await expect(scene).toHaveAttribute("data-local-building-count","402");
  await expect(scene).toHaveAttribute("data-viewer-instance-id",instance!);after=await pose(page);samePose(before,after);
  await page.getByRole("button",{name:"Show feature inspector",exact:true}).click();
  await expect(page.getByTestId("selected-feature-id")).toHaveText(selectedId);
  await page.getByRole("button",{name:"Close feature inspector",exact:true}).click();
  await page.screenshot({path:browserEvidencePath(`ion-engineering-${info.project.name}.png`),fullPage:true});
  expect(observation.pageErrors).toEqual([]);expect(observation.consoleErrors).toEqual([]);
  expect(observation.responses.filter(item=>item.status>=400)).toEqual([]);
  expect(observation.failedRequests.filter(item=>item.error!=="net::ERR_ABORTED")).toEqual([]);
 }finally{
  await writeFile(browserEvidencePath(`ion-live-${info.project.name}.json`),JSON.stringify({scope:"Actual authorized local token and live provider tiles, no geography/tile substitutions, all URLs stripped of query credentials",publicTokenConfigured:Boolean(settings.ionPublicToken),imageryAssetId:settings.imageryAssetId,terrainAssetId:settings.terrainAssetId,viewerInstanceId:instance,before,realistic,after,selectedId,creditText,observation},null,2)+"\n");
 }
});

test("actual unavailable legacy imagery asset produces an actionable visible error without hiding stored roads",async({page},info)=>{
 test.skip(info.project.name!=="desktop","Identical provider endpoint error policy is exercised once on desktop.");
 test.setTimeout(100_000);
 const settings=await config(page);test.skip(!settings.ionPublicToken,"Needs actual ion access; no fake provider error response is used.");
 const observation=observe(page,settings.ionPublicToken);
 await page.route("**/api/city/config",async route=>{const response=await route.fetch();const actual=await response.json() as Record<string,unknown>;await route.fulfill({response,json:{...actual,imageryAssetId:3812}});});
 try{
  const scene=await openEngineering(page);
  await page.getByRole("button",{name:"Realistic city mode",exact:true}).click();
  await expect(scene).toHaveAttribute("data-imagery-status","error",{timeout:60_000});
  await expect(page.locator('.city-provider-notice [role="alert"]')).toContainText(/asset unavailable.*404/i);
  await expect.poll(async()=>Number(await scene.getAttribute("data-road-count"))).toBeGreaterThan(0);
  expect(observation.responses.some(item=>item.status===404&&item.url.endsWith("/v1/assets/3812/endpoint"))).toBe(true);
  await page.screenshot({path:browserEvidencePath("ion-legacy-asset-error-desktop.png"),fullPage:true});
 }finally{
  await writeFile(browserEvidencePath("ion-legacy-asset-error.json"),JSON.stringify({scope:"Controlled configuration selects legacy asset3812; actual remote HTTP404 is not substituted; stored PostGIS geography remains actual",publicTokenConfigured:true,observation},null,2)+"\n");
 }
});
