import React, { useMemo } from 'react';
import { marked } from 'marked';

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

const customRenderer = {
  heading({ tokens, depth }) {
    const text = this.parser.parseInline(tokens);
    const sizes = {
      1: 'text-[16px] font-medium text-ink mt-3 mb-1.5 pb-1 border-b border-line',
      2: 'text-[14.5px] font-medium text-ink mt-2.5 mb-1',
      3: 'text-[13px] font-medium text-ash mt-2 mb-1',
      4: 'text-[12.5px] font-medium text-ash mt-1.5 mb-0.5',
    };
    const cls = sizes[depth] || sizes[4];
    return `<h${depth} class="font-disp ${cls}">${text}</h${depth}>`;
  },

  code({ text, lang }) {
    const language = (lang || 'code').trim().toLowerCase();
    const encoded = encodeURIComponent(text);
    return `<div class="code-block my-2.5 rounded-ui border border-line overflow-hidden bg-[var(--termbg)] shadow-sm">
      <div class="code-header px-3 py-1.5 border-b border-line bg-inset/60 flex items-center justify-between text-[10px] font-mono select-none">
        <span class="uppercase tracking-wider font-medium text-cyan">${escapeHtml(language)}</span>
        <button type="button" class="copy-code-btn hover:text-ink text-mut transition-colors uppercase tracking-wider text-[9.5px] px-2 py-0.5 rounded-full border border-line bg-inset hover:bg-hover cursor-pointer" data-code="${encoded}">
          copier
        </button>
      </div>
      <pre class="p-3 overflow-x-auto text-[11.5px] font-mono leading-relaxed text-[var(--term-ink)] select-text m-0"><code>${escapeHtml(text)}</code></pre>
    </div>`;
  },

  codespan({ text }) {
    return `<code class="px-1.5 py-0.5 rounded-[5px] bg-inset border border-line text-cyan font-mono text-[11px] select-text">${escapeHtml(text)}</code>`;
  },

  list({ items, ordered, start }) {
    const tag = ordered ? 'ol' : 'ul';
    const cls = ordered
      ? 'list-decimal list-outside ml-4 space-y-1 my-1.5 text-ash text-[12.5px]'
      : 'list-disc list-outside ml-4 space-y-1 my-1.5 text-ash text-[12.5px]';
    let body = '';
    for (const item of items) {
      body += this.listitem(item);
    }
    return `<${tag} class="${cls}">${body}</${tag}>`;
  },

  listitem(item) {
    const text = this.parser.parse(item.tokens, !!item.loose);
    return `<li class="leading-relaxed">${text}</li>`;
  },

  paragraph({ tokens }) {
    const text = this.parser.parseInline(tokens);
    return `<p class="my-1.5 leading-relaxed text-ash text-[12.5px] break-words">${text}</p>`;
  },

  blockquote({ tokens }) {
    const text = this.parser.parse(tokens);
    return `<blockquote class="border-l-2 border-cyan/60 pl-3 my-2 text-mut italic bg-inset/30 py-1 rounded-r-ui">${text}</blockquote>`;
  },

  table({ header, rows }) {
    let headerHtml = '';
    for (const cell of header) {
      headerHtml += `<th class="px-3 py-1.5 text-left text-[11px] font-mono uppercase tracking-wider text-ink border-b border-line bg-inset/50">${this.parser.parseInline(cell.tokens)}</th>`;
    }
    let bodyHtml = '';
    for (const row of rows) {
      bodyHtml += '<tr class="border-b border-line/60 hover:bg-hover transition-colors">';
      for (const cell of row) {
        bodyHtml += `<td class="px-3 py-1.5 text-[12px] font-mono text-ash">${this.parser.parseInline(cell.tokens)}</td>`;
      }
      bodyHtml += '</tr>';
    }
    return `<div class="my-2.5 overflow-x-auto rounded-ui border border-line">
      <table class="w-full border-collapse divide-y divide-line">${headerHtml ? `<thead><tr>${headerHtml}</tr></thead>` : ''}<tbody>${bodyHtml}</tbody></table>
    </div>`;
  },

  link({ href, title, tokens }) {
    const text = this.parser.parseInline(tokens);
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
    return `<a href="${escapeHtml(href)}"${titleAttr} target="_blank" rel="noopener noreferrer" class="text-cyan hover:underline underline-offset-2 transition-colors">${text}</a>`;
  },

  strong({ tokens }) {
    return `<strong class="font-medium text-ink">${this.parser.parseInline(tokens)}</strong>`;
  },

  em({ tokens }) {
    return `<em class="italic text-ash">${this.parser.parseInline(tokens)}</em>`;
  },

  hr() {
    return `<hr class="my-3 border-line" />`;
  },
};

marked.use({
  renderer: customRenderer,
  gfm: true,
  breaks: true,
});

export default function MarkdownMessage({ content = '', isStreaming = false }) {
  const parsedHtml = useMemo(() => {
    if (!content) return '';
    let textToParse = content;
    if (isStreaming) {
      const codeBlockMatches = textToParse.match(/```/g);
      if (codeBlockMatches && codeBlockMatches.length % 2 !== 0) {
        textToParse += '\n```';
      }
    }
    try {
      return marked.parse(textToParse);
    } catch {
      return `<p class="text-[12.5px] leading-relaxed text-ash whitespace-pre-wrap break-words">${escapeHtml(content)}</p>`;
    }
  }, [content, isStreaming]);

  const handleContainerClick = (e) => {
    const btn = e.target.closest('.copy-code-btn');
    if (!btn) return;
    const rawCode = btn.dataset.code;
    if (!rawCode) return;
    const decoded = decodeURIComponent(rawCode);
    navigator.clipboard.writeText(decoded).then(() => {
      const originalText = btn.textContent;
      btn.textContent = 'copié ✓';
      btn.classList.add('text-ok', 'border-ok/40');
      setTimeout(() => {
        btn.textContent = originalText;
        btn.classList.remove('text-ok', 'border-ok/40');
      }, 2000);
    });
  };

  return (
    <div
      onClick={handleContainerClick}
      className="markdown-content text-[12.5px] leading-relaxed"
      dangerouslySetInnerHTML={{ __html: parsedHtml }}
    />
  );
}
