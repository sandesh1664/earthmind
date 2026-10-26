"use client";

import {
  Compass,
  Focus,
  MoveUpRight,
  Navigation,
  RotateCcw,
  Scan,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { CameraPreset } from "@/lib/city/types";

export const CAMERA_PRESETS: { id: CameraPreset; label: string }[] = [
  { id: "dubai", label: "Dubai overview" },
  { id: "downtown", label: "Downtown Dubai" },
  { id: "business-bay", label: "Business Bay" },
];

export function MapToolbar({
  command,
  disabled,
  hasRegion,
  hasSelection,
}: {
  command: (preset: CameraPreset) => void;
  disabled: boolean;
  hasRegion: boolean;
  hasSelection: boolean;
}) {
  return (
    <div className="city-toolbar" aria-label="Camera controls">
      <div className="city-camera-presets">
        <span>
          <Compass size={13} /> Fly to
        </span>
        {CAMERA_PRESETS.map(({ id, label }) => (
          <button
            type="button"
            key={id}
            onClick={() => command(id)}
            disabled={disabled}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="city-camera-actions">
        <button
          type="button"
          title="Zoom to study region"
          aria-label="Zoom to study region"
          disabled={disabled || !hasRegion}
          onClick={() => command("region")}
        >
          <Focus size={17} />
        </button>
        <button
          type="button"
          title="Zoom to selected feature"
          aria-label="Zoom to selected feature"
          disabled={disabled || !hasSelection}
          onClick={() => command("feature")}
        >
          <Scan size={17} />
        </button>
        <button
          type="button"
          title="Top-down view"
          aria-label="Top-down view"
          disabled={disabled}
          onClick={() => command("top-down")}
        >
          <Navigation size={16} />
        </button>
        <button
          type="button"
          title="Perspective view"
          aria-label="Perspective view"
          disabled={disabled}
          onClick={() => command("perspective")}
        >
          <MoveUpRight size={17} />
        </button>
        <button
          type="button"
          title="Zoom in"
          aria-label="Zoom in"
          disabled={disabled}
          onClick={() => command("zoom-in")}
        >
          <ZoomIn size={17} />
        </button>
        <button
          type="button"
          title="Zoom out"
          aria-label="Zoom out"
          disabled={disabled}
          onClick={() => command("zoom-out")}
        >
          <ZoomOut size={17} />
        </button>
        <button
          type="button"
          title="Reset camera"
          aria-label="Reset camera"
          disabled={disabled}
          onClick={() => command("reset")}
        >
          <RotateCcw size={16} />
        </button>
      </div>
    </div>
  );
}
