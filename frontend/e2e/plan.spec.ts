import { expect, test, type Page } from '@playwright/test';

async function choosePlace(page: Page, label: string, query: string, option: string) {
  await page.getByRole('combobox', { name: label }).fill(query);
  await page.getByRole('option', { name: option }).click();
}

test('plan Dallas → Denver and inspect a checkpoint', async ({ page }) => {
  await page.goto('/');
  await choosePlace(page, 'Origin', 'dall', 'Dallas, TX');
  await choosePlace(page, 'Destination', 'denv', 'Denver, CO');
  await page.getByLabel('Load (lb)').fill('45000');
  await expect(page.getByLabel('Load (lb)')).toHaveValue('45,000');
  await page.getByText('25 mi', { exact: true }).click();
  await page.getByRole('button', { name: 'Plan routes' }).click();

  await page.waitForURL(/\/plan\/[0-9a-f-]{36}$/);
  await expect(page.locator('[data-route-card]')).toHaveCount(3);
  await expect(page.getByTestId('recommended-badge')).toHaveCount(1);

  await page.waitForFunction(() => {
    try {
      return Boolean(window.__truckMap?.getLayer('checkpoints'));
    } catch {
      return false;
    }
  });

  // Select route A and click one of its checkpoints on the map.
  const planId = page.url().split('/').pop() ?? '';
  const api = process.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const plan = (await (await page.request.get(`${api}/api/v1/plans/${planId}/`)).json()) as {
    routes: { label: string; checkpoints: { lat: number; lon: number; mile: number }[] }[];
  };
  const route = plan.routes.find((r) => r.label === 'A') ?? plan.routes[0];
  const cp = route?.checkpoints[3];
  expect(cp).toBeDefined();
  await page.locator(`[data-route-card="${route?.label}"]`).click();
  await expect(page.locator(`[data-route-card="${route?.label}"]`)).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.waitForTimeout(1200); // camera fitBounds (900 ms)
  const xy = await page.evaluate(
    ([lon, lat]) => {
      const map = window.__truckMap;
      if (!map) throw new Error('map not ready');
      const p = map.project([lon, lat]);
      const r = map.getCanvas().getBoundingClientRect();
      return { x: r.left + p.x, y: r.top + p.y };
    },
    [cp?.lon ?? 0, cp?.lat ?? 0] as [number, number],
  );
  await page.mouse.click(xy.x, xy.y);

  const drawer = page.getByTestId('checkpoint-drawer');
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(`Mile ${cp?.mile.toFixed(1)}`);
  await expect(drawer).toContainText('Forecast hour used');
  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();

  // Forecast slider: keyboard and drag both move the hour label.
  const slider = page.getByTestId('forecast-slider');
  const clock = page.getByTestId('slider-clock');
  await expect(clock).toContainText('+0.0 h');
  await slider.focus();
  await page.keyboard.press('Shift+ArrowRight');
  await expect(slider).toHaveAttribute('aria-valuenow', '6.0');
  await expect(clock).toContainText('+6.0 h');
  await page.keyboard.press('End');
  await expect(clock).toContainText('+48.0 h');
  await page.keyboard.press('Home');
  await expect(clock).toContainText('+0.0 h');

  // Shareable URL survives a reload.
  await page.reload();
  await expect(page.locator('[data-route-card]')).toHaveCount(3);
});
