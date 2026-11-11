import React, { useMemo } from 'react';
import katex from 'katex';

type Segment =
  | { kind: 'text'; value: string }
  | { kind: 'math'; value: string; display: boolean };

/** Split plain AI text into prose + LaTeX segments (\( \), \[ \], $, $$). */
function splitLatex(input: string): Segment[] {
  if (!input) return [{ kind: 'text', value: '' }];
  const pattern =
    /\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
  const parts: Segment[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(input)) !== null) {
    if (match.index > last) {
      parts.push({ kind: 'text', value: input.slice(last, match.index) });
    }
    if (match[1] != null) {
      parts.push({ kind: 'math', value: match[1].trim(), display: true });
    } else if (match[2] != null) {
      parts.push({ kind: 'math', value: match[2].trim(), display: false });
    } else if (match[3] != null) {
      parts.push({ kind: 'math', value: match[3].trim(), display: true });
    } else if (match[4] != null) {
      parts.push({ kind: 'math', value: match[4].trim(), display: false });
    }
    last = match.index + match[0].length;
  }
  if (last < input.length) {
    parts.push({ kind: 'text', value: input.slice(last) });
  }
  return parts.length ? parts : [{ kind: 'text', value: input }];
}

function renderMath(tex: string, display: boolean): string {
  try {
    return katex.renderToString(tex, {
      displayMode: display,
      throwOnError: false,
      strict: 'ignore',
      trust: false,
    });
  } catch {
    return tex;
  }
}

type Props = {
  text: string;
  className?: string;
  as?: 'div' | 'span' | 'p';
};

/** Renders mixed prose + LaTeX for faculty-facing AI evidence / working. */
export const LatexText: React.FC<Props> = ({ text, className = '', as = 'div' }) => {
  const segments = useMemo(() => splitLatex(text || ''), [text]);
  const Tag = as;

  return (
    <Tag className={`latex-text ${className}`.trim()}>
      {segments.map((seg, i) => {
        if (seg.kind === 'text') {
          return (
            <React.Fragment key={i}>
              {seg.value}
            </React.Fragment>
          );
        }
        const html = renderMath(seg.value, seg.display);
        return (
          <span
            key={i}
            className={seg.display ? 'block my-2 overflow-x-auto' : 'inline-block align-middle'}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </Tag>
  );
};
