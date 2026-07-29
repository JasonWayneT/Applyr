/**
 * FR-180 (CR-033): Playwright JD extraction — robust Built In + generic fallback.
 *
 * Extraction order:
 *  1. window.__NEXT_DATA__ JSON path scan (Next.js pages) → confidence: high
 *  2. JSON-LD <script type="application/ld+json"> JobPosting.description → confidence: high
 *  3. Multi-selector DOM walk (scores all candidates, picks highest) → confidence: medium
 *  4. document.body.innerText fallback → confidence: low
 *
 * Public API:
 *  - extractJobDescriptionWithMeta()  used by scoutBuiltIn — returns ExtractionResult with confidence
 *  - extractJobDescriptionFromPage()  used by scrape_new_jobs — unchanged string return signature
 *  - MIN_JD_CHARS = 200               generic minimum (scrape_new_jobs, all non-Built In sources)
 *  - BUILTIN_MIN_JD_CHARS = 500       higher bar applied only in the Built In scout path
 */

import { BrowserContext } from 'playwright';
import {
    hasRoleSignal,
    classifyConfidence,
    buildDataQualityFlags,
    type ExtractionSource,
    type ExtractionConfidence,
} from './domain/jdQuality.js';
import { isBlockedScrapeUrl } from '../shared/domain/blockedScrapeHosts.js';

export const MIN_JD_CHARS = 200;
export const BUILTIN_MIN_JD_CHARS = 500;
export const MAX_JD_CHARS = 15000;

// Ordered by specificity — Built In real selectors first, then generics.
// [class*="..."] wildcards survive compiled CSS class renames across deploys.
const JD_SELECTORS = [
    // Built In — current DOM
    '[data-id="job-description"]',
    '[data-id="job-content"]',
    '.job-description__description',
    '.description__text',
    // Common ATS embeds Built In sometimes inlines
    '.jobsearch-jobDescriptionText',
    '.job-details__description',
    // Wildcard class matches (compiled React class names e.g. JobDescription_jobDescription__xK2p3)
    '[class*="JobDescription"]',
    '[class*="job-description"]',
    '[class*="jobDescription"]',
    '[id*="job-description"]',
    '[id*="jobDescription"]',
    // Generic fallbacks
    '.job-description',
    '#job-description',
    '.description',
    '#description',
    // Last-resort structural
    'article',
    'main',
];

// Union string used by Playwright's waitForSelector (fires as soon as any one appears)
const WAIT_SELECTOR = [
    '[data-id="job-description"]',
    '[data-id="job-content"]',
    '.job-description__description',
    '[class*="JobDescription"]',
    'article',
    'main',
].join(', ');

// Known ATS domains — if the detail URL redirects here, the JD is on an external system.
const ATS_DOMAINS = [
    'greenhouse.io', 'lever.co', 'workday.com', 'myworkday.com',
    'smartrecruiters.com', 'icims.com', 'ashbyhq.com',
];

// ---------------------------------------------------------------------------
// Browser-side functions — must be fully self-contained (no imports/closures).
// Serialised to string by page.evaluate() and executed in the browser context.
// ---------------------------------------------------------------------------

/**
 * Attempt 1: window.__NEXT_DATA__ (Next.js SSR hydration payload)
 * Attempt 2: JSON-LD <script type="application/ld+json"> JobPosting schema
 * Returns the description string if found, null otherwise.
 */
function extractStructuredInBrowser(): string | null {
    // --- __NEXT_DATA__ ---
    try {
        const nd = (window as any).__NEXT_DATA__;
        if (nd) {
            const paths: string[][] = [
                ['props', 'pageProps', 'job', 'description'],
                ['props', 'pageProps', 'job', 'descriptionFormatted'],
                ['props', 'pageProps', 'jobPost', 'description'],
                ['props', 'pageProps', 'jobPost', 'descriptionFormatted'],
                ['props', 'pageProps', 'data', 'job', 'description'],
                ['props', 'pageProps', 'initialProps', 'job', 'description'],
            ];
            for (const path of paths) {
                let val: any = nd;
                for (const key of path) val = val?.[key];
                if (typeof val === 'string' && val.trim().length > 100) return val.trim();
            }
        }
    } catch {}

    // --- JSON-LD JobPosting ---
    try {
        const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
        for (const el of scripts) {
            try {
                const raw = (el as HTMLScriptElement).textContent ?? '';
                const data = JSON.parse(raw);
                const items: any[] = Array.isArray(data) ? data : [data];
                for (const item of items) {
                    if (
                        item?.['@type'] === 'JobPosting' &&
                        typeof item.description === 'string' &&
                        item.description.trim().length > 100
                    ) {
                        return item.description.trim();
                    }
                }
            } catch {}
        }
    } catch {}

    return null;
}

/**
 * DOM selector walk — scores all matching elements, picks the highest-scoring candidate.
 * Returns { text, usedBodyFallback } so the caller can classify confidence accurately.
 */
function extractInBrowser(
    { selectors, minLen }: { selectors: string[]; minLen: number },
): { text: string; usedBodyFallback: boolean } {
    const candidates: { text: string; score: number }[] = [];

    // 1. Score every matching element
    for (const sel of selectors) {
        try {
            const elements = document.querySelectorAll(sel);
            for (const el of Array.from(elements)) {
                const text = (el as HTMLElement).innerText?.trim() ?? '';
                if (text.length >= minLen) {
                    // Penalise broad structural tags — they often grab sidebar/nav too
                    const tag = el.tagName.toLowerCase();
                    const isStructural = ['main', 'article'].includes(tag);
                    const penalty = isStructural ? 0.5 : 1.0;
                    candidates.push({ text, score: text.length * penalty });
                }
            }
        } catch {}
    }

    // 2. Walk headings — Built In often structures JDs under a known h2
    const headingPhrases = /job description|about the role|about this role|responsibilities|what you.ll do|the opportunity/i;
    for (const h of Array.from(document.querySelectorAll('h1,h2,h3,h4'))) {
        if (headingPhrases.test(h.textContent ?? '')) {
            const chunks: string[] = [];
            const stopTags = new Set(['H1', 'H2', 'H3', 'H4']);
            let sib: Element | null = h.nextElementSibling;
            while (sib && !stopTags.has(sib.tagName)) {
                const t = (sib as HTMLElement).innerText?.trim() ?? '';
                if (t) chunks.push(t);
                sib = sib.nextElementSibling;
            }
            const joined = chunks.join('\n').trim();
            if (joined.length >= minLen) {
                // Boost: heading-anchored content is the most reliable JD signal
                candidates.push({ text: joined, score: joined.length * 1.2 });
            }
        }
    }

    // 3. Pick highest-scoring candidate
    if (candidates.length > 0) {
        candidates.sort((a, b) => b.score - a.score);
        return { text: candidates[0].text, usedBodyFallback: false };
    }

    // 4. Absolute last resort — full body text
    return { text: document.body?.innerText?.trim() ?? '', usedBodyFallback: true };
}

// ---------------------------------------------------------------------------
// Public extraction interface
// ---------------------------------------------------------------------------

export interface ExtractionResult {
    text: string;
    source: ExtractionSource;
    confidence: ExtractionConfidence;
    flags: string[];
}

/**
 * Full extraction with quality metadata.
 * Used by scoutBuiltIn() — returns confidence and flags alongside the text.
 */
export async function extractJobDescriptionWithMeta(
    context: BrowserContext,
    url: string,
    minChars: number = MIN_JD_CHARS,
): Promise<ExtractionResult> {
    if (isBlockedScrapeUrl(url)) {
        console.log(`[FR-080] Blocked scrape host — refusing navigation to ${url}`);
        return {
            text: '',
            source: 'body',
            confidence: 'low',
            flags: ['blocked_host_linkedin'],
        };
    }

    const page = await context.newPage();
    try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});

        // ATS redirect — follow and extract from destination (Built In → Greenhouse/Workday/etc.)
        const finalUrl = page.url();
        const atsRedirect =
          ATS_DOMAINS.some((d) => finalUrl.includes(d)) &&
          !ATS_DOMAINS.some((d) => url.includes(d));
        if (atsRedirect) {
            console.log(`[LOG] extract_job_page: ATS redirect ${url} → ${finalUrl}`);
        }

        // Wait for real content before extracting
        await Promise.race([
            page.waitForSelector(WAIT_SELECTOR, { timeout: 8000 }).catch(() => {}),
            new Promise(r => setTimeout(r, 8000)),
        ]);
        await new Promise(r => setTimeout(r, 800));

        // --- Attempt 1: Structured data (__NEXT_DATA__ / JSON-LD) ---
        const structured: string | null = await page.evaluate(extractStructuredInBrowser);
        if (structured && structured.length >= minChars) {
            const text = structured.slice(0, MAX_JD_CHARS);
            console.log(`[LOG] extract_job_page: structured (${text.length} chars) ${finalUrl}`);
            const flags = buildDataQualityFlags(text, 'structured', minChars);
            if (atsRedirect) flags.push('ats_redirect_followed');
            return {
                text,
                source: 'structured',
                confidence: classifyConfidence(text, 'structured'),
                flags,
            };
        }

        // --- Attempt 2: DOM selector walk ---
        const domResult: { text: string; usedBodyFallback: boolean } = await page.evaluate(
            extractInBrowser,
            { selectors: JD_SELECTORS, minLen: minChars },
        );
        const trimmed = (domResult.text ?? '').trim();
        const source: ExtractionSource = domResult.usedBodyFallback ? 'body' : 'dom';

        if (trimmed.length >= minChars) {
            const text = trimmed.slice(0, MAX_JD_CHARS);
            console.log(`[LOG] extract_job_page: ${source} (${text.length} chars) ${finalUrl}`);
            const flags = buildDataQualityFlags(text, source, minChars);
            if (atsRedirect) flags.push('ats_redirect_followed');
            return {
                text,
                source,
                confidence: classifyConfidence(text, source),
                flags,
            };
        }

        // Debug block: fires only when all extraction paths fail
        const counts: string = await page.evaluate(() => {
            const tags = ['[data-id]', '[class*="job"]', '[class*="Job"]', 'article', 'main', 'section'];
            return tags.map(s => `${s}: ${document.querySelectorAll(s).length}`).join(', ');
        });
        console.log(`[DEBUG] ${url} — DOM counts: ${counts}`);
        const bodyLen: number = await page.evaluate(() => document.body?.innerText?.length ?? 0);
        console.log(`[DEBUG] body.innerText length: ${bodyLen}`);

        return {
            text: '',
            source: 'body',
            confidence: 'low',
            flags: atsRedirect ? ['ats_redirect_failed'] : ['extraction_failed'],
        };

    } catch (err) {
        console.log(`[LOG] extract_job_page: failed for ${url} — ${err}`);
        return { text: '', source: 'body', confidence: 'low', flags: ['extraction_failed'] };
    } finally {
        await page.close().catch(() => {});
    }
}

/**
 * Backward-compatible wrapper — signature unchanged.
 * Used by scrape_new_jobs.ts; MIN_JD_CHARS (200) default preserved.
 */
export async function extractJobDescriptionFromPage(
    context: BrowserContext,
    url: string,
    minChars: number = MIN_JD_CHARS,
): Promise<string> {
    const { text } = await extractJobDescriptionWithMeta(context, url, minChars);
    return text;
}
