import type { ExpressionSpecification, Map as MapLibreMap } from 'maplibre-gl';
import type { Heatmap } from '../../../api/types';

export const HEAT_SOURCE = 'corridor-heat';
export const HEAT_LAYER = 'corridor-heat';
const HOURS = 49;
const MAX_SCORE = 4;
const METERS_PER_MILE = 1609.344;
/** Kernel radius as a multiple of grid spacing: neighbouring kernels overlap into a field. */
const RADIUS_PER_SPACING = 2.2;
/** MapLibre zoom levels use 512 px tiles: metres per pixel at z0 on the equator. */
const EARTH_M_PER_PX_Z0 = 78271.51696;

/** One FeatureCollection with h0…h48 = risk score (unknown → 0) and an `unk` flag. setData once. */
export function heatFeatureCollection(heat: Heatmap): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: 'FeatureCollection',
    features: heat.points.map((pt, i) => {
      const row = heat.risk[i] ?? [];
      const props: Record<string, number | boolean> = { unk: row.some((v) => v < 0) };
      for (let k = 0; k < HOURS; k++) props[`h${k}`] = Math.max(0, row[k] ?? 0);
      return {
        type: 'Feature' as const,
        properties: props,
        geometry: { type: 'Point' as const, coordinates: [pt[0] ?? 0, pt[1] ?? 0] },
      };
    }),
  };
}

/** Cross-fade between hour a and a+1 using paint properties only. */
export function heatWeight(hour: number): ExpressionSpecification {
  const a = Math.min(HOURS - 1, Math.max(0, Math.floor(hour)));
  const b = Math.min(a + 1, HOURS - 1);
  const f = Math.min(1, Math.max(0, hour - a));
  return ['/', ['+', ['*', ['get', `h${a}`], 1 - f], ['*', ['get', `h${b}`], f]], MAX_SCORE];
}

/** Radius ≈ RADIUS_PER_SPACING × grid spacing in pixels at every zoom (exponential base 2). */
export function heatRadius(spacingMi: number, latitude: number): ExpressionSpecification {
  const metersPerPxZ0 = EARTH_M_PER_PX_Z0 * Math.cos((latitude * Math.PI) / 180);
  const pxAtZ0 = (spacingMi * METERS_PER_MILE * RADIUS_PER_SPACING) / metersPerPxZ0;
  return ['interpolate', ['exponential', 2], ['zoom'], 0, pxAtZ0, 22, pxAtZ0 * 2 ** 22];
}

export function addHeatmapLayer(map: MapLibreMap, heat: Heatmap, beforeId?: string): void {
  const lats = heat.points.map((p) => p[1] ?? 0);
  const midLat = lats.length ? (Math.min(...lats) + Math.max(...lats)) / 2 : 39;
  map.addSource(HEAT_SOURCE, { type: 'geojson', data: heatFeatureCollection(heat) });
  map.addLayer(
    {
      id: HEAT_LAYER,
      type: 'heatmap',
      source: HEAT_SOURCE,
      paint: {
        'heatmap-weight': heatWeight(0),
        'heatmap-radius': heatRadius(heat.spacing_mi, midLat),
        // Density of a uniform field ≈ weight × intensity × (kernel overlap); tuned so a
        // Moderate-only area reads yellow and a Severe/No Travel core reads red/purple.
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 3, 0.55, 6, 0.7, 9, 0.85],
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0,
          'rgba(0,0,0,0)',
          0.12,
          'rgba(234,179,8,0)',
          0.25,
          '#EAB308',
          0.5,
          '#F97316',
          0.75,
          '#DC2626',
          1,
          '#4C1D95',
        ],
        'heatmap-opacity': 0.7,
      },
    },
    beforeId,
  );
}

export function removeHeatmapLayer(map: MapLibreMap): void {
  if (map.getLayer(HEAT_LAYER)) map.removeLayer(HEAT_LAYER);
  if (map.getSource(HEAT_SOURCE)) map.removeSource(HEAT_SOURCE);
}

export function paintHeatHour(map: MapLibreMap, hour: number): void {
  if (map.getLayer(HEAT_LAYER))
    map.setPaintProperty(HEAT_LAYER, 'heatmap-weight', heatWeight(hour));
}
