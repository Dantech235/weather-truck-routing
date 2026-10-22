import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, ApiError } from './client';
import type { Place, Plan, PlanRequest, RiskRules } from './types';

const DAY_MS = 24 * 60 * 60 * 1000;

export const queryKeys = {
  geocode: (q: string) => ['geocode', q] as const,
  plan: (id: string) => ['plan', id] as const,
  riskRules: ['risk-rules'] as const,
};

export function normalizeQuery(q: string): string {
  return q.trim().replace(/\s+/g, ' ').toLowerCase();
}

export function useGeocode(query: string) {
  const q = normalizeQuery(query);
  return useQuery({
    queryKey: queryKeys.geocode(q),
    queryFn: ({ signal }) =>
      apiFetch<Place[]>(`/api/v1/geocode/?q=${encodeURIComponent(q)}`, { signal }),
    enabled: q.length >= 3,
    staleTime: DAY_MS,
    gcTime: DAY_MS,
    retry: false,
  });
}

export function useCreatePlan() {
  const client = useQueryClient();
  return useMutation<Plan, ApiError, PlanRequest>({
    mutationFn: (body) =>
      apiFetch<Plan>('/api/v1/plans/', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (plan) => client.setQueryData(queryKeys.plan(plan.id), plan),
  });
}

export function usePlan(id: string | undefined) {
  return useQuery<Plan, ApiError>({
    queryKey: queryKeys.plan(id ?? ''),
    queryFn: ({ signal }) => apiFetch<Plan>(`/api/v1/plans/${id ?? ''}/`, { signal }),
    enabled: Boolean(id),
    staleTime: Infinity,
    retry: (count, error) => error.status >= 500 && count < 2,
  });
}

export function useRiskRules() {
  return useQuery<RiskRules, ApiError>({
    queryKey: queryKeys.riskRules,
    queryFn: ({ signal }) => apiFetch<RiskRules>('/api/v1/risk-rules/', { signal }),
    staleTime: Infinity,
  });
}
