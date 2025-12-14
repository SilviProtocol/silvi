/**
 * Utility functions for parsing and formatting species data
 */

/**
 * Check if a value is available (not null, undefined, empty, or "NA")
 */
export function isDataAvailable(value: string | null | undefined): boolean {
  if (!value) return false;
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  return trimmed !== '' && trimmed !== 'NA';
}

/**
 * Parse semicolon-separated values into an array
 * Filters out empty values and "NA"
 */
export function parseSemicolonList(value: string | null | undefined): string[] {
  if (!isDataAvailable(value)) return [];

  return value!
    .split(';')
    .map(v => v.trim())
    .filter(v => v !== '' && v !== 'NA');
}

/**
 * Parse numeric range from semicolon-separated values
 * Returns {min, max} or null if no valid data
 */
export function parseNumericRange(value: string | null | undefined): { min: number; max: number } | null {
  if (!isDataAvailable(value)) return null;

  const parts = value!
    .split(';')
    .map(p => parseFloat(p.trim()))
    .filter(n => !isNaN(n));

  if (parts.length === 0) return null;

  return {
    min: Math.min(...parts),
    max: Math.max(...parts)
  };
}

/**
 * Format a numeric range for display
 */
export function formatRange(min: number, max: number, unit: string = '', decimals: number = 0): string {
  const minStr = decimals > 0 ? min.toFixed(decimals) : Math.round(min).toString();
  const maxStr = decimals > 0 ? max.toFixed(decimals) : Math.round(max).toString();

  if (minStr === maxStr) {
    return `${minStr}${unit}`;
  }

  return `${minStr}-${maxStr}${unit}`;
}

/**
 * Truncate a list and return display array with "+N more" indicator
 */
export function truncateList<T>(
  items: T[],
  maxVisible: number = 5
): { visible: T[]; remaining: number } {
  if (items.length <= maxVisible) {
    return { visible: items, remaining: 0 };
  }

  return {
    visible: items.slice(0, maxVisible),
    remaining: items.length - maxVisible
  };
}

/**
 * Parse Köppen climate codes and descriptions
 * Returns array of {code, description} objects
 */
export function parseKoppenCodes(value: string | null | undefined): Array<{ code: string; description: string }> {
  const items = parseSemicolonList(value);

  return items.map(item => {
    const match = item.match(/^([A-Z][A-Za-z]+)\s*-\s*(.+)$/);
    if (match) {
      return { code: match[1], description: match[2] };
    }
    // Fallback if format doesn't match
    return { code: item, description: item };
  });
}
