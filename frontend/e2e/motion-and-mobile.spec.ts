import { expect, test, type Page } from '@playwright/test';

async function planTrip(page: Page) {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Origin' }).fill('dall');
  await page.getByRole('option', { name: 'Dallas, TX' }).click();
  await page.getByRole('combobox', { name: 'Destination' }).fill('denv');
  await page.getByRole('option', { name: 'Denver, CO' }).click();
  await page.getByRole('button', { name: 'Plan routes' }).click();
  await page.waitForURL(/\/plan\//);
  await page.waitForFunction(() => {
    try {
      return Boolean(window.__truckMap?.getLayer('checkpoints'));
    } catch {
      return false;
    }
  });
}

const checkpointOpacity = (page: Page) =>
  page.evaluate(() => {
    const m = window.__truckMap as unknown as {
      getPaintProperty: (layer: string, prop: string) => unknown;
    };
    return JSON.stringify(m.getPaintProperty('checkpoints', 'circle-opacity'));
  });

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });

  test('routes and checkpoints appear immediately, no card transforms', async ({ page }) => {
    await planTrip(page);
    // No draw-in: checkpoint opacity is already at full strength for the selected route.
    expect(await checkpointOpacity(page)).toContain('1');
    const transform = await page
      .locator('.route-card')
      .first()
      .evaluate((el) => getComputedStyle(el).transform);
    expect(transform === 'none' || transform === 'matrix(1, 0, 0, 1, 0, 0)').toBe(true);
    await expect(page.getByTestId('recommended-badge')).toBeVisible();
  });
});

test.describe('motion on', () => {
  test.use({ reducedMotion: 'no-preference' });

  test('checkpoints fade in after the routes draw', async ({ page }) => {
    await planTrip(page);
    // Right after the layers are added the checkpoints start hidden…
    const early = await checkpointOpacity(page);
    await page.waitForTimeout(2000); // 0.9 s draw + 2 × 0.15 s stagger + 0.3 s fade
    const late = await checkpointOpacity(page);
    expect(late).not.toBe(early);
    expect(late).toContain('1');
  });
});

test.describe('phone layout', () => {
  test.use({ viewport: { width: 375, height: 812 }, hasTouch: true });

  test('bottom sheet snaps and the slider rides above it', async ({ page }) => {
    await planTrip(page);
    const sheet = page.getByTestId('bottom-sheet');
    await expect(sheet).toHaveAttribute('data-snap', 'half');
    const slider = page.getByTestId('forecast-slider');
    await expect(slider).toBeVisible();
    const sliderBox = await slider.boundingBox();
    const sheetTopHalf = (await sheet.boundingBox())?.y ?? 0;
    // Slider sits above the visible part of the sheet.
    const visibleTop = await sheet.evaluate((el) => el.getBoundingClientRect().top);
    expect((sliderBox?.y ?? 0) + (sliderBox?.height ?? 0)).toBeLessThanOrEqual(visibleTop + 1);
    expect(sheetTopHalf).toBeGreaterThan(0);

    // Keyboard: the handle cycles half → full → peek.
    const handle = page.getByTestId('sheet-handle');
    await handle.focus();
    await page.keyboard.press('Enter');
    await expect(sheet).toHaveAttribute('data-snap', 'full');
    await page.keyboard.press('Enter');
    await expect(sheet).toHaveAttribute('data-snap', 'peek');
    await page.waitForTimeout(400);
    const peekTop = await sheet.evaluate((el) => el.getBoundingClientRect().top);
    expect(812 - peekTop).toBeLessThan(170);

    // Drag the handle up past halfway → snaps to full.
    const hb = await handle.boundingBox();
    if (!hb) throw new Error('handle not visible');
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(hb.x + hb.width / 2, hb.y - 60 * i);
    await page.mouse.up();
    await expect(sheet).toHaveAttribute('data-snap', 'full');

    // No horizontal scroll at 375 px.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
