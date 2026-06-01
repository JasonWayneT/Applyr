/**
 * Pure quality-check functions for extracted job descriptions.
 * No I/O, no DOM dependencies — fully unit-testable in Node.js.
 * Used by extract_job_page.ts (post-extraction scoring) and scout_local.ts (ingest gate).
 */

// Substring matches are intentional: "responsibilit" catches both "responsibility" and "responsibilities".
const ROLE_SIGNAL_PHRASES = [
    'responsibilit',
    'requirement',
    'qualif',
    'you will',
    "you'll",
    'about the role',
    "what we're looking for",
    "what you'll do",
    'what you will do',
    'your role',
    'key duties',
    'day-to-day',
    'in this role',
    'the role',
] as const;

export function hasRoleSignal(text: string): boolean {
    if (!text) return false;
    const lower = text.toLowerCase();
    return ROLE_SIGNAL_PHRASES.some(phrase => lower.includes(phrase));
}

export type ExtractionSource = 'structured' | 'dom' | 'body';
export type ExtractionConfidence = 'high' | 'medium' | 'low';

export function classifyConfidence(text: string, source: ExtractionSource): ExtractionConfidence {
    if (!text || text.length < 100) return 'low';
    if (source === 'structured') return 'high';
    if (source === 'dom' && hasRoleSignal(text)) return 'medium';
    return 'low';
}

export function buildDataQualityFlags(
    text: string,
    source: ExtractionSource,
    minChars: number,
): string[] {
    const flags: string[] = [];
    if (!hasRoleSignal(text)) flags.push('no_requirements_section');
    if (text.length < minChars * 2) flags.push('short_jd');
    if (source === 'body') flags.push('body_fallback');
    return flags;
}
