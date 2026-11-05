import type { Metadata } from "next";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./globals.css";
import "./city.css";
import "./simulation.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "EARTHMIND · Mission control",
  description:
    "AI-Powered Urban Intelligence Platform — geospatial storage and an interactive Dubai 3D viewer.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
