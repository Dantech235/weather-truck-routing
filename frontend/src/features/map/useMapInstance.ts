import maplibregl, { type Map as MapLibreMap, type StyleSpecification } from 'maplibre-gl';
import { useEffect, useRef, useState, type RefObject } from 'react';

const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const STYLE_TIMEOUT_MS = 5000;

/** Used when the vector style cannot be fetched: OSM raster tiles, muted. */
export const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#e2e8f0' } },
    {
      id: 'osm',
      type: 'raster',
      source: 'osm',
      paint: { 'raster-saturation': -0.8, 'raster-opacity': 0.8 },
    },
  ],
};

function prefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

async function loadStyle(): Promise<string | StyleSpecification> {
  const configured = import.meta.env.VITE_MAP_STYLE_URL as string | undefined;
  const url = configured || (prefersDark() ? DARK_STYLE : LIGHT_STYLE);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), STYLE_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`style HTTP ${res.status}`);
    return (await res.json()) as StyleSpecification;
  } catch {
    return FALLBACK_STYLE;
  } finally {
    window.clearTimeout(timer);
  }
}

/** One MapLibre instance per mounted container, created once. `map` is null until loaded. */
export function useMapInstance(container: RefObject<HTMLDivElement | null>): MapLibreMap | null {
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState<MapLibreMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadStyle().then((style) => {
      const el = container.current;
      if (cancelled || !el || mapRef.current) return;
      const map = new maplibregl.Map({
        container: el,
        style,
        center: [-98.5, 39.5],
        zoom: 3.4,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      mapRef.current = map;
      if (import.meta.env.DEV) {
        // Dev/e2e only: lets Playwright project checkpoints to screen positions.
        (window as unknown as { __truckMap?: MapLibreMap }).__truckMap = map;
      }
      map.once('load', () => {
        if (!cancelled) setReady(map);
      });
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      setReady(null);
    };
  }, [container]);

  return ready;
}
