import maplibregl, { type MapLayerMouseEvent, type Map as MapLibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Heatmap, Plan } from '../../api/types';
import { boundsOf, type Bounds, type LonLat } from '../../lib/geo';
import { mapBottomInset } from '../../lib/layoutMetrics';
import { DESKTOP_QUERY } from '../../lib/useMediaQuery';
import { decodePolyline } from '../../lib/polyline';
import { routeDrawIn } from '../../animations/timelines';
import { prefersReducedMotion } from '../../animations/useReducedMotion';
import { useTheme } from '../../lib/theme';
import { useUIStore } from '../../store/ui';
import { CheckpointPopup } from '../checkpoint/CheckpointPopup';
import { findCheckpoint } from '../checkpoint/CheckpointDrawer';
import type { HourBus } from '../timeline/hourBus';
import { buildTrack, truckPosition } from '../timeline/truckPosition';
import { addHeatmapLayer, paintHeatHour, removeHeatmapLayer } from './layers/heatmap';
import { addTruckLayers, removeTruckLayers, updateTrucks } from './layers/trucks';
import {
  addCheckpointLayers,
  CHECKPOINT_LAYER,
  paintCheckpointEmphasis,
  removeCheckpointLayers,
} from './layers/checkpoints';
import {
  addRouteLayers,
  paintRouteEmphasis,
  removeRouteLayers,
  riskLayerId,
} from './layers/routes';
import { useMapInstance } from './useMapInstance';

const FIT_DURATION_MS = 900;

function cameraPadding() {
  if (window.matchMedia?.(DESKTOP_QUERY).matches) {
    // Keep routes clear of the floating side panel and the slider dock.
    const panelRight = document.getElementById('planner')?.getBoundingClientRect().right ?? 412;
    const short = window.innerHeight < 600;
    return {
      top: short ? 30 : 60,
      bottom: short ? 120 : 130,
      left: panelRight + 36,
      right: short ? 30 : 60,
    };
  }
  return {
    top: 50,
    bottom: (mapBottomInset() || Math.round(window.innerHeight * 0.5)) + 16,
    left: 30,
    right: 30,
  };
}

function fit(map: MapLibreMap, bounds: Bounds | null) {
  if (!bounds) return;
  map.fitBounds(bounds, { padding: cameraPadding(), duration: FIT_DURATION_MS, maxZoom: 11 });
}

const HOUR_MS = 3_600_000;

export interface MapViewProps {
  plan: Plan | null;
  heatmap: Heatmap | null;
  bus: HourBus;
  /** Epoch ms of slider hour 0 (departure hour, UTC floor). */
  startMs: number;
}

export default function MapView({ plan, heatmap, bus, startMs }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const theme = useTheme((s) => s.resolved);
  const map = useMapInstance(containerRef, theme);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [popupNode, setPopupNode] = useState<HTMLDivElement | null>(null);
  const selectedCheckpoint = useUIStore((s) => s.selectedCheckpoint);

  // Decode geometry once per plan.
  const lines = useMemo(() => {
    const out = new Map<string, LonLat[]>();
    for (const r of plan?.routes ?? []) out.set(r.label, decodePolyline(r.geometry));
    return out;
  }, [plan]);
  const labels = useMemo(() => plan?.routes.map((r) => r.label) ?? [], [plan]);
  const tracks = useMemo(
    () => plan?.routes.map((r) => buildTrack(r, lines.get(r.label) ?? [])) ?? [],
    [plan, lines],
  );

  // Sources + layers: added once per plan, removed on plan change. Never re-created on hover.
  useEffect(() => {
    if (!map || !plan) return;
    const reduce = prefersReducedMotion();
    // Created hidden (progress 0, opacity 0) and revealed by the draw-in timeline.
    addRouteLayers(map, plan.routes, lines, undefined, reduce ? 1 : 0);
    addCheckpointLayers(map, plan.routes, reduce ? 1 : 0);
    const { selectedRoute, hoveredRoute } = useUIStore.getState();
    paintRouteEmphasis(map, labels, selectedRoute, hoveredRoute, CHECKPOINT_LAYER);
    if (reduce) paintCheckpointEmphasis(map, selectedRoute);
    fit(map, boundsOf([...lines.values()]));
    const drawIn = routeDrawIn(map, plan.routes, reduce);
    return () => {
      drawIn.kill();
      popupRef.current?.remove();
      removeCheckpointLayers(map);
      removeRouteLayers(map, labels);
    };
  }, [map, plan, lines, labels]);

  // Hover/selection → paint properties only, outside React's render cycle.
  useEffect(() => {
    if (!map || !plan) return;
    let prevSelected = useUIStore.getState().selectedRoute;
    let prevHovered = useUIStore.getState().hoveredRoute;
    return useUIStore.subscribe((s) => {
      if (s.selectedRoute === prevSelected && s.hoveredRoute === prevHovered) return;
      prevHovered = s.hoveredRoute;
      paintRouteEmphasis(map, labels, s.selectedRoute, s.hoveredRoute, CHECKPOINT_LAYER);
      paintCheckpointEmphasis(map, s.selectedRoute);
      if (s.selectedRoute !== prevSelected) {
        prevSelected = s.selectedRoute;
        const line = s.selectedRoute ? lines.get(s.selectedRoute) : undefined;
        if (line && !s.selectedCheckpoint) fit(map, boundsOf([line]));
      }
    });
  }, [map, plan, labels, lines]);

  // Truck markers: one tiny source, positions driven by the hour bus (no React render).
  useEffect(() => {
    if (!map || !plan || tracks.length === 0) return;
    const at = (hour: number) => tracks.map((t) => truckPosition(t, startMs + hour * HOUR_MS));
    addTruckLayers(map, at(bus.get()));
    const unsubscribe = bus.subscribe((hour) => updateTrucks(map, at(hour)));
    return () => {
      unsubscribe();
      removeTruckLayers(map);
    };
  }, [map, plan, tracks, bus, startMs]);

  // Corridor heatmap: setData once; scrubbing only changes `heatmap-weight` (paint property).
  useEffect(() => {
    if (!map || !plan || !heatmap) return;
    const lowestRouteLayer = map.getStyle().layers.find((l) => l.id.startsWith('route-casing-'));
    addHeatmapLayer(map, heatmap, lowestRouteLayer?.id);
    const unsubscribe = bus.subscribe((hour) => paintHeatHour(map, hour));
    return () => {
      unsubscribe();
      removeHeatmapLayer(map);
    };
  }, [map, plan, heatmap, bus]);

  // Pointer interactions (stable handlers, registered once per plan).
  useEffect(() => {
    if (!map || !plan) return;
    let hoveredId: number | string | undefined;
    const canvas = map.getCanvas();

    const onMove = (e: MapLayerMouseEvent) => {
      const f = e.features?.[0];
      if (!f || f.id === undefined) return;
      if (hoveredId !== undefined && hoveredId !== f.id) {
        map.setFeatureState({ source: 'checkpoints', id: hoveredId }, { hover: false });
      }
      hoveredId = f.id;
      map.setFeatureState({ source: 'checkpoints', id: f.id }, { hover: true });
      canvas.style.cursor = 'pointer';
    };
    const onLeave = () => {
      if (hoveredId !== undefined) {
        map.setFeatureState({ source: 'checkpoints', id: hoveredId }, { hover: false });
      }
      hoveredId = undefined;
      canvas.style.cursor = '';
    };
    const onClickCheckpoint = (e: MapLayerMouseEvent) => {
      const props = e.features?.[0]?.properties as { route?: string; index?: number } | undefined;
      if (props?.route === undefined || props.index === undefined) return;
      e.preventDefault();
      useUIStore.getState().selectCheckpoint({ route: props.route, index: Number(props.index) });
    };
    const routeHandlers = labels.map((label) => {
      const id = riskLayerId(label);
      const click = (e: MapLayerMouseEvent) => {
        if (e.defaultPrevented) return;
        useUIStore.getState().selectRoute(label);
      };
      const enter = () => {
        canvas.style.cursor = 'pointer';
        useUIStore.getState().hoverRoute(label);
      };
      const leave = () => {
        canvas.style.cursor = '';
        useUIStore.getState().hoverRoute(null);
      };
      map.on('click', id, click);
      map.on('mouseenter', id, enter);
      map.on('mouseleave', id, leave);
      return { id, click, enter, leave };
    });

    map.on('mousemove', CHECKPOINT_LAYER, onMove);
    map.on('mouseleave', CHECKPOINT_LAYER, onLeave);
    map.on('click', CHECKPOINT_LAYER, onClickCheckpoint);
    return () => {
      map.off('mousemove', CHECKPOINT_LAYER, onMove);
      map.off('mouseleave', CHECKPOINT_LAYER, onLeave);
      map.off('click', CHECKPOINT_LAYER, onClickCheckpoint);
      for (const h of routeHandlers) {
        map.off('click', h.id, h.click);
        map.off('mouseenter', h.id, h.enter);
        map.off('mouseleave', h.id, h.leave);
      }
    };
  }, [map, plan, labels]);

  // Popup for the selected checkpoint (content rendered by React through a portal).
  const popupCheckpoint =
    plan && selectedCheckpoint
      ? findCheckpoint(plan, selectedCheckpoint.route, selectedCheckpoint.index)
      : undefined;

  useEffect(() => {
    if (!map) return;
    if (!popupCheckpoint) {
      popupRef.current?.remove();
      setPopupNode(null);
      return;
    }
    const node = document.createElement('div');
    const popup = new maplibregl.Popup({ closeButton: false, offset: 12, maxWidth: '240px' })
      .setLngLat([popupCheckpoint.lon, popupCheckpoint.lat])
      .setDOMContent(node)
      .addTo(map);
    popupRef.current?.remove();
    popupRef.current = popup;
    setPopupNode(node);
    map.easeTo({
      center: [popupCheckpoint.lon, popupCheckpoint.lat],
      duration: 500,
      padding: cameraPadding(),
    });
    return () => {
      popup.remove();
    };
  }, [map, popupCheckpoint]);

  return (
    <div className="absolute inset-0">
      <div
        ref={containerRef}
        className="h-full w-full"
        role="region"
        aria-label="Route map. Use the route cards to select a route; checkpoints open details."
      />
      {popupNode &&
        popupCheckpoint &&
        selectedCheckpoint &&
        createPortal(
          <CheckpointPopup route={selectedCheckpoint.route} checkpoint={popupCheckpoint} />,
          popupNode,
        )}
    </div>
  );
}
