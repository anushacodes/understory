import { useEffect, useRef, useState } from 'react';
import type { Citation, Source } from '../types';
import { Icon } from './Icon';

function highlight(line: string) {
  const pattern = /(#.*$|""".*?"""|'''.*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\b(?:async|await|def|class|return|raise|if|else|elif|for|while|in|not|and|or|import|from|as|with|try|except|None|True|False|self)\b|\b\d[\d_]*\b)/g;
  let last = 0; const parts = []; let match: RegExpExecArray | null;
  while ((match = pattern.exec(line)) !== null) {
    if (match.index > last) parts.push(line.slice(last, match.index));
    const token = match[0];
    const kind = token.startsWith('#') ? 'comment' : /^['"]/.test(token) ? 'string' : /^\d/.test(token) ? 'number' : token === 'self' ? 'self' : 'keyword';
    parts.push(<span className={`syntax-${kind}`} key={match.index}>{token}</span>); last = pattern.lastIndex;
  }
  if (last < line.length) parts.push(line.slice(last));
  return parts;
}

export function SourceViewer({ source, loading, error, citation, citations, tabs, openFile, closeTab, expanded, toggleExpanded, next, previous }: { source: Source | null; loading: boolean; error: string | null; citation: Citation | null; citations: Citation[]; tabs: string[]; openFile: (path: string) => void; closeTab: (path: string) => void; expanded: boolean; toggleExpanded: () => void; next: () => void; previous: () => void }) {
  const [citedOnly, setCitedOnly] = useState(false);
  const [copied, setCopied] = useState(false);
  const selection = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (citation) selection.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [citation, source]);
  const fileCitations = citations.filter(item => item.path === source?.path);
  const lines = source?.content.split('\n') ?? [];
  return <main className={`source-pane ${expanded ? 'source-expanded' : ''}`} aria-label="Source evidence">
    <div className="pane-toolbar source-toolbar"><strong>{source?.path.split('/').at(-1) ?? 'Source evidence'}</strong><span className="file-metadata">{source ? `${source.path.includes('/') ? source.path.slice(0, source.path.lastIndexOf('/')) : 'repository'} · ${source.line_count} lines · indexed at ${source.commit_sha.slice(0, 7)}` : 'Your evidence, in context'}</span><div className="toolbar-actions"><button className="icon-button" title="Copy path" aria-label="Copy path" disabled={!source} onClick={async () => { if (source) { await navigator.clipboard.writeText(source.path); setCopied(true); setTimeout(() => setCopied(false), 1600); } }}><Icon name={copied ? 'check' : 'copy'} /></button>{source?.source_url && <a className="icon-button" href={source.source_url} target="_blank" rel="noreferrer" aria-label="Open pinned source on GitHub" title="Open pinned source on GitHub"><Icon name="external" /></a>}<button className="icon-button" aria-label={expanded ? 'Restore workspace panes' : 'Expand source'} title={expanded ? 'Restore panes' : 'Expand source'} onClick={toggleExpanded}><Icon name={expanded ? 'collapse' : 'expand'} /></button></div></div>
    <div className="source-controls"><div className="segmented"><button className="active" aria-current="page"><Icon name="code" size={13} /> Code</button></div><div className="segmented" role="group" aria-label="Source lines"><button className={citedOnly ? 'active' : ''} aria-pressed={citedOnly} onClick={() => setCitedOnly(true)} disabled={!fileCitations.length}>Cited</button><button className={!citedOnly ? 'active' : ''} aria-pressed={!citedOnly} onClick={() => setCitedOnly(false)}>All</button></div><span className="controls-spacer" />{citation?.path === source?.path && <span className="selection-label">L{citation?.start_line}–{citation?.end_line} selected</span>}</div>
    <div className="code-scroll pane-scroll" aria-busy={loading}>
      {loading ? <div className="source-empty"><Icon name="spinner" className="spin" size={25} /><p>Opening stored source…</p></div> : error ? <div className="source-empty"><Icon name="info" size={28} /><h2>Source unavailable</h2><p role="alert">{error}</p></div> : source ? <div className="code-lines" role="region" aria-label={`${source.path} source code`} tabIndex={0}>{lines.map((line, index) => {
        const number = source.start_line + index;
        const refs = fileCitations.filter(item => item.start_line <= number && item.end_line >= number);
        const selected = citation?.path === source.path && citation.start_line <= number && citation.end_line >= number;
        if (citedOnly && !refs.length) return null;
        return <div className={`code-line ${selected || refs.length ? 'cited-line' : ''}`} key={number} ref={selected && number === citation?.start_line ? selection : undefined} data-line={number}><span className="citation-gutter">{refs.some(item => item.start_line === number) && <span className="citation-number" title={`Evidence ${refs[0].evidence_id}`}>{refs[0].evidence_id.replace(/^e/, '')}</span>}</span><span className="line-number">{number}</span><code>{highlight(line) || ' '}</code></div>;
      })}</div> : <div className="source-empty"><div className="source-empty-icon"><Icon name="code" size={28} /></div><h2>The source tells the story.</h2><p>Choose a file or a citation to inspect the code behind an explanation.</p></div>}
    </div>
    {source && (source.next_start_line || source.start_line > 1) && <div className="source-pagination"><button disabled={source.start_line <= 1} onClick={previous}>Previous lines</button><span>L{source.start_line}–{source.end_line} of {source.line_count}</span><button disabled={!source.next_start_line} onClick={next}>Next lines</button></div>}
    <div className="source-legend"><span><i className="legend-highlight" /> cited lines</span><span><i className="citation-number">1</i> source number</span>{source && <span className="source-kind">{source.kind} · {source.state === 'parse_failed' ? 'parse failed' : 'stored source'}</span>}</div>
    <div className="file-tabs" aria-label="Open files">{tabs.map(path => <div className={`file-tab ${path === source?.path ? 'active' : ''}`} key={path}><button onClick={() => openFile(path)} title={path}><Icon name="file" size={13} />{path.split('/').at(-1)}</button><button className="close-file" aria-label={`Close ${path}`} onClick={() => closeTab(path)}><Icon name="close" size={11} /></button></div>)}</div>
  </main>;
}
