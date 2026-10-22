# Definition of done (spec §13): status

Legend: ✅ done and verified · 🟡 done, with a check that needs your environment · ⬜ needs you

## Logic (40%)

- 🟡 **3 distinct routes for typical US city pairs; fewer only when they truly don't exist, with a
  notice.** Implemented and tested with the alternatives algorithm (dedupe + 4 via-point
  retries, never invents a route) and the "fewer than 3" banner. Still to verify against live
  TomTom: `docs/deploy-vercel.md` step 5, or `python manage.py smoke_plan`.
- ✅ **Checkpoints at exactly 10 / 25 / 50 mi plus origin and destination** (merge < 2 mi;
  property-tested).
- ✅ **Weather selected at each checkpoint's ETA with Open-Meteo hour semantics**; "forecast hour
  used" is shown in the drawer.
- ✅ **Every threshold edge and load rule matches §5**: 113 parametrized risk cases.
- ✅ **Ranking: No Travel gate → Severe → High → avg risk → time**; the worked example passes.
- ✅ **Reason / lost-because strings match the card numbers** (same rounding; tested).

## UI and smoothness (40%)

- ✅ **All routes, checkpoints, risk levels, ETAs and summaries are visible on the map** (popup +
  drawer + cards).
- 🟡 **Heatmap scrubs 0–48 h at ≥ 55 fps with zero React renders per tick.** Zero renders while
  dragging and while playing is proven by `e2e/slider-perf.spec.ts`. The fps must be measured on a
  machine with a GPU (the sandbox is software WebGL). The Profiler screenshot (`docs/perf/profiler.png`)
  needs React DevTools in a real Chrome; steps are in `docs/perf/README.md`.
- ✅ **Hover and selection cause no geometry re-upload** (paint properties + feature-state).
- ✅ **GSAP draw-in, card, drawer and badge animations; reduced motion respected; no leaked
  tweens** (Playwright reduced-motion test; `useGSAP` / matchMedia reverts).
- ✅ **Usable at 375 px width; keyboard accessible** (bottom sheet test, no horizontal scroll,
  Lighthouse a11y 100).

## Code quality (15%)

- ✅ **`risk/` and `ranking.py` are pure with no Django imports** (enforced by a test).
- 🟡 **CI green** (ruff, mypy, pytest with coverage gates, schema validation, eslint, tsc,
  vitest, build, Playwright). Every job passes locally; `.github/workflows/ci.yml` runs on the
  first push to GitHub.
- ✅ **Frontend types generated from the OpenAPI schema** (`npm run gen:api` / `gen:api:file`).

## Docs (5%)

- ✅ **README per §10.**
- ⬜ **Loom recorded per §11**: the script is in `docs/loom-script.md`.
- ⬜ **Hosted URLs live**: deploy with `docs/deploy-vercel.md`, then put both URLs at the top
  of the README.

## Deviations from the brief (documented)

- **Hosting:** Vercel for both the API and the web app (owner's choice), instead of
  Render/Railway + Vercel/Netlify.
- **Rain rate:** `rain + showers` (Open-Meteo puts convective rain in `showers`).
- **Gusts:** use the `ceil(ETA)` hour (Open-Meteo defines them as the preceding-hour maximum).
- **Provider fixtures:** these follow the documented response shapes because the build sandbox
  couldn't reach the providers; replace them with recorded responses.
