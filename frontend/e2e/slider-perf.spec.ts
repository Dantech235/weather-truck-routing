import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

/**
 * Phase 5 gate: scrubbing the 0–48 h slider must cause zero React commits per tick.
 * Uses the dev-only <Profiler> counter in main.tsx. Also samples frame rate while scrubbing
 * and during playback. Results are written to ../docs/perf/slider-perf.json.
 */
test('slider scrubs and plays with zero React renders per tick', async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Origin' }).fill('dall');
  await page.getByRole('option', { name: 'Dallas, TX' }).click();
  await page.getByRole('combobox', { name: 'Destination' }).fill('denv');
  await page.getByRole('option', { name: 'Denver, CO' }).click();
  await page.getByRole('button', { name: 'Plan routes' }).click();
  await page.waitForURL(/\/plan\//);
  await page.waitForFunction(
    () => {
      try {
        return Boolean(window.__truckMap?.getLayer('corridor-heat'));
      } catch {
        return false;
      }
    },
    null,
    { timeout: 45_000 },
  );
  await page.waitForTimeout(1500); // let camera + layout settle

  const track = page.getByTestId('forecast-slider').locator('..');
  const box = await track.boundingBox();
  if (!box) throw new Error('slider track not visible');
  const y = box.y + box.height / 2;

  // Start an fps sampler (counts rAF callbacks).
  await page.evaluate(() => {
    const w = window as unknown as { __frames: number; __fpsRun: boolean };
    w.__frames = 0;
    w.__fpsRun = true;
    const tick = () => {
      w.__frames++;
      if (w.__fpsRun) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  await page.mouse.move(box.x + 2, y);
  await page.mouse.down();
  const commitsAtDown = await page.evaluate(() => window.__reactCommits ?? 0);
  const t0 = Date.now();
  const STEPS = 48;
  for (let i = 1; i <= STEPS; i++) {
    await page.mouse.move(box.x + 2 + ((box.width + 8) * i) / STEPS, y);
  }
  const scrubMs = Date.now() - t0;
  const commitsBeforeUp = await page.evaluate(() => window.__reactCommits ?? 0);
  const scrubFrames = await page.evaluate(
    () => (window as unknown as { __frames: number }).__frames,
  );
  await page.mouse.up();
  await expect(page.getByTestId('slider-clock')).toContainText('+48.0 h');
  const commitsAfterUp = await page.evaluate(() => window.__reactCommits ?? 0);

  // Playback: press Home then play for ~3 s.
  await page.getByTestId('forecast-slider').focus();
  await page.keyboard.press('Home');
  await page.waitForTimeout(200);
  const commitsBeforePlay = await page.evaluate(() => window.__reactCommits ?? 0);
  await page.evaluate(() => {
    (window as unknown as { __frames: number }).__frames = 0;
  });
  await page.getByTestId('play-button').click();
  const commitsAtPlayStart = await page.evaluate(() => window.__reactCommits ?? 0);
  const playStart = Date.now();
  await page.waitForTimeout(3000);
  const playFrames = await page.evaluate(
    () => (window as unknown as { __frames: number }).__frames,
  );
  const commitsDuringPlay = await page.evaluate(() => window.__reactCommits ?? 0);
  const playMs = Date.now() - playStart;
  const hourAfterPlay = Number(
    await page.getByTestId('forecast-slider').getAttribute('aria-valuenow'),
  );
  await page.getByTestId('play-button').click(); // pause
  await page.screenshot({ path: '../docs/perf/slider-playback.png' });

  const result = {
    measured_at: new Date().toISOString(),
    environment: 'headless Chromium (software WebGL), dev build, 1440×900',
    scrub: {
      pointer_moves: STEPS,
      duration_ms: scrubMs,
      react_commits_during_drag: commitsBeforeUp - commitsAtDown,
      react_commits_on_pointer_up: commitsAfterUp - commitsBeforeUp,
      fps: Math.round((scrubFrames / scrubMs) * 1000),
    },
    playback: {
      duration_ms: playMs,
      hours_advanced: hourAfterPlay,
      react_commits_on_play_click: commitsAtPlayStart - commitsBeforePlay,
      react_commits_while_playing: commitsDuringPlay - commitsAtPlayStart,
      fps: Math.round((playFrames / playMs) * 1000),
    },
  };
  mkdirSync('../docs/perf', { recursive: true });
  writeFileSync('../docs/perf/slider-perf.json', `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify(result, null, 2));

  expect(result.scrub.react_commits_during_drag).toBe(0);
  expect(result.playback.react_commits_while_playing).toBe(0);
  expect(hourAfterPlay).toBeGreaterThan(5); // 0.4 s per hour → ~7.5 h in 3 s
});
