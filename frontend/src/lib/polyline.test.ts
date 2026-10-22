import { describe, expect, it } from 'vitest';
import { decodePolyline } from './polyline';

describe('decodePolyline', () => {
  it('decodes the reference example into [lon, lat]', () => {
    const pts = decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@');
    expect(pts).toEqual([
      [-120.2, 38.5],
      [-120.95, 40.7],
      [-126.453, 43.252],
    ]);
  });
  it('handles empty and truncated input', () => {
    expect(decodePolyline('')).toEqual([]);
    expect(() => decodePolyline('_p~iF~')).toThrow('truncated');
  });
});
