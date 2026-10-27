import type { Network, Region } from "../geospatial";

/** Synthetic fixture catalogs are an explicit separate mode, never map defaults. */
export function cityRegionsForMode(regions: readonly Region[], development: boolean): Region[] {
  return regions.filter((region) => (region.metadata.is_synthetic === true) === development);
}

export function cityNetworksForMode(networks: readonly Network[], development: boolean): Network[] {
  return networks.filter((network) => network.is_synthetic === development);
}

export function preferredCityRegion(regions: readonly Region[], selectedId: string): Region | null {
  return regions.find((region) => region.id === selectedId)
    ?? regions.find((region) => region.slug === "dubai-downtown-business-bay-osm")
    ?? regions.find((region) => region.metadata.is_synthetic === false)
    ?? regions[0] ?? null;
}
