"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

export class ViewerErrorBoundary extends Component<
  { children?: ReactNode; retry: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="city-viewer-failure" role="alert">
          <AlertTriangle size={24} />
          <h3>The 3D workspace could not render</h3>
          <p>
            Retry the viewer. Your stored region and network data are preserved.
          </p>
          <button type="button" onClick={this.props.retry}>
            Retry 3D viewer
          </button>
        </div>
      );
    return this.props.children;
  }
}
