// Run against Vite with Playwright available via node resolution / NODE_PATH:
// node web/e2e/landing-cards.cjs
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const evidence = '.tmp/landing/manual-cards';
  fs.mkdirSync(evidence, { recursive: true });
  try {
    for (const mode of ['desktop', 'mobile', 'reduced']) {
      const page = await browser.newPage({
        viewport: mode === 'mobile' ? { width: 390, height: 844 } : { width: 1440, height: 900 },
        isMobile: mode === 'mobile', hasTouch: mode === 'mobile',
        reducedMotion: mode === 'reduced' ? 'reduce' : 'no-preference',
      });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(process.env.LANDING_URL || 'http://127.0.0.1:5173/');
      const stack = page.locator('[class*="documentStack_"]');
      const active = () => page.locator('[data-active="true"][data-paper-layer]').getAttribute('data-paper-layer');
      const next = page.getByRole('button', { name: 'Next source page', exact: true });
      const previous = page.getByRole('button', { name: 'Previous source page', exact: true });
      await stack.waitFor();
      await page.evaluate(() => document.fonts.ready);
      if (mode !== 'desktop') await stack.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${evidence}/${mode}-initial.png` });
      if (mode === 'desktop') {
        const rest = await stack.evaluate(el => getComputedStyle(el).transform);
        const box = await stack.boundingBox();
        await page.mouse.move(box.x + box.width * .85, box.y + box.height * .2);
        await page.waitForTimeout(700);
        assert.notEqual(await stack.evaluate(el => getComputedStyle(el).transform), rest);
        assert.equal(await active(), '0', 'hover must not flip a card');
        await page.screenshot({ path: `${evidence}/desktop-hover.png` });
        await page.mouse.wheel(0, 450);
        await page.waitForTimeout(400);
        assert((await page.evaluate(() => scrollY)) > 0, 'wheel over cards must scroll');
        assert.equal(await active(), '0', 'scroll must not flip cards');
        await page.evaluate(() => scrollTo(0, 0));
      }
      // Clicking the reading face flips exactly once, without scrolling.
      const face = page.locator('[data-paper-layer="0"] button');
      await face.scrollIntoViewIfNeeded();
      const beforeClick = await page.evaluate(() => scrollY);
      await face.click();
      await page.waitForTimeout(700);
      assert.equal(await active(), '1');
      assert.equal(await page.evaluate(() => scrollY), beforeClick);
      if (mode === 'desktop') {
        // The exposed next sheet is also a real click target.
        const back = page.locator('[data-paper-layer="2"] button');
        const point = await back.evaluate(button => {
          const box = button.getBoundingClientRect();
          const y = box.y + box.height * .4;
          for (let x = box.right - 1; x > box.left; x -= 2) {
            if (document.elementFromPoint(x, y) === button) return { x, y };
          }
          throw new Error('Next sheet has no exposed click target');
        });
        await page.mouse.click(point.x - 3, point.y);
        await page.waitForTimeout(700);
        assert.equal(await active(), '2', 'clicking the exposed next sheet must flip');
        await previous.click();
        await page.waitForTimeout(700);
      }
      if (mode === 'mobile') {
        const cdp = await page.context().newCDPSession(page);
        async function swipe(dx, dy) {
          const box = await stack.boundingBox();
          const x = box.x + box.width / 2, y = box.y + box.height / 2;
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
          for (let i = 1; i <= 8; i++) {
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + dx * i / 8, y: y + dy * i / 8 }] });
            await page.waitForTimeout(25);
          }
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
          await page.waitForTimeout(700);
        }
        await swipe(-100, 2);
        assert.equal(await active(), '2', 'horizontal swipe must flip once');
        await swipe(100, 2);
        assert.equal(await active(), '1', 'reverse swipe must go back');
        const before = await page.evaluate(() => scrollY);
        await swipe(2, -120);
        assert((await page.evaluate(() => scrollY)) > before, 'vertical swipe must scroll');
        assert.equal(await active(), '1', 'vertical swipe must not flip');
      }
      for (let i = 2; i < 5; i++) {
        await next.click();
        await page.waitForTimeout(700);
        assert.equal(await active(), String(i));
      }
      assert(await next.isDisabled());
      await previous.focus();
      await page.keyboard.press('Enter');
      await page.waitForTimeout(700);
      assert.equal(await active(), '3');
      await page.screenshot({ path: `${evidence}/${mode}-visualize.png` });
      if (mode === 'desktop') {
        const scene = page.locator('[class*="documentScene_"]');
        const cardTransform = await page.locator('[data-paper-layer="3"]').evaluate(el => getComputedStyle(el).transform);
        for (const progress of [.38, .48]) {
          await page.evaluate(p => scrollTo(0, (document.querySelector('main').offsetHeight - innerHeight) * p), progress);
          await page.waitForTimeout(400);
          assert.equal(await active(), '3');
          assert.equal(await page.locator('[data-paper-layer="3"]').evaluate(el => getComputedStyle(el).transform), cardTransform);
          const opacity = Number(await scene.evaluate(el => getComputedStyle(el).opacity));
          assert(progress === .38 ? opacity > 0 && opacity < 1 : opacity === 0);
          await page.screenshot({ path: `${evidence}/desktop-exit-${progress}.png` });
        }
        assert.equal(await page.locator('[class*="productStage_"]').evaluate(el => getComputedStyle(el).opacity), '0');
        assert(await page.locator('[class*="documentScene_"]').evaluate(el => el.hasAttribute('inert')));
      }
      assert.deepEqual(errors, []);
      console.log(`${mode}: card controls, native scroll, accessibility and scene continuity PASS`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
