import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import type { TruckPosition } from '../../timeline/truckPosition';

export const TRUCK_SOURCE = 'trucks';
export const TRUCK_LAYER = 'trucks';
export const TRUCK_LABEL_LAYER = 'truck-labels';

export function truckCollection(trucks: TruckPosition[]): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: 'FeatureCollection',
    features: trucks.map((t) => ({
      type: 'Feature' as const,
      properties: {
        label: t.label,
        state: t.state,
        text: t.state === 'arrived' ? `${t.label} · Arrived` : t.label,
      },
      geometry: { type: 'Point' as const, coordinates: t.position },
    })),
  };
}

export function addTruckLayers(map: MapLibreMap, trucks: TruckPosition[]): void {
  map.addSource(TRUCK_SOURCE, { type: 'geojson', data: truckCollection(trucks) });
  map.addLayer({
    id: TRUCK_LAYER,
    type: 'circle',
    source: TRUCK_SOURCE,
    paint: {
      'circle-radius': 9,
      'circle-color': '#0F172A',
      'circle-stroke-color': '#FFFFFF',
      'circle-stroke-width': 2.5,
      'circle-opacity': ['match', ['get', 'state'], 'before', 0.6, 1],
    },
  });
  if (map.getStyle().glyphs) {
    map.addLayer({
      id: TRUCK_LABEL_LAYER,
      type: 'symbol',
      source: TRUCK_SOURCE,
      layout: {
        'text-field': ['get', 'text'],
        'text-size': 11,
        'text-offset': [0, -1.6],
        'text-anchor': 'bottom',
        'text-allow-overlap': true,
        'text-font': ['Open Sans Semibold', 'Noto Sans Regular'],
      },
      paint: { 'text-color': '#0F172A', 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.5 },
    });
  }
}

/** Tiny (one feature per route) — cheap enough to update inside the scrub frame. */
export function updateTrucks(map: MapLibreMap, trucks: TruckPosition[]): void {
  (map.getSource(TRUCK_SOURCE) as GeoJSONSource | undefined)?.setData(truckCollection(trucks));
}

export function removeTruckLayers(map: MapLibreMap): void {
  for (const id of [TRUCK_LABEL_LAYER, TRUCK_LAYER]) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(TRUCK_SOURCE)) map.removeSource(TRUCK_SOURCE);
}
