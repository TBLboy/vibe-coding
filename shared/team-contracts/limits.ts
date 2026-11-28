export const MAX_DOCUMENT_BYTES = 1024 * 1024;
export const MAX_BODY = 2 * 1024 * 1024;
export const MAX_DOCUMENT_BODY = 7 * 1024 * 1024;
export const MAX_IMPORT_BODY = 32 * 1024 * 1024;
export const validText = (content: string): boolean => !/[\uD800-\uDFFF]/u.test(content);
export function decodeText(bytes: Uint8Array): string { return new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(bytes); }
/** Compare path segments under conservative case folding; exact same path is an update, not a collision. */
export function pathsCollide(a: string, b: string): boolean {
  if (a === b) return false;
  const left=a.split('/'), right=b.split('/');
  for (let i=0;i<Math.min(left.length,right.length);i++) {
    if (left[i].toLowerCase() !== right[i].toLowerCase()) return false;
    if (left[i] !== right[i]) return true;
  }
  return true; // same folded path or file/directory prefix
}
