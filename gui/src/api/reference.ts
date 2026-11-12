/** Helpers for the register_reference Op (manual reference images, SPEC §3.6). */

/** Decoded size cap shared with the core register_reference Op (5 MiB). */
export const REFERENCE_MAX_BYTES = 5 * 1024 * 1024;
export const REFERENCE_TYPES = ['image/png', 'image/gif', 'image/jpeg', 'image/bmp', 'image/webp'];

/** Standard base64 of raw bytes, chunked so large files do not overflow the call stack. */
export function toBase64(bytes: Uint8Array): string {
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}

/** Arguments for the register_reference Op; the server records placed_by=human-gui. */
export function referenceArgs(bytes: Uint8Array, rightsNote: string, license: string) {
  return { data: toBase64(bytes), rights_note: rightsNote.trim(), license: license.trim() || 'unknown' };
}
