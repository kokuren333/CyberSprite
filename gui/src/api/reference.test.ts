import { describe, expect, it } from 'vitest';
import { REFERENCE_MAX_BYTES, referenceArgs, toBase64 } from './reference';

describe('register_reference arguments', () => {
  it('encodes bytes as standard base64, across chunk boundaries', () => {
    const bytes = new Uint8Array(0x8000 * 2 + 3).map((_, i) => (i * 37) & 0xff);
    expect(toBase64(bytes)).toBe(Buffer.from(bytes).toString('base64'));
    expect(toBase64(new Uint8Array([0x89, 0x50, 0x4e, 0x47]))).toBe('iVBORw==');
  });
  it('trims the rights note and defaults the license to unknown', () => {
    const args = referenceArgs(new Uint8Array([1, 2, 3]), '  measure only ', ' ');
    expect(args).toEqual({ data: 'AQID', rights_note: 'measure only', license: 'unknown' });
    expect(Object.keys(args)).not.toContain('placed_by');
  });
  it('matches the core 5 MiB cap', () => {
    expect(REFERENCE_MAX_BYTES).toBe(5 * 1024 * 1024);
  });
});
