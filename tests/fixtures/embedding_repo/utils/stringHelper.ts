export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function slugify(text: string): string {
  return text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]+/g, '');
}

export function camelCase(text: string): string {
  return text.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}
