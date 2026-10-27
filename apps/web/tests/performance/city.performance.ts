import { test, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";

test("actual 300-road PostGIS display, selection and repeated viewer cleanup", async ({ page }) => {
  const regionId = process.env.EARTHMIND_CITY_BENCHMARK_REGION_ID;
  const networkId = process.env.EARTHMIND_CITY_BENCHMARK_NETWORK_ID;
  if (!regionId || !networkId) throw new Error("Run scripts/verify_city_performance.py to create and safely clean up the real temporary QA dataset.");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const heap: number[] = [], loadMs: number[] = [], selectionMs: number[] = [];
  const domSamples: {documents:number;nodes:number;jsEventListeners:number}[] = [];
  let baselineCreditStyles: number | null = null;
  for (let cycle=0; cycle<30; cycle++) {
    const start = Date.now();
    if (cycle===0) {
      await page.goto("/");
      await page.getByRole("button",{name:"Overview",exact:true}).click();
      await expect(page.locator(".city-cesium-host canvas")).toHaveCount(0);
      baselineCreditStyles = await page.evaluate(() => [...document.head.querySelectorAll("style")].filter(style => style.textContent?.includes(".cesium-credit-lightbox")).length);
    }
    await page.getByRole("button",{name:"City Explorer",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Dubai digital twin",exact:true})).toBeVisible();
    await page.getByRole("checkbox",{name:"Development datasets",exact:true}).check();
    const regions = page.getByLabel("3D study region",{exact:true});
    await expect(regions.locator(`option[value="${regionId}"]`)).toHaveCount(1);
    await regions.selectOption(regionId);
    await expect(page.getByLabel("3D network version",{exact:true})).toHaveValue(networkId);
    const scene = page.getByTestId("cesium-viewer");
    await expect(scene).toHaveAttribute("data-phase","ready");
    await expect(scene).toHaveAttribute("data-geometry-ready","true",{timeout:60_000});
    await expect(scene).toHaveAttribute("data-road-count","300",{timeout:60_000});
    await expect(scene).toHaveAttribute("data-intersection-count","300");
    await expect(page.locator(".city-synthetic-strip")).toContainText("Synthetic study data");
    expect(await scene.locator("canvas").count()).toBe(1);
    loadMs.push(Date.now()-start);
    const first = page.getByRole("button",{name:"Inspect road provisional:benchmark-e000",exact:true});
    const selected = Date.now();
    await first.click();
    await expect(page.getByTestId("selected-road-identifier")).toHaveText("provisional:benchmark-e000");
    selectionMs.push(Date.now()-selected);
    await page.getByRole("button",{name:"Deselect",exact:true}).click();
    if (cycle===29) await page.screenshot({path:"../../docs/evidence/recovery/benchmark-300-roads.png",fullPage:true});
    await page.getByRole("button",{name:"Overview",exact:true}).click();
    await expect(page.locator(".city-cesium-host canvas")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => [...document.head.querySelectorAll("style")].filter(style => style.textContent?.includes(".cesium-credit-lightbox")).length)).toBe(baselineCreditStyles);
    await page.waitForTimeout(1000); // allow destroyed resources and in-flight health requests to settle before GC
    await session.send("HeapProfiler.collectGarbage");
    const metrics = await session.send("Performance.getMetrics");
    const used = metrics.metrics.find(metric => metric.name==="JSHeapUsedSize")?.value;
    if (used!==undefined) heap.push(used);
    domSamples.push(await session.send("Memory.getDOMCounters") as {documents:number;nodes:number;jsEventListeners:number});
  }
  // Actual graphics renderer, not an inferred claim about the host's Apple GPU.
  await page.getByRole("button",{name:"City Explorer",exact:true}).click();
  await expect(page.getByTestId("cesium-viewer")).toHaveAttribute("data-phase","ready");
  const graphics = await page.locator(".city-cesium-host canvas").evaluate((canvas) => {
    const gl = (canvas as HTMLCanvasElement).getContext("webgl2");
    if (!gl) return {api:"not available",renderer:"not available"};
    const extension = gl.getExtension("WEBGL_debug_renderer_info");
    return {api:String(gl.getParameter(gl.VERSION)), renderer:extension ? String(gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)) : String(gl.getParameter(gl.RENDERER))};
  });
  await mkdir("../../docs/evidence/recovery",{recursive:true});
  await page.getByRole("button",{name:"Overview",exact:true}).click();
  await page.waitForTimeout(2000);
  await session.send("HeapProfiler.collectGarbage");
  const finalMetrics = await session.send("Performance.getMetrics");
  const delayedPostUnmountJSHeapBytes = finalMetrics.metrics.find(metric => metric.name==="JSHeapUsedSize")?.value ?? null;
  const result = {domSamples,delayedPostUnmountJSHeapBytes,dataset:"Temporary project-generated synthetic QA network in actual PostGIS; 300 nodes and 300 roads; not Dubai observations",cycles:30,loadMs,selectionMs,postUnmountCollectedJSHeapBytes:heap,graphics,errors,scope:"Local Chromium/diagnostics-enabled; JS heap excludes GPU allocations; thirty cycles are not a long-duration leak or production throughput benchmark"};
  await writeFile("../../docs/evidence/recovery/performance-observations.json",JSON.stringify(result,null,2)+"\n");
  expect(errors).toEqual([]);
  expect(loadMs).toHaveLength(30);
  const steadyHeap = heap.slice(-10);
  const steadyDOM = domSamples.slice(-10);
  // A documented bounded local stability gate after twenty warm-up cycles.
  // This does not establish indefinite/GPU memory safety.
  expect(steadyHeap).toHaveLength(10);
  expect(Math.max(...steadyHeap)-Math.min(...steadyHeap)).toBeLessThan(1024*1024);
  expect(Math.max(...steadyDOM.map(value=>value.nodes))-Math.min(...steadyDOM.map(value=>value.nodes))).toBeLessThan(25);
  expect(Math.max(...steadyDOM.map(value=>value.jsEventListeners))-Math.min(...steadyDOM.map(value=>value.jsEventListeners))).toBeLessThan(10);
  expect(selectionMs.every(value=>value<5000)).toBe(true);
});
