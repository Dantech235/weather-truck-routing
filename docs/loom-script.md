# Loom walkthrough (~8 min)

Before recording:
- Open the deployed web app (or `localhost:5173`) in Chrome at about 1440 × 900.
- Open `backend/risk/engine.py`, `backend/trips/ranking.py` and a terminal in your editor.
- Open React DevTools → Profiler.
- Pick a departure 2–3 hours ahead so the weather is interesting.

## 0:00 Problem and what the app answers (45 s)

"A dispatcher choosing between routes for a heavy truck cares about the weather **when the truck
gets there**, not when it leaves. Wind that's fine for an empty trailer can tip a 45,000 lb load.
This app compares three truck routes, forecasts each checkpoint at its own ETA, applies
load-weight rules, and recommends the safest route. It explains every decision with the same
numbers you see on screen."

## 0:45 Demo: Dallas → Denver, 45,000 lb, 25 mi (1 m 45 s)

1. Type "Dall" and pick Dallas, TX. Type "Denv" and pick Denver, CO. Set 45,000 lb and 25 mi,
   then click **Plan routes**.
2. Point out the routes drawing in A → B → C, coloured by risk along their length, and the
   checkpoints fading in.
3. Walk through the route cards: the Recommended badge, distance, duration and arrival time, the
   bar of miles by risk level, and the sentence ("No Severe miles and the fewest High miles…").
   Read one "Lost because" line.
4. Hover a card to highlight its route, then click it so the map fits that route.
5. Click a **Severe** checkpoint. In the drawer, read:
   - the wind, gusts ("shown, not scored"), rain and snow;
   - the **forecast hour used**, explaining why rain uses the hour ending after the ETA;
   - the load rule text ("35–44 mph with 45,000 lb > 40,000 lb → Severe").

## 2:30 Change the load to 29,000 lb (1 m)

Resubmit. The same wind is now High instead of Severe, the Severe miles drop, and the
recommendation or its sentence changes. "Same weather, lighter load, different risk: the load
rules only ever raise a level, never lower it."

## 3:30 Heatmap and trucks (1 m)

1. Drag the forecast slider. The corridor heatmap cross-fades hour by hour, and the three truck
   markers move to where each truck would be at that time.
2. Press **Play**: 48 hours in about 19 s. Point at a truck driving into or around the storm.
3. Show the keyboard controls: ←/→ moves 1 h, Shift moves 6 h, Home/End jump to the ends.
4. Copy the plan link and open it in a new window to show it's shareable.

## 4:30 Code tour (1 m 30 s)

1. `risk/rules.py` and `risk/engine.py`: the bands as data, the edge choices (No Travel strictly
   above 1.00 / 3.00), and the load rules. "Pure Python, no Django: a test enforces that."
2. `trips/ranking.py`: the rank key with the No Travel gate. `trips/reasons.py`: the first
   criterion where a route differs from the winner.
3. Terminal: `pytest risk -q` (113 boundary cases) and `pytest -q` (256 tests).

## 6:00 Performance (1 m)

1. React DevTools Profiler: start recording, drag the slider and press Play, then stop. **No
   commits** while scrubbing.
2. Explain why: the heatmap's 49 hours are uploaded once; the slider writes to an hour bus; one
   `requestAnimationFrame` calls `setPaintProperty('heatmap-weight', …)`. Hover and selection
   use `feature-state` and paint properties, and never re-upload geometry.
3. Mention the Lighthouse numbers in `docs/perf/lighthouse.md`.

## 7:00 Architecture, trade-offs, next steps (1 m)

- **Architecture:** React SPA → Django REST on a Vercel Function → TomTom / OpenRouteService /
  Open-Meteo, with Neon Postgres for plans and Redis caches. Provider keys never reach the
  browser.
- **Trade-offs:**
  - Checkpoint spacing versus storm detail (segments take the worse endpoint).
  - Open-Meteo's hourly grid resolution.
  - ORS fallback without departure time or traffic.
  - Cold starts on serverless.
- **Next steps:**
  - Record provider fixtures from live responses.
  - Re-route around No Travel segments.
  - Weather alerts (NWS) as an extra signal.
  - A per-checkpoint confidence based on forecast lead time.
