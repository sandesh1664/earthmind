/**
 * Camera stops create distinct spatial keys. Keep only observed spatial data:
 * a time-only cache could retain many 25,000-position viewports at once.
 * Active queries still share stable keys and a freshness window.
 */
export const CITY_SPATIAL_QUERY_OPTIONS = {
  staleTime: 15_000,
  refetchOnWindowFocus: false,
  gcTime: 0,
} as const;
