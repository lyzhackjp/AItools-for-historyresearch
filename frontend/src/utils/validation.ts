export function requireText(value: string) {
  return value.trim().length > 0;
}

export function isSafeLocalPath(path: string) {
  return !path.includes('..') && !path.toLowerCase().includes('secrets');
}
