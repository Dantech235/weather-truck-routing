import type { components } from './schema';

type S = components['schemas'];

export type Plan = S['Plan'];
export type Route = S['Route'];
export type Checkpoint = S['Checkpoint'];
export type Segment = S['Segment'];
export type Metrics = S['Metrics'];
export type Place = S['Place'];
export type PlanRequest = S['PlanRequestRequest'];
export type RiskRules = S['RiskRules'];
export type RiskLevel = S['RiskLevelEnum'];
export type ComponentLevel = S['ComponentLevelEnum'];
export type Heatmap = S['Heatmap'];
