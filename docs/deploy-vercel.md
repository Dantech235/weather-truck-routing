# Deploying to Vercel (API + web app)

Both halves deploy from **one Git repository as two Vercel projects**:

| Project | Root Directory | Framework preset | What Vercel builds |
| --- | --- | --- | --- |
| `truck-api` | `backend` | Django (auto-detected) | One Python 3.12 function from `config.wsgi`, static files on the CDN, daily cron |
| `truck-web` | `frontend` | Vite | Static SPA in `dist/`, every path falls back to `index.html` |

Both builds were verified offline with `vercel build` (CLI 65.1.0): Django 5.2 detected, Python 3.12
from `.python-version`, `scripts/vercel_build.py` run, `collectstatic` run, one `django` function
with `maxDuration: 60`, tests excluded from the bundle, cron registered.

## 1. Push the repository to GitHub

```bash
cd weatherapp
git remote add origin https://github.com/<you>/weather-truck-routing.git
git push -u origin main
```

## 2. Database (and optional Redis)

The API needs Postgres; serverless functions have no persistent disk.

1. Create the `truck-api` project first (step 3), then open **Storage → Create → Neon (Postgres)**
   and connect it to the project. Neon sets `DATABASE_URL` for you.
   Prefer the **pooled** connection string (host contains `-pooler`).
2. Optional: **Upstash Redis** from the same Storage tab, and copy its `rediss://…` URL into
   `REDIS_URL`. Without Redis, geocode/route/weather caches and rate limits are per function
   instance (correct, just less effective).

Migrations run automatically in the build (`scripts/vercel_build.py` → `manage.py migrate`) when
`DATABASE_URL` is present. Set `SKIP_MIGRATIONS=1` if preview deployments share the production
database and you'd rather migrate by hand:

```bash
cd backend && vercel env pull .env.production.local --environment=production
set -a && . ./.env.production.local && set +a
VERCEL=1 python manage.py migrate
```

## 3. API project (`truck-api`)

**Add New → Project → Import** the repo, then:

- **Root Directory:** `backend`
- **Framework Preset:** Django (auto-detected; leave build/install commands empty)
- **Environment variables** (Production and Preview):

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | a long random string (`python -c "import secrets;print(secrets.token_urlsafe(50))"`). **Needed at build time too**: `collectstatic` loads the production settings |
| `TOMTOM_API_KEY` | your TomTom key (routing + search) |
| `ORS_API_KEY` | optional OpenRouteService key (routing fallback) |
| `CORS_ALLOWED_ORIGINS` | `https://truck-web.vercel.app` (your web project's URL; add custom domains comma-separated) |
| `CORS_ALLOWED_ORIGIN_REGEXES` | optional: `^https://truck-web-.*\.vercel\.app$` to allow web preview deployments |
| `CRON_SECRET` | a random string; Vercel Cron sends it as `Authorization: Bearer …` |
| `ALLOWED_HOSTS` | only for custom domains (e.g. `api.example.com`); `*.vercel.app` is added automatically |
| `DATABASE_URL` | set by the Neon integration |
| `REDIS_URL` | optional (Upstash) |

`DJANGO_SETTINGS_MODULE` does **not** need setting: `manage.py` and `config/wsgi.py` select
`config.settings.prod` when Vercel's `VERCEL=1` is present. Never set `PROVIDERS_MODE=fake` in
production; the production settings refuse to start with it.

Deploy, then check:

```bash
curl https://truck-api.vercel.app/api/health/
# {"status":"ok","providers":{"tomtom":true,"ors":false}}
open https://truck-api.vercel.app/api/docs/
```

`backend/vercel.json` configures:

- `functions["config/wsgi.py"].maxDuration = 60`: a cold plan with 4 via-point requests plus
  weather batches typically takes 3–10 s; 60 s leaves headroom on slow provider days.
- `excludeFiles`: tests, fixtures and caches stay out of the function bundle.
- `crons`: `GET /api/v1/internal/purge-expired-plans/` daily at 03:17 UTC (deletes plans older
  than 7 days). Hobby plans allow one daily cron, which is all this needs.

## 4. Web project (`truck-web`)

**Add New → Project → Import** the same repo again:

- **Root Directory:** `frontend`
- **Framework Preset:** Vite (from `frontend/vercel.json`)
- **Environment variables:**

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://truck-api.vercel.app` (no trailing slash) |
| `VITE_MAP_STYLE_URL` | optional: a MapLibre style URL (MapTiler with key, or leave empty for Carto Positron / Dark Matter) |

`VITE_*` values are baked in at build time, so **redeploy the web project after changing them**.
After the first web deploy, put its URL into the API's `CORS_ALLOWED_ORIGINS` and redeploy the
API.

`frontend/vercel.json` rewrites every non-file path to `index.html` (so shared `/plan/<id>` links
load) and marks hashed `/assets/*` as immutable for a year.

## 5. Smoke test the live stack

```bash
# Live Dallas → Denver plan through the deployed API (Phase 3 gate)
curl -s -X POST https://truck-api.vercel.app/api/v1/plans/ \
  -H 'Content-Type: application/json' \
  -d '{"origin":{"label":"Dallas, TX","lat":32.7767,"lon":-96.797},
       "destination":{"label":"Denver, CO","lat":39.7392,"lon":-104.9903},
       "departure":"'"$(date -u -d '+1 hour' +%Y-%m-%dT%H:00:00Z)"'",
       "load_lb":45000,"interval_mi":25}' | python -m json.tool | head -40
```

Then open the web app, plan Dallas → Denver, open a checkpoint, scrub the slider and copy the
plan link into a private window.

## Notes and limits on Vercel

- **Cold starts**: the first request after idle loads Django (~1–2 s). Fluid compute keeps warm
  instances between requests.
- **Timeouts**: provider calls time out at 8 s with 2 retries; the function limit is 60 s.
- **Heatmap**: computed on the first `GET /plans/{id}/heatmap/` (≤ 600 grid points × 49 h, 6
  Open-Meteo batches in parallel) and then stored on the plan, so later loads are a DB read.
- **Rate limits** (20 plans/min, 120 geocodes/min per IP) need `REDIS_URL` to be shared across
  instances.
- **Docker / docker-compose** remain for local development and any container host.
