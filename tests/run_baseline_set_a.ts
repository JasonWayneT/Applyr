import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import { extractJobDescriptionWithMeta } from '../scripts/extract_job_page.js';

chromium.use(stealth());

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function run() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const fixturesDir = path.join(__dirname, 'fixtures/builtin');
    const files = fs.readdirSync(fixturesDir).filter(f => f.endsWith('.html'));

    const results: Record<string, any> = {};

    for (const file of files) {
        const filePath = path.join(fixturesDir, file);
        const fileUrl = 'file://' + filePath.replace(/\\/g, '/');
        console.log(`Processing ${file}...`);
        
        // We use minChars=0 for the test to ensure we capture extraction success even on small files like thin_jd
        const res = await extractJobDescriptionWithMeta(context, fileUrl, 0);
        results[file] = {
            source: res.source,
            confidence: res.confidence,
            flags: res.flags,
            length: res.text.length
        };
        console.log(`  -> source: ${res.source}, confidence: ${res.confidence}, length: ${res.text.length}`);
    }

    await browser.close();
    
    fs.writeFileSync(path.join(__dirname, 'baseline_set_a.json'), JSON.stringify(results, null, 2));
    console.log('Saved baseline_set_a.json');
}

run().catch(console.error);
