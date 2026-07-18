// Starter Lab — end-to-end flows (@playwright/test), current gated-reveal build.
//
// Setup once:  npm i -D @playwright/test && npx playwright install
// Run:         npm run test:e2e            (or: npx playwright test)
// The webServer + baseURL (127.0.0.1) come from playwright.config.ts, which also
// runs every spec across chromium / webkit / firefox.
//
// Resilient locators (role/id/text) over stable ids; drives the vanilla-JS build.

import { test, expect, Page } from '@playwright/test';

const PATH = '/lab.built.html';

// The team is GATED behind SPIN (no spoiler until you spin). boot() waits for the
// data to load (pool counter), then reveal() spins and waits for the ranked trio.
async function boot(page: Page) {
  await page.addInitScript(() => { try { localStorage.setItem('sl_tour', 'done'); } catch { /* private mode */ } });
  await page.goto(PATH, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#poolv')).toHaveText(/pool \d+/, { timeout: 15000 });
}
async function reveal(page: Page) {
  // SPIN is a no-op until the Web Worker returns results; after a param change there's a
  // recompute window, so retry the spin until the ranked readout appears.
  const rank = page.locator('#rank');
  for (let i = 0; i < 4; i++) {
    await page.locator('#spin').click();
    try { await expect(rank).toHaveText(/MATCH #\d+ \/ \d+/, { timeout: 4000 }); return; }
    catch { await page.waitForTimeout(500); }
  }
  await expect(rank).toHaveText(/MATCH #\d+ \/ \d+/, { timeout: 4000 });
}
// Types / BST / base-town live behind the collapsed "Advanced filters" accordion.
async function openAdvanced(page: Page) {
  // deterministically reveal the accordion (bypass the toggle's 0.18s advin animation),
  // then wait on a chip being actionable rather than the still-animating container.
  await page.evaluate(() => {
    const a = document.getElementById('advfilters') as HTMLElement | null;
    if (a) { a.hidden = false; document.getElementById('advtoggle')?.setAttribute('aria-expanded', 'true'); }
  });
  await expect(page.locator('#types .chip[data-type="fire"]')).toBeVisible();
}

test.beforeEach(async ({ page }) => { await boot(page); });

test('gated on load; SPIN reveals a ranked trio and a "#N / total" counter', async ({ page }) => {
  await expect(page.locator('#rank')).toHaveText(/READY/);           // gated: no spoiler before spin
  await reveal(page);
  await expect(page.locator('#rank')).toHaveText(/MATCH #1 \/ \d+/);
  await expect(page.locator('.smon[data-dex]')).toHaveCount(3);
  await expect(page.locator('.reel:not(.gone) .cell img')).toHaveCount(3);
});

test('Next / Prev walk the ranked results after reveal', async ({ page }) => {
  await reveal(page);
  await page.getByRole('button', { name: /Next/ }).click();
  await expect(page.locator('#rank')).toHaveText(/MATCH #2 \//);
  await page.getByRole('button', { name: /Prev/ }).click();
  await expect(page.locator('#rank')).toHaveText(/MATCH #1 \//);
});

test('selecting Gen II only renders the Johto catch map', async ({ page }) => {
  await page.locator('#gens .chip[data-gen="2"]').click();  // add Gen II
  await page.locator('#gens .chip[data-gen="1"]').click();  // drop Gen I -> Johto only
  await reveal(page);
  // maps are auto multi-panels now (no tabs); one Johto panel with catch nodes
  await expect(page.locator('#mapgrid .mappanel')).toHaveCount(1);
  await expect(page.locator('#maplabel')).toContainText(/Johto/);
});

test('a type chip cycles off -> include -> exclude', async ({ page }) => {
  await openAdvanced(page);
  const water = page.locator('#types .chip[data-type="water"]');
  await expect(water).toHaveAttribute('data-state', 'off');
  await water.click();
  await expect(water).toHaveAttribute('data-state', 'inc');
  await water.click();
  await expect(water).toHaveAttribute('data-state', 'exc');
  // engine re-ran (gated); revealing still yields a full trio under the exclusion
  await reveal(page);
  await expect(page.locator('.smon[data-dex]')).toHaveCount(3);
});

test('an impossible filter surfaces the auto-relax note', async ({ page }) => {
  await openAdvanced(page);
  // include Dragon in Gen-1 = only the Dratini line -> a size-3 team is impossible -> relax
  await page.locator('#types .chip[data-type="dragon"]').click();
  await reveal(page);
  await expect(page.locator('#relaxnote')).toBeVisible();
  await expect(page.locator('#relaxnote')).toContainText(/loosened|relax/i);
});

test('Copy link writes a hash that restores controls on a fresh load', async ({ page, context }) => {
  await page.locator('#strat').selectOption({ label: 'Max coverage' });
  await page.locator('#sizeseg button[data-s="2"]').click();
  // copyShareLink runs syncHash() (updating the URL) before the clipboard write, so the
  // hash is authoritative even where headless clipboard access is denied (e.g. WebKit).
  await page.locator('#sharebtn').click();
  const url = page.url();
  expect(url).toMatch(/st=coverage/);
  expect(url).toMatch(/sz=2/);
  // a fresh load of the shared URL restores state (authoritative applyHash-on-boot)
  const p2 = await context.newPage();
  await p2.addInitScript(() => { try { localStorage.setItem('sl_tour', 'done'); } catch { /* */ } });
  await p2.goto(url, { waitUntil: 'domcontentloaded' });
  await expect(p2.locator('#poolv')).toHaveText(/pool \d+/, { timeout: 15000 });
  await expect(p2.locator('#strat')).toHaveValue('Max coverage');
  await expect(p2.locator('#sizeseg button.on')).toHaveAttribute('data-s', '2');
});

test('clicking a revealed team member opens the detail dialog; Escape closes it', async ({ page }) => {
  await reveal(page);
  await page.locator('.smon[data-dex]').first().click();
  const dialog = page.locator('.dmodal[role="dialog"]');
  await expect(page.locator('#dback')).toHaveClass(/open/);
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute('aria-modal', 'true');
  await expect(dialog.locator('h3')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#dback')).not.toHaveClass(/open/);
});

test('Browse full dex opens the species grid', async ({ page }) => {
  await page.getByRole('button', { name: /Browse full dex/i }).click();
  await expect(page.locator('#dback')).toHaveClass(/open/);
  await expect(page.locator('.dextile')).not.toHaveCount(0);
  await expect(page.locator('#dscreen h3')).toContainText(/Pok.dex browser/i);
  await page.getByRole('button', { name: /Close/ }).click();
  await expect(page.locator('#dback')).not.toHaveClass(/open/);
});

test('type chips are keyboard-operable (Enter activates)', async ({ page }) => {
  await openAdvanced(page);
  const fire = page.locator('#types .chip[data-type="fire"]');
  await fire.focus();
  await expect(fire).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(fire).toHaveAttribute('data-state', 'inc');
});
