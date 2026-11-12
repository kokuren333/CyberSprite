/** Server-returned paths are relative to its root, never relative to the document. */
export const fileUrl = (path: string) => `/files/${path.split('/').map(encodeURIComponent).join('/')}`;
