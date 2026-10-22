import type { RiskLevel, RiskRules } from '../api/types';

/** Mirrors backend risk/rules.py LEVEL_COLORS; replaced at runtime by /risk-rules/. */
export const DEFAULT_COLORS: Record<RiskLevel, string> = {
  LOW: '#22C55E',
  MODERATE: '#EAB308',
  HIGH: '#F97316',
  SEVERE: '#DC2626',
  NO_TRAVEL: '#4C1D95',
  UNKNOWN: '#94A3B8',
};

export const LEVEL_ORDER: RiskLevel[] = [
  'LOW',
  'MODERATE',
  'HIGH',
  'SEVERE',
  'NO_TRAVEL',
  'UNKNOWN',
];

export const DEFAULT_LABELS: Record<RiskLevel, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  SEVERE: 'Severe',
  NO_TRAVEL: 'No Travel',
  UNKNOWN: 'Unknown',
};

/** Non-colour cue so risk is never conveyed by colour alone. */
export const LEVEL_ICONS: Record<RiskLevel, string> = {
  LOW: '●',
  MODERATE: '▲',
  HIGH: '◆',
  SEVERE: '■',
  NO_TRAVEL: '⛔',
  UNKNOWN: '?',
};

let colors: Record<RiskLevel, string> = { ...DEFAULT_COLORS };
let labels: Record<RiskLevel, string> = { ...DEFAULT_LABELS };

/** Adopt colours/labels from the API (single source of truth). */
export function applyRiskRules(rules: RiskRules): void {
  colors = { ...DEFAULT_COLORS, ...(rules.colors as Partial<Record<RiskLevel, string>>) };
  labels = { ...DEFAULT_LABELS, ...(rules.labels as Partial<Record<RiskLevel, string>>) };
}

export function colorOf(level: RiskLevel): string {
  return colors[level];
}

export function labelOf(level: RiskLevel): string {
  return labels[level];
}

/** Text colour with AA contrast on top of the level colour. */
export function onColorOf(level: RiskLevel): string {
  return level === 'MODERATE' || level === 'LOW' || level === 'UNKNOWN' ? '#0F172A' : '#FFFFFF';
}

export function isRiskLevel(value: unknown): value is RiskLevel {
  return typeof value === 'string' && (LEVEL_ORDER as string[]).includes(value);
}
