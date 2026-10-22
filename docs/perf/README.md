# Forecast slider performance (Phase 5 gate)

## How scrubbing avoids React

1. The heatmap's 49 hourly risk scores are packed into **one** GeoJSON source
   (`h0 … h48` per grid point) and uploaded with `setData` **once** per plan.
2. The slider writes the hour to an imperative **hour bus** (`features/timeline/hourBus.ts`),
   not to React state. The bus runs its listeners at most once per animation frame.
3. In that frame:
   - `heatmap-weight` is replaced with a cross-fade expression between `h{floor}` and
     `h{floor+1}` (`setPaintProperty`), so no geometry is re-uploaded;
   - the 3-feature `trucks` source gets new positions (tiny `setData`);
   - the slider thumb, fill, `aria-valuenow` and clock label are written straight to the DOM.
4. React state (`sliderHour` in zustand) is committed only on pointer-up and per key press.
   Playback is a GSAP tween on a plain `{hour}` object whose `onUpdate` writes to the bus.

## Measured (`e2e/slider-perf.spec.ts`)

The test counts React commits with a dev-only `<Profiler>` (`src/main.tsx`) and samples
`requestAnimationFrame` while dragging the slider across 0 → 48 h and during 3 s of playback.
Latest result: [`slider-perf.json`](slider-perf.json).

| Metric | Result |
| --- | --- |
| React commits during a 48-step drag | **0** |
| React commits on pointer-up | 0 (nothing subscribes to the committed hour yet) |
| React commits while playing | **0** (1 on the play click itself) |

### Frame rate: needs a real GPU

The build sandbox's Chromium renders WebGL with **SwiftShader** (a CPU emulation of a GPU).
There, any MapLibre repaint at 1440×900 runs at about **9 fps even with the heatmap hidden**,
while the idle page runs at 60 fps. So the measured 6–8 fps is the emulated GPU's ceiling, not
the app's. The ≥ 55 fps target in the definition of done must be measured on a machine with a
real GPU:

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npx playwright test e2e/slider-perf.spec.ts --headed
```

For the screenshot the checklist asks for: open the plan in Chrome, start a React DevTools
Profiler recording, drag the slider and press play, stop, and save the "no commits" view next
to this file as `profiler.png`.
