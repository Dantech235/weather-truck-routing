import { describe, expect, it } from 'vitest';
import { formFieldFor, tripFormSchema } from './schema';

const valid = {
  origin: { label: 'Dallas, TX', lat: 32.7767, lon: -96.797 },
  destination: { label: 'Denver, CO', lat: 39.7392, lon: -104.9903 },
  departureLocal: '2026-10-22T13:00',
  load: '45,000',
  interval: 25 as const,
};

describe('tripFormSchema', () => {
  it('accepts a complete form', () => {
    expect(tripFormSchema.safeParse(valid).success).toBe(true);
  });
  it.each([
    [{ origin: null }, 'origin'],
    [{ destination: null }, 'destination'],
    [{ load: '' }, 'load'],
    [{ load: '0' }, 'load'],
    [{ load: '120,001' }, 'load'],
    [{ departureLocal: '' }, 'departureLocal'],
    [{ interval: 30 }, 'interval'],
  ])('rejects %o', (patch, field) => {
    const r = tripFormSchema.safeParse({ ...valid, ...patch });
    expect(r.success).toBe(false);
    if (!r.success) expect(r.error.issues[0]?.path[0]).toBe(field);
  });
});

describe('formFieldFor', () => {
  it('maps API fields to form fields', () => {
    expect(formFieldFor('origin.lat')).toBe('origin');
    expect(formFieldFor('departure')).toBe('departureLocal');
    expect(formFieldFor('load_lb')).toBe('load');
    expect(formFieldFor('interval_mi')).toBe('interval');
    expect(formFieldFor('nope')).toBeNull();
    expect(formFieldFor(null)).toBeNull();
  });
});
