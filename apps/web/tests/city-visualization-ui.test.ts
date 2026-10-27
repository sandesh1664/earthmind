import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { VisualizationModeSwitch } from "../components/city/VisualizationModeSwitch";

test("both city modes remain selectable and accurately expose the current mode", () => {
  const engineering = renderToStaticMarkup(createElement(VisualizationModeSwitch, {
    mode:"engineering",onChange:()=>{},
  }));
  assert.match(engineering,/role="group" aria-label="Visualization mode"/);
  assert.match(engineering,/aria-label="Engineering mode" aria-pressed="true"/);
  assert.match(engineering,/aria-label="Realistic city mode" aria-pressed="false"/);
  assert.doesNotMatch(engineering,/disabled/);

  const realistic = renderToStaticMarkup(createElement(VisualizationModeSwitch, {
    mode:"realistic",onChange:()=>{},
  }));
  assert.match(realistic,/aria-label="Engineering mode" aria-pressed="false"/);
  assert.match(realistic,/aria-label="Realistic city mode" aria-pressed="true"/);
  assert.doesNotMatch(realistic,/loaded|verified|photorealistic/);
});
