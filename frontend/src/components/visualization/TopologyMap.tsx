import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useSessionStore } from '../../stores/sessionStore';
import { useUIStore } from '../../stores/uiStore';

type LayerKey =
  | 'runway_surface'
  | 'runway_centerline'
  | 'runway_label'
  | 'taxiway_surface'
  | 'taxiway_centerline'
  | 'taxiway_label'
  | 'stand_surface'
  | 'stand_label';

const layerSources: Record<LayerKey, string> = {
  runway_surface: '/api/spatial/geojson/runway_surface',
  runway_centerline: '/api/spatial/geojson/runway_centerline',
  runway_label: '/api/spatial/geojson/runway_label',
  taxiway_surface: '/api/spatial/geojson/taxiway_surface',
  taxiway_centerline: '/api/spatial/geojson/taxiway_centerline',
  taxiway_label: '/api/spatial/geojson/taxiway_label',
  stand_surface: '/api/spatial/geojson/stand_surface',
  stand_label: '/api/spatial/geojson/stand_label',
};

const baseStyles = {
  runwaySurface: {
    color: '#f85149',
    weight: 1.2,
    opacity: 0.9,
    fillColor: '#f85149',
    fillOpacity: 0.35,
  },
  taxiwaySurface: {
    color: '#4c6a8a',
    weight: 0.8,
    opacity: 0.8,
    fillColor: '#4c6a8a',
    fillOpacity: 0.18,
  },
  standSurface: {
    color: '#1f6feb',
    weight: 0.6,
    opacity: 0.8,
    fillColor: '#1f6feb',
    fillOpacity: 0.22,
  },
  centerline: {
    color: '#f2c94c',
    weight: 1.1,
    opacity: 0.7,
  },
};

const highlightStyles = {
  stand: {
    color: '#ff7b72',
    weight: 2,
    opacity: 0.95,
    fillColor: '#ff7b72',
    fillOpacity: 0.6,
  },
  label: '#ffd166',
};

function normalizeCode(raw: string): string {
  return raw
    .replace(/(滑行道|跑道|机位|机坪|停机位|航班)/g, '')
    .replace(/^(stand_|taxiway_|runway_)/i, '')
    .replace(/\s+/g, '')
    .toUpperCase();
}

function buildCodeSet(values: Array<string | undefined>): Set<string> {
  const set = new Set<string>();
  values
    .filter(Boolean)
    .forEach((value) => {
      const cleaned = normalizeCode(String(value));
      cleaned
        .split('/')
        .map((part) => part.trim())
        .filter(Boolean)
        .forEach((part) => set.add(part));
    });
  return set;
}

function matchesCode(raw: string | undefined, target: Set<string>): boolean {
  if (!raw || target.size === 0) return false;
  const cleaned = normalizeCode(raw);
  return cleaned
    .split('/')
    .map((part) => part.trim())
    .filter(Boolean)
    .some((part) => target.has(part));
}

function safeLabelText(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;');
}

type PlanePlacement = {
  latlng: L.LatLng;
  heading: number;
};

function toLatLng(coords: [number, number]): L.LatLng {
  return L.latLng(coords[1], coords[0]);
}

function getFeatureLabel(feature: any): string {
  const props = (feature?.properties || {}) as Record<string, unknown>;
  return String(props.RESOURCE_C || props.NAME || '').trim();
}

function getFeatures(data: any): any[] {
  return (data?.features || []) as any[];
}

function pointToSegmentDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }) {
  const abx = b.x - a.x;
  const aby = b.y - a.y;
  const apx = p.x - a.x;
  const apy = p.y - a.y;
  const abLen2 = abx * abx + aby * aby;
  if (abLen2 === 0) {
    const dx = p.x - a.x;
    const dy = p.y - a.y;
    return dx * dx + dy * dy;
  }
  const t = Math.max(0, Math.min(1, (apx * abx + apy * aby) / abLen2));
  const projx = a.x + t * abx;
  const projy = a.y + t * aby;
  const dx = p.x - projx;
  const dy = p.y - projy;
  return dx * dx + dy * dy;
}

function computeHeadingFromLine(coords: [number, number][], anchor: L.LatLng): number {
  if (coords.length < 2) return 0;
  const anchorScale = Math.cos((anchor.lat * Math.PI) / 180);
  const anchorXY = {
    x: anchor.lng * anchorScale,
    y: anchor.lat,
  };

  let best: { a: [number, number]; b: [number, number]; dist: number } | null = null;
  for (let i = 0; i < coords.length - 1; i += 1) {
    const a = coords[i];
    const b = coords[i + 1];
    const aXY = { x: a[0] * anchorScale, y: a[1] };
    const bXY = { x: b[0] * anchorScale, y: b[1] };
    const dist = pointToSegmentDistance(anchorXY, aXY, bXY);
    if (!best || dist < best.dist) {
      best = { a, b, dist };
    }
  }
  if (!best) return 0;
  const dx = (best.b[0] - best.a[0]) * anchorScale;
  const dy = best.b[1] - best.a[1];
  const heading = (Math.atan2(dx, dy) * 180) / Math.PI; // 0 = north, 90 = east
  return (heading + 360) % 360;
}

function pickClosestLineFeature(
  lineFeatures: any[],
  anchor: L.LatLng | null,
  codeSet: Set<string>,
): { coords: [number, number][], heading: number } | null {
  const matches = lineFeatures.filter((feature) =>
    matchesCode(getFeatureLabel(feature), codeSet)
  );
  if (matches.length === 0) return null;

  const anchorPoint = anchor || toLatLng((matches[0].geometry?.coordinates?.[0] || [0, 0]) as [number, number]);
  let bestCoords: [number, number][] | null = null;
  let bestHeading = 0;
  let bestDist = Number.POSITIVE_INFINITY;

  matches.forEach((feature) => {
    const geometry = feature.geometry || {};
    const type = geometry.type;
    const lines: [number, number][][] = [];
    if (type === 'LineString') {
      lines.push(geometry.coordinates as [number, number][]);
    } else if (type === 'MultiLineString') {
      lines.push(...(geometry.coordinates as [number, number][][]));
    }
    lines.forEach((coords) => {
      const heading = computeHeadingFromLine(coords, anchorPoint);
      const anchorScale = Math.cos((anchorPoint.lat * Math.PI) / 180);
      const anchorXY = { x: anchorPoint.lng * anchorScale, y: anchorPoint.lat };
      let localBest = Number.POSITIVE_INFINITY;
      for (let i = 0; i < coords.length - 1; i += 1) {
        const a = coords[i];
        const b = coords[i + 1];
        const aXY = { x: a[0] * anchorScale, y: a[1] };
        const bXY = { x: b[0] * anchorScale, y: b[1] };
        const dist = pointToSegmentDistance(anchorXY, aXY, bXY);
        if (dist < localBest) localBest = dist;
      }
      if (localBest < bestDist) {
        bestDist = localBest;
        bestCoords = coords;
        bestHeading = heading;
      }
    });
  });

  if (!bestCoords) return null;
  return { coords: bestCoords, heading: bestHeading };
}

function getPlaneIcon(heading: number, size: number) {
  const svg = `
    <svg width="${size}" height="${size}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M50 4
           C53 4 56 7 56 10
           L56 37
           L85 52
           L85 58
           L56 49
           L56 80
           L64 90
           L64 94
           L50 88
           L36 94
           L36 90
           L44 80
           L44 49
           L15 58
           L15 52
           L44 37
           L44 10
           C44 7 47 4 50 4 Z"
        fill="rgba(230,237,243,0.92)"
        stroke="rgba(9,14,20,0.55)"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
    </svg>
  `;
  const html = `
    <div style="width:${size}px;height:${size}px;transform:rotate(${heading}deg);transform-origin:center;pointer-events:none;">
      ${svg}
    </div>
  `;
  return L.divIcon({
    className: '',
    html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export type TopologyMapHandle = {
  toggleFullscreen: () => Promise<void>;
};

export const TopologyMap = forwardRef<TopologyMapHandle>(function TopologyMap(_, ref) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fullscreenTargetRef = useRef<HTMLDivElement | null>(null);
  const planeLayerRef = useRef<L.Marker | null>(null);
  const layerDataRef = useRef<Record<LayerKey, Record<string, unknown> | null>>({
    runway_surface: null,
    runway_centerline: null,
    runway_label: null,
    taxiway_surface: null,
    taxiway_centerline: null,
    taxiway_label: null,
    stand_surface: null,
    stand_label: null,
  });
  const baseLayersRef = useRef<Record<string, L.Layer>>({});
  const highlightLayersRef = useRef<Record<string, L.Layer>>({});
  const spreadLayerRef = useRef<L.LayerGroup | null>(null);
  const focusKeyRef = useRef<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [layersReady, setLayersReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState<string | null>(null);

  const { incident, spatialAnalysis } = useSessionStore();
  const { bigScreenMode } = useUIStore();

  const getFullscreenElement = () =>
    document.fullscreenElement ||
    // Safari/WebKit
    (document as any).webkitFullscreenElement ||
    (document as any).mozFullScreenElement ||
    (document as any).msFullscreenElement ||
    null;

  const labelFontSize = bigScreenMode ? 12 : 10;
  const labelOpacity = bigScreenMode ? 0.95 : 0.85;

  const highlightSets = useMemo(() => {
    const standTargets = buildCodeSet([
      incident?.position,
      ...(spatialAnalysis?.affected_stands || []),
    ]);
    const taxiwayTargets = buildCodeSet(spatialAnalysis?.affected_taxiways || []);
    const runwayTargets = buildCodeSet(spatialAnalysis?.affected_runways || []);
    return {
      standTargets,
      taxiwayTargets,
      runwayTargets,
    };
  }, [incident?.position, spatialAnalysis]);

  const affectedCodeSets = useMemo(() => {
    return {
      stand: buildCodeSet(spatialAnalysis?.affected_stands || []),
      taxiway: buildCodeSet(spatialAnalysis?.affected_taxiways || []),
      runway: buildCodeSet(spatialAnalysis?.affected_runways || []),
    };
  }, [spatialAnalysis]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      preferCanvas: true,
      zoomControl: true,
      attributionControl: false,
    });
    mapRef.current = map;
    map.setView([30.308, 104.441], 13);

    // Leaflet will render blank/partial layers if its container size changes (layout, split panes,
    // browser zoom, etc.) without an explicit invalidateSize(). Use ResizeObserver for robustness.
    const resizeTarget = containerRef.current;
    let resizeTimer: number | null = null;
    const scheduleInvalidate = () => {
      if (resizeTimer) window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => mapRef.current?.invalidateSize({ pan: false }), 80);
    };
    const resizeObserver = new ResizeObserver(scheduleInvalidate);
    resizeObserver.observe(resizeTarget);
    window.addEventListener('resize', scheduleInvalidate);

    const abortController = new AbortController();

    const loadLayer = async (key: LayerKey) => {
      const apiKey = localStorage.getItem('api_key');
      const headers = apiKey ? { 'X-API-Key': apiKey } : undefined;
      const response = await fetch(layerSources[key], {
        signal: abortController.signal,
        headers,
      });
      if (!response.ok) {
        throw new Error(`加载图层失败: ${key}`);
      }
      return (await response.json()) as Record<string, unknown>;
    };

    const addLabelLayer = (data: Record<string, unknown>, color: string, opacity: number) =>
      L.geoJSON(data as any, {
        pointToLayer: (feature: any, latlng: L.LatLng) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          const label =
            String(props.RESOURCE_C || props.NAME || '')
              .trim();
          if (!label) {
            return L.marker(latlng, { opacity: 0 });
          }
          const html = `<div style="color:${color};font-size:${labelFontSize}px;opacity:${opacity};text-shadow:0 0 2px rgba(0,0,0,0.7);white-space:nowrap;">${safeLabelText(label)}</div>`;
          return L.marker(latlng, {
            icon: L.divIcon({
              className: '',
              html,
            }),
            interactive: false,
          });
        },
      });

    const addBaseLayers = () => {
      const data = layerDataRef.current;
      if (!mapRef.current) return;

      const runwaySurface = L.geoJSON(data.runway_surface as any, {
        style: baseStyles.runwaySurface,
      });
      const taxiwaySurface = L.geoJSON(data.taxiway_surface as any, {
        style: baseStyles.taxiwaySurface,
      });
      const standSurface = L.geoJSON(data.stand_surface as any, {
        style: baseStyles.standSurface,
      });
      const runwayCenterline = L.geoJSON(data.runway_centerline as any, {
        style: baseStyles.centerline,
      });
      const taxiwayCenterline = L.geoJSON(data.taxiway_centerline as any, {
        style: baseStyles.centerline,
      });
      const runwayLabel = addLabelLayer(data.runway_label as any, '#e6edf3', labelOpacity);
      const taxiwayLabel = addLabelLayer(data.taxiway_label as any, '#e6edf3', labelOpacity);
      const standLabel = addLabelLayer(data.stand_label as any, '#e6edf3', labelOpacity);

      baseLayersRef.current = {
        runwaySurface,
        taxiwaySurface,
        standSurface,
        runwayCenterline,
        taxiwayCenterline,
        runwayLabel,
        taxiwayLabel,
        standLabel,
      };

      Object.values(baseLayersRef.current).forEach((layer) => layer.addTo(mapRef.current!));

      const overlayMaps = {
        跑道面: runwaySurface,
        滑行道面: taxiwaySurface,
        机位面: standSurface,
        跑道中线: runwayCenterline,
        滑行道中线: taxiwayCenterline,
        跑道标注: runwayLabel,
        滑行道标注: taxiwayLabel,
        机位标注: standLabel,
      };

      L.control.layers({}, overlayMaps, { collapsed: true }).addTo(mapRef.current!);

      const bounds = standSurface.getBounds();
      if (bounds.isValid()) {
        mapRef.current!.fitBounds(bounds.pad(0.05));
      }
      mapRef.current!.invalidateSize();
    };

    const loadAllLayers = async () => {
      try {
        const entries = await Promise.all(
          (Object.keys(layerSources) as LayerKey[]).map(async (key) => [key, await loadLayer(key)] as const)
        );
        entries.forEach(([key, data]) => {
          layerDataRef.current[key] = data;
        });
        addBaseLayers();
        setIsLoading(false);
        setLayersReady(true);
      } catch (error) {
        if ((error as DOMException)?.name === 'AbortError') {
          return;
        }
        setLoadError(error instanceof Error ? error.message : '地图加载失败');
        setIsLoading(false);
        setLayersReady(false);
      }
    };

    loadAllLayers();

    return () => {
      abortController.abort();
      resizeObserver.disconnect();
      window.removeEventListener('resize', scheduleInvalidate);
      if (resizeTimer) window.clearTimeout(resizeTimer);
      map.remove();
      mapRef.current = null;
    };
  }, [labelFontSize, labelOpacity]);

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const data = layerDataRef.current;

    Object.values(highlightLayersRef.current).forEach((layer) => map.removeLayer(layer));
    highlightLayersRef.current = {};

    if (data.stand_surface && highlightSets.standTargets.size > 0) {
      const standHighlight = L.geoJSON(data.stand_surface as any, {
        filter: (feature: any) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          return matchesCode(String(props.RESOURCE_C || props.NAME || ''), highlightSets.standTargets);
        },
        style: highlightStyles.stand,
      });
      standHighlight.addTo(map);
      highlightLayersRef.current.stand = standHighlight;
    }

    if (data.runway_label && highlightSets.runwayTargets.size > 0) {
      const runwayHighlight = L.geoJSON(data.runway_label as any, {
        filter: (feature: any) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          return matchesCode(String(props.RESOURCE_C || props.NAME || ''), highlightSets.runwayTargets);
        },
        pointToLayer: (feature: any, latlng: L.LatLng) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          const label = String(props.RESOURCE_C || props.NAME || '').trim();
          const html = `<div style="color:${highlightStyles.label};font-size:${labelFontSize + 2}px;font-weight:600;text-shadow:0 0 4px rgba(0,0,0,0.9);white-space:nowrap;">${safeLabelText(label)}</div>`;
          return L.marker(latlng, {
            icon: L.divIcon({ className: '', html }),
            interactive: false,
          });
        },
      });
      runwayHighlight.addTo(map);
      highlightLayersRef.current.runway = runwayHighlight;
    }

    if (data.taxiway_label && highlightSets.taxiwayTargets.size > 0) {
      const taxiwayHighlight = L.geoJSON(data.taxiway_label as any, {
        filter: (feature: any) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          return matchesCode(String(props.RESOURCE_C || props.NAME || ''), highlightSets.taxiwayTargets);
        },
        pointToLayer: (feature: any, latlng: L.LatLng) => {
          const props = (feature?.properties || {}) as Record<string, unknown>;
          const label = String(props.RESOURCE_C || props.NAME || '').trim();
          const html = `<div style="color:${highlightStyles.label};font-size:${labelFontSize + 1}px;font-weight:600;text-shadow:0 0 4px rgba(0,0,0,0.9);white-space:nowrap;">${safeLabelText(label)}</div>`;
          return L.marker(latlng, {
            icon: L.divIcon({ className: '', html }),
            interactive: false,
          });
        },
      });
      taxiwayHighlight.addTo(map);
      highlightLayersRef.current.taxiway = taxiwayHighlight;
    }
  }, [highlightSets, labelFontSize]);

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const data = layerDataRef.current;

    const highlightLayers = Object.values(highlightLayersRef.current);
    if (highlightLayers.length === 0) return;

    const focusKey = [
      ...highlightSets.standTargets,
      ...highlightSets.taxiwayTargets,
      ...highlightSets.runwayTargets,
    ]
      .sort()
      .join('|');

    if (!focusKey || focusKey === focusKeyRef.current) return;
    focusKeyRef.current = focusKey;

    const bounds = highlightLayers.reduce<L.LatLngBounds | null>((acc, layer) => {
      const layerBounds = (layer as L.FeatureGroup).getBounds?.();
      if (!layerBounds || !layerBounds.isValid()) return acc;
      return acc ? acc.extend(layerBounds) : layerBounds;
    }, null);

    if (bounds && bounds.isValid()) {
      map.fitBounds(bounds.pad(0.4));
      // Ensure all vector layers repaint after programmatic zoom/pan.
      map.invalidateSize({ pan: false });
    }
  }, [highlightSets]);

  useEffect(() => {
    if (!mapRef.current || !layersReady) return;
    const map = mapRef.current;
    const data = layerDataRef.current;
    const positionText = String(incident?.position || '').trim();

    if (!positionText) {
      if (planeLayerRef.current) {
        map.removeLayer(planeLayerRef.current);
        planeLayerRef.current = null;
      }
      return;
    }

    const codeSet = buildCodeSet([positionText]);
    const standFeatures = getFeatures(data.stand_surface);
    const taxiwayLabelFeatures = getFeatures(data.taxiway_label);
    const taxiwayLineFeatures = getFeatures(data.taxiway_centerline);
    const runwayLabelFeatures = getFeatures(data.runway_label);
    const runwayLineFeatures = getFeatures(data.runway_centerline);

    let placement: PlanePlacement | null = null;

    const standMatch = standFeatures.find((feature) => matchesCode(getFeatureLabel(feature), codeSet));
    if (standMatch) {
      const bounds = L.geoJSON(standMatch as any).getBounds();
      if (bounds.isValid()) {
        placement = { latlng: bounds.getCenter(), heading: 0 };
      }
    }

    const preferRunway = /跑道|RWY|RUNWAY/i.test(positionText);
    const preferTaxiway = /滑行道|TWY|TAXI/i.test(positionText);

    const resolveLinePlacement = (
      labelFeatures: any[],
      lineFeatures: any[],
    ): PlanePlacement | null => {
      const labelFeature = labelFeatures.find((feature) => matchesCode(getFeatureLabel(feature), codeSet));
      const labelPoint =
        labelFeature?.geometry?.type === 'Point'
          ? toLatLng(labelFeature.geometry.coordinates as [number, number])
          : null;
      const linePick = pickClosestLineFeature(lineFeatures, labelPoint, codeSet);
      if (!linePick) return null;
      let anchor = labelPoint;
      if (!anchor) {
        const bounds = L.latLngBounds(linePick.coords.map((coord) => toLatLng(coord)));
        anchor = bounds.isValid() ? bounds.getCenter() : toLatLng(linePick.coords[0]);
      }
      return {
        latlng: anchor,
        heading: linePick.heading,
      };
    };

    if (!placement) {
      if (preferRunway) {
        placement = resolveLinePlacement(runwayLabelFeatures, runwayLineFeatures)
          || resolveLinePlacement(taxiwayLabelFeatures, taxiwayLineFeatures);
      } else if (preferTaxiway) {
        placement = resolveLinePlacement(taxiwayLabelFeatures, taxiwayLineFeatures)
          || resolveLinePlacement(runwayLabelFeatures, runwayLineFeatures);
      } else {
        placement = resolveLinePlacement(taxiwayLabelFeatures, taxiwayLineFeatures)
          || resolveLinePlacement(runwayLabelFeatures, runwayLineFeatures);
      }
    }

    if (!placement) {
      if (planeLayerRef.current) {
        map.removeLayer(planeLayerRef.current);
        planeLayerRef.current = null;
      }
      return;
    }

    if (planeLayerRef.current) {
      map.removeLayer(planeLayerRef.current);
      planeLayerRef.current = null;
    }

    const planeSize = bigScreenMode ? 76 : 60;
    const icon = getPlaneIcon(placement.heading, planeSize);
    const marker = L.marker(placement.latlng, {
      icon,
      interactive: false,
      keyboard: false,
      zIndexOffset: 1200,
    });
    marker.addTo(map);
    planeLayerRef.current = marker;
  }, [incident?.position, layersReady, bigScreenMode]);

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const data = layerDataRef.current;
    const spread = spatialAnalysis?.spread_animation || [];

    if (!data.stand_surface || !data.taxiway_surface || !data.runway_surface || spread.length === 0) {
      if (spreadLayerRef.current) {
        map.removeLayer(spreadLayerRef.current);
        spreadLayerRef.current = null;
      }
      return;
    }

    const classifyNodes = (nodes: string[]) => {
      const standCodes = new Set<string>();
      const taxiwayCodes = new Set<string>();
      const runwayCodes = new Set<string>();
      nodes.forEach((node) => {
        const normalized = normalizeCode(node);
        if (node.toLowerCase().startsWith('stand_') || affectedCodeSets.stand.has(normalized)) {
          standCodes.add(normalized);
        } else if (node.toLowerCase().startsWith('taxiway_') || affectedCodeSets.taxiway.has(normalized)) {
          taxiwayCodes.add(normalized);
        } else if (node.toLowerCase().startsWith('runway_') || affectedCodeSets.runway.has(normalized)) {
          runwayCodes.add(normalized);
        }
      });
      return { standCodes, taxiwayCodes, runwayCodes };
    };

    const createLayer = (nodes: string[], color: string) => {
      const { standCodes, taxiwayCodes, runwayCodes } = classifyNodes(nodes);
      const group = L.layerGroup();

      if (standCodes.size > 0) {
        L.geoJSON(data.stand_surface as any, {
          filter: (feature: any) => {
            const props = (feature?.properties || {}) as Record<string, unknown>;
            return matchesCode(String(props.RESOURCE_C || props.NAME || ''), standCodes);
          },
          style: {
            color,
            weight: 1.6,
            opacity: 0.9,
            fillColor: color,
            fillOpacity: 0.5,
          },
        }).addTo(group);
      }

      if (taxiwayCodes.size > 0) {
        L.geoJSON(data.taxiway_surface as any, {
          filter: (feature: any) => {
            const props = (feature?.properties || {}) as Record<string, unknown>;
            return matchesCode(String(props.RESOURCE_C || props.NAME || ''), taxiwayCodes);
          },
          style: {
            color,
            weight: 1.4,
            opacity: 0.8,
            fillColor: color,
            fillOpacity: 0.35,
          },
        }).addTo(group);
      }

      if (runwayCodes.size > 0) {
        L.geoJSON(data.runway_surface as any, {
          filter: (feature: any) => {
            const props = (feature?.properties || {}) as Record<string, unknown>;
            return matchesCode(String(props.RESOURCE_C || props.NAME || ''), runwayCodes);
          },
          style: {
            color,
            weight: 1.8,
            opacity: 0.85,
            fillColor: color,
            fillOpacity: 0.35,
          },
        }).addTo(group);
      }

      return group;
    };

    let index = 0;
    const playFrame = () => {
      const step = spread[index];
      if (!step) return;
      if (spreadLayerRef.current) {
        map.removeLayer(spreadLayerRef.current);
      }
      const layer = createLayer(step.nodes, step.color || '#f85149');
      layer.addTo(map);
      spreadLayerRef.current = layer;
      index = (index + 1) % spread.length;
    };

    playFrame();
    const timer = window.setInterval(playFrame, 900);
    return () => {
      window.clearInterval(timer);
      if (spreadLayerRef.current) {
        map.removeLayer(spreadLayerRef.current);
        spreadLayerRef.current = null;
      }
    };
  }, [spatialAnalysis?.spread_animation, affectedCodeSets]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const active = getFullscreenElement() === fullscreenTargetRef.current;
      setIsFullscreen(active);
      if (mapRef.current) {
        setTimeout(() => mapRef.current?.invalidateSize(), 50);
      }
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange as any);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange as any);
    };
  }, []);

  const toggleFullscreen = useCallback(async () => {
    setFullscreenError(null);
    if (!fullscreenTargetRef.current) return;
    try {
      const current = getFullscreenElement();
      if (current) {
        const exit = document.exitFullscreen || (document as any).webkitExitFullscreen;
        if (exit) {
          await exit.call(document);
        } else {
          setFullscreenError('当前浏览器不支持退出全屏');
        }
      } else {
        const el: any = fullscreenTargetRef.current;
        const request = el.requestFullscreen || el.webkitRequestFullscreen;
        if (request) {
          await request.call(el);
        } else {
          setFullscreenError('当前浏览器不支持全屏');
        }
      }
    } catch (error) {
      setFullscreenError(error instanceof Error ? error.message : '进入全屏失败');
    }
  }, []);

  useImperativeHandle(ref, () => ({ toggleFullscreen }), [toggleFullscreen]);

  return (
    <div
      ref={fullscreenTargetRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        background: 'transparent',
      }}
    >
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          borderRadius: isFullscreen ? 0 : '8px',
          overflow: 'hidden',
          background: 'radial-gradient(900px 500px at 15% 10%, #132235 0%, #0d1117 60%)',
          border: '1px solid var(--border)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          // Keep Leaflet layer control at top-right; place fullscreen toggle bottom-right instead.
          right: 12,
          bottom: 'calc(12px + env(safe-area-inset-bottom))',
          display: 'flex',
          gap: 8,
          zIndex: 1200,
          pointerEvents: 'auto',
        }}
      >
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            void toggleFullscreen();
          }}
          style={{
            background: 'rgba(15, 20, 28, 0.85)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: bigScreenMode ? '6px 10px' : '4px 8px',
            fontSize: bigScreenMode ? 12 : 11,
            cursor: 'pointer',
            boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
          }}
        >
          {isFullscreen ? '退出全屏' : '全屏'}
        </button>
      </div>

      {isLoading && !loadError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            fontSize: bigScreenMode ? 14 : 12,
            pointerEvents: 'none',
            background: 'rgba(10, 14, 20, 0.35)',
          }}
        >
          加载天府机场地图...
        </div>
      )}

      {loadError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--danger)',
            fontSize: bigScreenMode ? 14 : 12,
            background: 'rgba(10, 14, 20, 0.5)',
          }}
        >
          {loadError}
        </div>
      )}

      {fullscreenError && (
        <div
          style={{
            position: 'absolute',
            bottom: 12,
            right: 12,
            color: 'var(--danger)',
            fontSize: bigScreenMode ? 12 : 11,
            background: 'rgba(10, 14, 20, 0.65)',
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid var(--border)',
          }}
        >
          {fullscreenError}
        </div>
      )}
    </div>
  );
});
