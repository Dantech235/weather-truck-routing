# Provider notes (checked against current docs, 2026-10-22)

These fold into the README in Phase 7.

## Open-Meteo (weather)
- Hourly variables: `wind_speed_10m`, `wind_gusts_10m`, `rain`, `showers`, `snowfall`, with
  `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=GMT`, `timeformat=unixtime`,
  `start_hour` / `end_hour` (`yyyy-mm-ddThh:mm`, UTC). Forecasts reach at most 16 days.
- **Deviation from the brief:** Open-Meteo's `rain` is large-scale rain only; convective rain
  (thunderstorms) is reported separately as `showers`. The rain rate used for classification
  is `rain + showers`, otherwise a downpour would read as Low.
- `snowfall` is natively centimetres. Units are read from `hourly_units` on every response and
  converted to inches, so a value is never misread.
- `rain`, `showers`, `snowfall` **and `wind_gusts_10m`** describe the preceding hour, so all four
  use the hour labelled `ceil(ETA)`. `wind_speed_10m` is instantaneous and is interpolated.
- Multi-location responses are a list in request order; a single location is an object.

## TomTom Routing (primary)
- `vehicleWeight` is kilograms (lb × 0.45359237, rounded); `maxAlternatives` is 0–5.
- `departAt` must be in the future, so a departure at or before "now" is sent without
  `departAt` (TomTom then departs now). ETAs always use the requested departure.
- Errors are `{"formatVersion", "detailedError": {"code", "message"}}`; auth/quota errors come
  back as XML, so 401/403 are handled by status only (→ falls back to ORS).

## TomTom Search (geocoding)
- `GET /search/2/search/{query}.json?typeahead=true&limit=6&countrySet=US,CA`.

## OpenRouteService (routing fallback)
- `POST /v2/directions/driving-hgv/geojson`, `Authorization: <key>`, coordinates `[lon, lat]`,
  `options.profile_params.restrictions.weight` in metric tonnes.
- No departure time or live traffic: ETAs use typical speeds from the requested departure.
- Alternative routes are only requested when the straight-line distance is ≤ 55 mi (ORS caps
  alternatives at ~100 km); longer trips get alternatives from via-point requests.

## Nominatim (geocoding fallback)
- Server-side only, ≤ 1 request/second per process, identifying User-Agent, results cached 24 h.

## Test fixtures
- `backend/providers/tests/fixtures/*.json` follow the documented response shapes. They were
  **not** recorded from live calls, because the build environment cannot reach the providers.
  Replace them with recorded responses once network access and keys are available.

## Live gate (Phase 3)
`python manage.py smoke_plan` builds a real Dallas → Denver plan (45,000 lb, 25 mi) and prints
routes, metrics and timings. It needs network access plus `TOMTOM_API_KEY` (or `ORS_API_KEY`).
