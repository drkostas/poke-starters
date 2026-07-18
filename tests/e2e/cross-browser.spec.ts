// Cross-browser capability + core-flow smoke for the Starter Lab vanilla build.
// Runs on chromium / webkit / firefox (see playwright.config.ts) to lock in the
// engine-sensitive behaviors that differ across browsers: `inert` focus-trap,
// Web Animations, AudioContext, module Web Worker, and the full reveal/modal/tour flow.
import { test, expect, Page } from '@playwright/test';

const PATH = '/lab.built.html';

async function boot(page: Page) {
  await page.addInitScript(() => { try { localStorage.setItem('sl_tour', 'done'); } catch { /* private mode */ } });
  await page.goto(PATH, { waitUntil: 'domcontentloaded' });
  // the pool counter proves boot() + the Web Worker (or its main-thread fallback) ran
  await expect(page.locator('#poolv')).toHaveText(/pool \d+/, { timeout: 15000 });
}

test('platform capabilities the app depends on are present', async ({ page }) => {
  await boot(page);
  const caps = await page.evaluate(() => ({
    inert: 'inert' in HTMLElement.prototype,
    waapi: typeof Element.prototype.animate === 'function',
    audio: !!(window.AudioContext || (window as any).webkitAudioContext),
    matchMedia: typeof matchMedia === 'function',
  }));
  expect(caps.inert, 'inert (modal/tour focus-trap)').toBe(true);
  expect(caps.waapi, 'Web Animations (spin/evolve/flash)').toBe(true);
  expect(caps.audio, 'AudioContext (GB sound fx)').toBe(true);
  expect(caps.matchMedia, 'matchMedia (reduced-motion)').toBe(true);
});

test('core flow: gated reveal -> team + triangle + maps + matrix', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { location.hash = '#g=1&sz=3&st=triangle'; dispatchEvent(new HashChangeEvent('hashchange')); });
  await page.waitForTimeout(700);
  await page.locator('#spin').click();
  await expect(page.locator('#rank')).toHaveText(/MATCH #1 \/ \d+/, { timeout: 12000 });
  await expect(page.locator('#smons .smon')).toHaveCount(3);
  await expect(page.locator('#trisvg image')).toHaveCount(3);
  await expect(page.locator('#mapgrid .mappanel')).toHaveCount(1);
  // Gen-1 view => 15-type defensive matrix (era-aware)
  await expect(page.locator('#dmx .dmc')).toHaveCount(15);
});

test('modal is a real focus trap (inert) and clears on close', async ({ page }) => {
  await boot(page);
  await page.locator('#dexbtn').click();
  await expect(page.locator('#dback')).toHaveClass(/open/);
  const trapped = await page.evaluate(() => {
    const wrapInert = document.querySelector('.wrap')!.hasAttribute('inert');
    const run = document.getElementById('run')!; run.focus();
    return { wrapInert, focusEscaped: document.activeElement === run };
  });
  expect(trapped.wrapInert, 'background .wrap is inert while modal open').toBe(true);
  expect(trapped.focusEscaped, 'focus cannot land on a background control').toBe(false);
  await page.keyboard.press('Escape');
  await expect(page.locator('.wrap')).not.toHaveAttribute('inert', /.*/);
});

test('evolve updates the sprite (Web Animations path) and the tour opens/closes', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => { location.hash = '#g=1&sz=3'; dispatchEvent(new HashChangeEvent('hashchange')); });
  await page.waitForTimeout(700);
  await page.locator('#spin').click();
  await expect(page.locator('#rank')).toHaveText(/MATCH #1/, { timeout: 12000 });
  const before = await page.locator('.reels .reel:not(.gone) img').first().getAttribute('src');
  const evo = page.locator('#evolve');
  if (await evo.isEnabled()) {
    await evo.click();
    await page.waitForTimeout(1000);
    const after = await page.locator('.reels .reel:not(.gone) img').first().getAttribute('src');
    expect(after, 'a reel sprite advanced a stage').not.toBe(before);
  }
  await page.locator('#helpbtn').click();
  await expect(page.locator('#tour')).not.toHaveAttribute('hidden', /.*/);
  await page.keyboard.press('Escape');
  await expect(page.locator('#tour')).toHaveAttribute('hidden', /.*/);
});
