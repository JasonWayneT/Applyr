import { describe, it, expect } from 'vitest';
import {
  textMatchesLocalArea,
  textHasRemoteSignal,
  passesBuiltInStrictRemoteCard,
  isExplicitForeignLocation,
  normalizeGeoTerms,
} from '../../shared/domain/geoPrefs.js';

describe('geoPrefs', () => {
  it('normalizeGeoTerms lowercases and trims', () => {
    expect(normalizeGeoTerms([' San Diego ', 'Austin, TX'])).toEqual(['san diego', 'austin, tx']);
  });

  it('textMatchesLocalArea uses configured terms only', () => {
    expect(textMatchesLocalArea('Hybrid in San Diego, CA', ['san diego'])).toBe(true);
    expect(textMatchesLocalArea('Hybrid in San Diego, CA', [])).toBe(false);
    expect(textMatchesLocalArea('Hybrid in Austin, TX', ['san diego'])).toBe(false);
  });

  it('textHasRemoteSignal detects remote keywords', () => {
    expect(textHasRemoteSignal('Fully remote US role')).toBe(true);
    expect(textHasRemoteSignal('On-site in Chicago')).toBe(false);
  });

  it('passesBuiltInStrictRemoteCard rejects hybrid combo cards', () => {
    const geo = { localAreaTerms: ['austin'] };
    expect(passesBuiltInStrictRemoteCard('Remote or Hybrid United States', geo)).toBe(false);
    expect(passesBuiltInStrictRemoteCard('Remote United States', geo)).toBe(true);
    expect(passesBuiltInStrictRemoteCard('Austin, TX', geo)).toBe(true);
  });

  it('isExplicitForeignLocation respects US preference', () => {
    expect(isExplicitForeignLocation('Based in London, United Kingdom only', 'United States')).toBe(true);
    expect(
      isExplicitForeignLocation('United Kingdom or United States remote', 'United States'),
    ).toBe(false);
  });
});
