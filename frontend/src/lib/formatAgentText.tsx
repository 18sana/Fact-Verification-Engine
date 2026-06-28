import type { Evidence } from '@/types';

const UUID_REGEX =
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

/** Build lookup from evidence id → display index & metadata */
export function buildEvidenceIndex(evidence: Evidence[]) {
  const byId = new Map<string, { num: number; ev: Evidence }>();
  evidence.forEach((ev, i) => {
    byId.set(ev.id.toLowerCase(), { num: i + 1, ev });
  });
  return byId;
}

/** Replace raw UUIDs and "(IDs ...)" blocks with readable [n] Source labels */
export function sanitizeAgentText(text: string, evidence: Evidence[]): string {
  if (!text) return '';
  const index = buildEvidenceIndex(evidence);

  let cleaned = text.replace(
    /\(IDs?\s*([0-9a-f-,\s]+)\)/gi,
    (_, idList: string) => {
      const ids = idList.match(UUID_REGEX) ?? [];
      const refs = ids
        .map((id) => index.get(id.toLowerCase()))
        .filter(Boolean)
        .map((r) => `[${r!.num}]`);
      return refs.length ? `(${refs.join(', ')})` : '';
    }
  );

  cleaned = cleaned.replace(
    /\[(?:Evidence|Source|Ref)\s*#?(\d+)\]/gi,
    '[$1]',
  );

  cleaned = cleaned.replace(UUID_REGEX, (uuid) => {
    const hit = index.get(uuid.toLowerCase());
    return hit ? `[${hit.num}]` : '';
  });

  // Collapse leftover empty parens, replacement chars, and double spaces
  return cleaned
    .replace(/\uFFFD/g, '')
    .replace(/\[\?\]/g, '')
    .replace(/\(\?\)/g, '')
    .replace(/\(\s*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.])/g, '$1')
    .trim();
}

export type TextBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] };

/** Split reasoning into paragraphs and bullet lists for structured display */
export function parseReasoningBlocks(text: string): TextBlock[] {
  const blocks: TextBlock[] = [];
  const sections = text.split(/\n\n+/).map((s) => s.trim()).filter(Boolean);

  for (const section of sections) {
    const lines = section.split('\n').map((l) => l.trim()).filter(Boolean);
    const isList = lines.length > 1 && lines.every((l) => /^[-*•]\s|^\d+[.)]\s/.test(l));

    if (isList) {
      blocks.push({
        type: 'list',
        items: lines.map((l) => l.replace(/^[-*•]\s|^\d+[.)]\s/, '')),
      });
    } else if (lines.length > 1 && lines.some((l) => /^[-*•]\s|^\d+[.)]\s/.test(l))) {
      // Mixed: flush non-list lines then list
      const prose: string[] = [];
      const listItems: string[] = [];
      for (const line of lines) {
        if (/^[-*•]\s|^\d+[.)]\s/.test(line)) {
          listItems.push(line.replace(/^[-*•]\s|^\d+[.)]\s/, ''));
        } else {
          prose.push(line);
        }
      }
      if (prose.length) blocks.push({ type: 'paragraph', text: prose.join(' ') });
      if (listItems.length) blocks.push({ type: 'list', items: listItems });
    } else {
      blocks.push({ type: 'paragraph', text: section.replace(/\n/g, ' ') });
    }
  }

  if (!blocks.length && text.trim()) {
    blocks.push({ type: 'paragraph', text: text.trim() });
  }

  return blocks;
}

export function isValidUrl(url?: string): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}
