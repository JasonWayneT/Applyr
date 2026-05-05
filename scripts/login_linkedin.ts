import { chromium } from 'playwright-extra';
import stealthPlugin from 'puppeteer-extra-plugin-stealth';
import path from 'path';

chromium.use(stealthPlugin());

const CONTEXT_DIR = path.resolve('data/browser_context');

(async () => {
    console.log('Opening persistent browser context...');
    const context = await chromium.launchPersistentContext(CONTEXT_DIR, {
        headless: false,
        viewport: { width: 1440, height: 900 },
        args: ['--disable-blink-features=AutomationControlled'],
    });

    const page = context.pages()[0] || await context.newPage();
    console.log('Navigating to LinkedIn...');
    await page.goto('https://www.linkedin.com/login');
    
    console.log('Please log into LinkedIn in the browser window.');
    console.log('You can close the browser window manually when you are done.');
    
    // Keep it open until the user closes the browser manually
    await new Promise<void>((resolve) => {
        context.on('close', () => {
            console.log('Browser closed. Your session is saved!');
            resolve();
        });
    });
})();
