// Changelog'ni xavfsiz ko'rsatish — `dangerouslySetInnerHTML` YO'Q, faqat matn bolalari (React o'zi escape qiladi).
// Qoʻllab-quvvatlanadi: `##`/`###` sarlavha, `-`/`*` roʻyxat, `**qalin**`, `` `kod` ``. Qolgani oddiy paragraf.
import { Fragment, type ReactNode } from 'react';
import { parseMarkdownLite, tokenizeInline, type InlineToken } from '@/domain/update';

function renderInline(text: string): ReactNode {
  return tokenizeInline(text).map((tok: InlineToken, i) => {
    if (tok.type === 'bold') return <strong key={i} className="font-semibold text-fg">{tok.value}</strong>;
    if (tok.type === 'code') return <code key={i} className="num rounded-sm bg-surface-2 px-1 py-0.5 text-[0.85em]">{tok.value}</code>;
    return <Fragment key={i}>{tok.value}</Fragment>;
  });
}

export function MarkdownLite({ text }: { text: string }) {
  const blocks = parseMarkdownLite(text);
  return (
    <div className="flex flex-col gap-2 text-sm text-fg">
      {blocks.map((b, i) => {
        if (b.type === 'heading') {
          const Tag = b.level === 2 ? 'h3' : 'h4';
          return <Tag key={i} className="font-display font-semibold text-fg">{renderInline(b.text)}</Tag>;
        }
        if (b.type === 'list') {
          return (
            <ul key={i} className="list-inside list-disc space-y-0.5">
              {b.items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
            </ul>
          );
        }
        return <p key={i}>{renderInline(b.text)}</p>;
      })}
    </div>
  );
}
