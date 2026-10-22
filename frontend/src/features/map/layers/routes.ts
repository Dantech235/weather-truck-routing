import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import type { Route } from '../../../api/types';
import type { LonLat } from '../../../lib/geo';
import { riskGradient } from '../gradient';

export const routeSourceId = (label: string) => `route-${label}`;
export const casingLayerId = (label: string) => `route-casing-${label}`;
export const riskLayerId = (label: string) => `route-risk-${label}`;

export const OPACITY = { selected: 1, hovered: 0.8, idle: 0.35 } as const;

/** Add one LineString source (lineMetrics) + casing + risk-gradient layer per route. */
export function addRouteLayers(
  map: MapLibreMap,
  routes: Route[],
  lines: Map<string, LonLat[]>,
  beforeId: string | undefined,
  progress = 1,
): void {
  // Draw lower-ranked routes first so the best route sits on top.
  for (const route of [...routes].reverse()) {
    const coords = lines.get(route.label) ?? [];
    map.addSource(routeSourceId(route.label), {
      type: 'geojson',
      lineMetrics: true,
      data: {
        type: 'Feature',
        properties: { label: route.label },
        geometry: { type: 'LineString', coordinates: coords },
      },
    });
    map.addLayer(
      {
        id: casingLayerId(route.label),
        type: 'line',
        source: routeSourceId(route.label),
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#0F172A', 'line-width': 9, 'line-opacity': OPACITY.idle * 0.5 },
      },
      beforeId,
    );
    map.addLayer(
      {
        id: riskLayerId(route.label),
        type: 'line',
        source: routeSourceId(route.label),
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-width': 5,
          'line-opacity': OPACITY.idle,
          'line-gradient': riskGradient(route.segments, progress),
        },
      },
      beforeId,
    );
  }
}

export function removeRouteLayers(map: MapLibreMap, labels: string[]): void {
  for (const label of labels) {
    for (const id of [riskLayerId(label), casingLayerId(label)]) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource(routeSourceId(label))) map.removeSource(routeSourceId(label));
  }
}

/** Paint-only emphasis: no setData, no layer re-creation. */
export function paintRouteEmphasis(
  map: MapLibreMap,
  labels: string[],
  selected: string | null,
  hovered: string | null,
  topBeforeId: string | undefined,
): void {
  for (const label of labels) {
    if (!map.getLayer(riskLayerId(label))) continue;
    const opacity =
      label === selected ? OPACITY.selected : label === hovered ? OPACITY.hovered : OPACITY.idle;
    map.setPaintProperty(riskLayerId(label), 'line-opacity', opacity);
    map.setPaintProperty(casingLayerId(label), 'line-opacity', opacity * 0.5);
    map.setPaintProperty(riskLayerId(label), 'line-width', label === selected ? 6 : 5);
  }
  // Keep the emphasised route above the others (layer order only, no data change).
  for (const label of [hovered, selected]) {
    if (label && map.getLayer(riskLayerId(label))) {
      map.moveLayer(casingLayerId(label), topBeforeId);
      map.moveLayer(riskLayerId(label), topBeforeId);
    }
  }
}

export function setRouteProgress(map: MapLibreMap, route: Route, progress: number): void {
  const id = riskLayerId(route.label);
  if (map.getLayer(id))
    map.setPaintProperty(id, 'line-gradient', riskGradient(route.segments, progress));
}

export function isRouteSource(map: MapLibreMap, label: string): boolean {
  return Boolean(map.getSource(routeSourceId(label)) as GeoJSONSource | undefined);
}
