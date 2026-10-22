/** Decode a Google encoded polyline into [lon, lat] pairs (GeoJSON order). */
export function decodePolyline(encoded: string, precision = 5): [number, number][] {
  const factor = 10 ** precision;
  const out: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lon = 0;

  const next = (): number => {
    let shift = 0;
    let result = 0;
    let byte = 0x20;
    while (byte >= 0x20) {
      if (index >= encoded.length) throw new Error('truncated polyline');
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    }
    return result & 1 ? ~(result >> 1) : result >> 1;
  };

  while (index < encoded.length) {
    lat += next();
    lon += next();
    out.push([lon / factor, lat / factor]);
  }
  return out;
}
