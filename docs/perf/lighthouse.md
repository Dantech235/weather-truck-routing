# Lighthouse (desktop preset), production build

Measured on 2026-10-22 against `vite preview` with the backend in fake-provider mode
(`npx lighthouse <url> --preset=desktop`).

| Page | Performance | Accessibility | Best practices | SEO | LCP | TBT | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/` (planner) | **90–93** | **100** | 96 | 100 | 0.7–0.8 s | 200–260 ms | 0 |
| `/plan/:id` (map + 3 routes + heatmap) | 70 | **100** | 96 | 100 | 0.8 s | 1.17–1.30 s | 0.001 |

- **Best practices 96**: the only failure is console errors from basemap tiles the sandbox
  network blocks (`ERR_TUNNEL_CONNECTION_FAILED`); they disappear with normal internet access.
- **Bundle**: main chunk 141 KB gzip (budget 180 KB); `maplibre-gl` in its own lazy chunk.

## Why `/plan/:id` scores lower here

The sandbox's Chromium has no GPU and renders WebGL with **SwiftShader** (a CPU emulation), so
every map frame, shader compile and synchronous GL query lands on the main thread as a
200–300 ms long task. Attribution runs:

| Variant | Performance | TBT |
| --- | --- | --- |
| Baseline | 70 | 1,170 ms |
| Heatmap request blocked | 70 | 1,300 ms |
| `prefers-reduced-motion` (no draw-in, no camera animation) | 71 | 870 ms |

So the cost is not the heatmap or the GSAP draw-in. It is WebGL setup plus any repaint, which
on a real GPU takes a few milliseconds. The planner page creates the same map but draws far
less, so it clears the gate even under SwiftShader.

**To verify on real hardware** (Chrome with GPU acceleration):

```bash
cd frontend && npm run build && npx vite preview --port 4173
npx lighthouse http://localhost:4173/plan/<id> --preset=desktop --view
```
