import maplibregl, { type MapLayerMouseEvent, type Map as MapLibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Plan } from '../../api/types';
import { boundsOf, type Bounds, type LonLat } from '../../lib/geo';
import { decodePolyline } from '../../lib/polyline';
import { useUIStore } from '../../store/ui';
import { CheckpointPopup } from '../checkpoint/CheckpointPopup';
import { findCheckpoint } from '../checkpoint/CheckpointDrawer';
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

const DESKTOP_MIN_WIDTH = 900;
const FIT_DURATION_MS = 900;

function cameraPadding() {
  if (window.innerWidth >= DESKTOP_MIN_WIDTH) return { top: 60, bottom: 110, left: 420, right: 60 };
  return { top: 50, bottom: Math.round(window.innerHeight * 0.55) + 24, left: 30, right: 30 };
}

function fit(map: MapLibreMap, bounds: Bounds | null) {
  if (!bounds) return;
  map.fitBounds(bounds, { padding: cameraPadding(), duration: FIT_DURATION_MS, maxZoom: 11 });
}

export interface MapViewProps {
  plan: Plan | null;
}

export default function MapView({ plan }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const map = useMapInstance(containerRef);
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

  // Sources + layers: added once per plan, removed on plan change. Never re-created on hover.
  useEffect(() => {
    if (!map || !plan) return;
    addRouteLayers(map, plan.routes, lines, undefined);
    addCheckpointLayers(map, plan.routes);
    const { selectedRoute, hoveredRoute } = useUIStore.getState();
    paintRouteEmphasis(map, labels, selectedRoute, hoveredRoute, CHECKPOINT_LAYER);
    paintCheckpointEmphasis(map, selectedRoute);
    fit(map, boundsOf([...lines.values()]));
    return () => {
      popupRef.current?.remove();
      removeCheckpointLayers(map);
      removeRouteLayers(map, labels);
    };
  }, [map, plan, lines, labels]);

  // Hover/selection → paint properties only, outside React's render cycle.
  useEffect(() => {
    if (!map || !plan) return;
    let prevSelected = useUIStore.getState().selectedRoute;
    return useUIStore.subscribe((s) => {
      paintRouteEmphasis(map, labels, s.selectedRoute, s.hoveredRoute, CHECKPOINT_LAYER);
      paintCheckpointEmphasis(map, s.selectedRoute);
      if (s.selectedRoute !== prevSelected) {
        prevSelected = s.selectedRoute;
        const line = s.selectedRoute ? lines.get(s.selectedRoute) : undefined;
        if (line && !s.selectedCheckpoint) fit(map, boundsOf([line]));
      }
    });
  }, [map, plan, labels, lines]);

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
