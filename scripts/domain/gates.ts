/**
 * Deterministic ingest gates — pure functions, no I/O.
 * Used by scout_local.ts at ingest time; tested in tests/unit/gates.test.ts.
 */

export interface ScrapedJob {
    company: string;
    title: string;
    url: string;
    description: string;
    source: string;
    salary_range?: string;
    recruiter_name?: string;
    recruiter_url?: string;
    extraction_confidence?: string;
    data_quality_flags?: string[];
}

export interface GateConfig {
    blockedIndustries: string[];
    titleBlocklist: string[];
    workSetting: string;
    maxExperienceYears: number;
}

// Sources where every listing is remote — geo gate always passes.
const REMOTE_ONLY_SOURCES = new Set(['Remotive', 'RemoteOK', 'WWR', 'Himalayas']);

function industryTermMatches(text: string, term: string): boolean {
    const phrase = term.trim();
    if (!phrase || !text) return false;
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`\\b${escaped}\\b`, 'i').test(text);
}

export function titleMatchesBlocked(title: string, term: string): boolean {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`\\b${escaped}\\b`, 'i').test(title);
}

export function parseMaxYearsRequired(text: string): number | null {
    const patterns = [
        /(?:minimum|min\.?|at least|requires?)\s*(\d+)\s*\+?\s*(?:years?|yrs?)/gi,
        /(\d+)\s*\+\s*years?/gi,
        /(\d+)\s*[-–]\s*(\d+)\s*years?/gi,
        /(\d+)\s+years?\s+(?:of\s+)?experience/gi,
    ];
    const found: number[] = [];
    for (const pat of patterns) {
        let m: RegExpExecArray | null;
        const re = new RegExp(pat.source, pat.flags);
        while ((m = re.exec(text)) !== null) {
            const nums = m.slice(1).filter(Boolean).map((g) => parseInt(g, 10));
            if (nums.length === 1) found.push(nums[0]);
            else if (nums.length >= 2) found.push(Math.max(...nums));
        }
    }
    return found.length ? Math.max(...found) : null;
}

export function passesTitleBlocklist(title: string, config: GateConfig): boolean {
    if (!title) return true;
    return !config.titleBlocklist.some(blocked => titleMatchesBlocked(title, blocked));
}

export function passesIndustryGate(job: ScrapedJob, config: GateConfig): boolean {
    if (!config.blockedIndustries.length) return true;
    for (const term of config.blockedIndustries) {
        if (industryTermMatches(job.company || '', term)) {
            console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
            return false;
        }
        if (industryTermMatches(job.title || '', term)) {
            console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
            return false;
        }
    }
    const desc = (job.description || '').trim();
    if (desc.length > 0 && desc.length <= 120) {
        for (const term of config.blockedIndustries) {
            if (industryTermMatches(desc, term)) {
                console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
                return false;
            }
        }
    }
    return true;
}

export function passesGeographicGate(job: ScrapedJob, config: GateConfig): boolean {
    const text = `${job.title} ${job.description || ''}`.toLowerCase();

    if ((job.description || '').trim().length < 50) {
        if (config.workSetting === 'Remote') {
            if (REMOTE_ONLY_SOURCES.has(job.source)) return true;
            console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - [GEOGRAPHIC REJECT] remote_only_no_location_signal`);
            return false;
        }
        return true;
    }

    const hasLocalSD =
        text.includes('san diego') || text.includes('carlsbad') || text.includes('la jolla') ||
        text.includes('encinitas') || text.includes('del mar') || text.includes('solana beach') ||
        text.includes('ca');

    const hasRemote =
        text.includes('remote') || text.includes('anywhere in') ||
        text.includes('work from home') || text.includes('telecommute');

    const isExplicitForeign = (
        text.includes('canada') || text.includes('united kingdom') || text.includes('london,') ||
        text.includes('europe') || text.includes('germany') || text.includes('india') || text.includes('apac')
    ) && !(
        text.includes('united states') || text.includes('within the us') || text.includes('us citizen')
    );

    if (isExplicitForeign) return false;
    if (hasLocalSD || hasRemote) return true;
    if (REMOTE_ONLY_SOURCES.has(job.source)) return true;
    return false;
}

export function passesSeniorityGate(job: ScrapedJob, config: GateConfig): boolean {
    const title = (job.title || '').trim();
    for (const term of config.titleBlocklist) {
        if (titleMatchesBlocked(title, term)) {
            console.log(`[REJECT] ${title} at ${job.company} — title_blocked:${term}`);
            return false;
        }
    }
    const desc = (job.description || '').trim();
    if (desc.length >= 80) {
        const required = parseMaxYearsRequired(`${title}\n${desc}`);
        if (required !== null && required > config.maxExperienceYears) {
            console.log(`[REJECT] ${title} at ${job.company} — required_years_${required}_exceeds_max_${config.maxExperienceYears}`);
            return false;
        }
    }
    return true;
}
