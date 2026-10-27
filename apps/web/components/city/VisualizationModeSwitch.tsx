"use client";

import { Layers3, Sun } from "lucide-react";
import type { VisualizationMode } from "@/lib/city/types";

export function VisualizationModeSwitch({
  mode,
  onChange,
}: {
  mode: VisualizationMode;
  onChange: (mode: VisualizationMode) => void;
}) {
  return (
    <div className="city-mode-switch" role="group" aria-label="Visualization mode">
      <button
        type="button"
        aria-label="Engineering mode"
        aria-pressed={mode === "engineering"}
        onClick={() => onChange("engineering")}
        title="Analytical road categories and source-height building geometry"
      >
        <Layers3 size={13} aria-hidden="true" /> Engineering
      </button>
      <button
        type="button"
        aria-label="Realistic city mode"
        aria-pressed={mode === "realistic"}
        onClick={() => onChange("realistic")}
        title="Authorized aerial imagery and Cesium OSM Buildings"
      >
        <Sun size={13} aria-hidden="true" /> Realistic city
      </button>
    </div>
  );
}
