import type { ExpressionSpecification, Map as MapLibreMap } from 'maplibre-gl';
import type { Route } from '../../../api/types';
import { colorOf } from '../../../lib/risk';

export const CHECKPOINT_SOURCE = 'checkpoints';
export const CHECKPOINT_LAYER = 'checkpoints';
export const CHECKPOINT_LABEL_LAYER = 'checkpoint-labels';

const ID_STRIDE = 10_000;

/** Numeric feature id (required for feature-state) ↔ (route, index). */
export function checkpointFeatureId(routeIdx: number, cpIndex: number): number {
  return routeIdx * ID_STRIDE + cpIndex;
}

export function checkpointCollection(routes: Route[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: 'FeatureCollection',
    features: routes.flatMap((route, routeIdx) =>
      route.checkpoints.map((cp) => ({
        type: 'Feature' as const,
        id: checkpointFeatureId(routeIdx, cp.index),
        properties: {
          route: route.label,
          index: cp.index,
          level: cp.risk.level,
          color: colorOf(cp.risk.level),
          label: `${route.label} · mi ${cp.mile.toFixed(0)}`,
        },
        geometry: { type: 'Point' as const, coordinates: [cp.lon, cp.lat] },
      })),
    ),
  };
}

const radius: ExpressionSpecification = [
  'case',
  ['boolean', ['feature-state', 'hover'], false],
  8,
  5,
];

export function addCheckpointLayers(map: MapLibreMap, routes: Route[], opacity = 1): void {
  map.addSource(CHECKPOINT_SOURCE, { type: 'geojson', data: checkpointCollection(routes) });
  map.addLayer({
    id: CHECKPOINT_LAYER,
    type: 'circle',
    source: CHECKPOINT_SOURCE,
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': radius,
      'circle-stroke-color': '#FFFFFF',
      'circle-stroke-width': 1.5,
      'circle-opacity': opacity,
      'circle-stroke-opacity': opacity,
    },
  });
  if (map.getStyle().glyphs) {
    map.addLayer({
      id: CHECKPOINT_LABEL_LAYER,
      type: 'symbol',
      source: CHECKPOINT_SOURCE,
      minzoom: 8,
      layout: {
        'text-field': ['get', 'label'],
        'text-size': 11,
        'text-offset': [0, 1.2],
        'text-anchor': 'top',
        'text-font': ['Open Sans Regular', 'Noto Sans Regular'],
      },
      paint: { 'text-color': '#0F172A', 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.2 },
    });
  }
}

export function removeCheckpointLayers(map: MapLibreMap): void {
  for (const id of [CHECKPOINT_LABEL_LAYER, CHECKPOINT_LAYER]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource(CHECKPOINT_SOURCE)) map.removeSource(CHECKPOINT_SOURCE);
}

/** Dim checkpoints of non-selected routes (paint only). */
export function paintCheckpointEmphasis(
  map: MapLibreMap,
  selected: string | null,
  visible = 1,
): void {
  if (!map.getLayer(CHECKPOINT_LAYER)) return;
  const opacity: ExpressionSpecification | number = selected
    ? ['case', ['==', ['get', 'route'], selected], visible, visible * 0.35]
    : visible;
  map.setPaintProperty(CHECKPOINT_LAYER, 'circle-opacity', opacity);
  map.setPaintProperty(CHECKPOINT_LAYER, 'circle-stroke-opacity', opacity);
}
