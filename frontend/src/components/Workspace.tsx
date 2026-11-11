import { useEffect, useRef, useState } from 'react';
import { allPages, api, download, params, post } from '../api';
import type { Accepted, Capabilities, Citation, FileEntry, Job, Repository, Run, RunSummary, SearchResponse, Snapshot, Source } from '../types';
import { useJob } from '../useJob';
import { FileTree } from './FileTree';
import { Icon, Wordmark } from './Icon';
import { SourceViewer } from './SourceViewer';

type Mode = 'overview' | 'ask' | 'search' | 'history';
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';

export function Workspace({ dark, toggleTheme, home, capabilities, initialQuery }: { dark: boolean; toggleTheme: () => void; home: () => void; capabilities: Capabilities; initialQuery: string }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [repoId, setRepoId] = useState(localStorage.getItem('understory-repository') ?? '');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotId, setSnapshotId] = useState('');
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [fileFilter, setFileFilter] = useState('');
  const [source, setSource] = useState<Source | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [tabs, setTabs] = useState<string[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [mobilePane, setMobilePane] = useState('question');
  const [mode, setMode] = useState<Mode>('overview');
  const [question, setQuestion] = useState(initialQuery.includes('/') ? '' : initialQuery);
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState('lexical');
  const [sourceKind, setSourceKind] = useState('');
  const [pathPrefix, setPathPrefix] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [importName, setImportName] = useState(initialQuery.includes('/') ? initialQuery : 'understory/fixture');
  const [importRef, setImportRef] = useState('main');
  const [collapsed, setCollapsed] = useState(false);
  const [repoLoading, setRepoLoading] = useState(true);
  const sourceRequest = useRef<AbortController | null>(null);
  const repo = repositories.find(item => item.id === repoId);
  const snapshot = snapshots.find(item => item.id === snapshotId);
  const coverage = snapshot?.coverage ?? repo?.coverage;
  const lastRunId = repoId ? localStorage.getItem(`understory-run-${repoId}`) : null;

  useEffect(() => {
    const controller = new AbortController();
    allPages<Repository>('/repositories', controller.signal).then(items => {
      setRepositories(items);
      if (items.length) setRepoId(current => items.some(item => item.id === current) ? current : items[0].id);
      else { setRepoId(''); setShowImport(true); }
    }).catch(error => { if (!controller.signal.aborted) setError(errorText(error)); }).finally(() => { if (!controller.signal.aborted) setRepoLoading(false); });
    return () => { controller.abort(); sourceRequest.current?.abort(); };
  }, []);

  useEffect(() => {
    if (!repoId) return;
    const controller = new AbortController();
    api<Repository>(`/repositories/${repoId}`, { signal: controller.signal }).then(updated => {
      if (controller.signal.aborted) return;
      setRepositories(items => items.map(item => item.id === updated.id ? updated : item));
      const pending = updated.jobs?.find(item => !['succeeded', 'failed', 'cancelled'].includes(item.status));
      if (pending) setJobId(pending.id);
    }).catch(error => { if (!controller.signal.aborted) setError(errorText(error)); });
    return () => controller.abort();
  }, [repoId]);

  useEffect(() => {
    if (!repoId) return;
    localStorage.setItem('understory-repository', repoId);
    const controller = new AbortController();
    allPages<Snapshot>(`/repositories/${repoId}/snapshots`, controller.signal).then(items => {
      setSnapshots(items);
      const selected = repositories.find(item => item.id === repoId)?.active_snapshot_id;
      setSnapshotId(current => items.some(item => item.id === current) ? current : selected ?? items.at(-1)?.id ?? '');
    }).catch(error => { if (!controller.signal.aborted) setError(errorText(error)); });
    return () => controller.abort();
  }, [repoId, repositories]);

  useEffect(() => {
    if (!repoId || !snapshotId) { setFiles([]); return; }
    const controller = new AbortController();
    allPages<FileEntry>(`/repositories/${repoId}/tree${params({ snapshot_id: snapshotId })}`, controller.signal).then(setFiles).catch(error => { if (!controller.signal.aborted) setError(errorText(error)); });
    return () => controller.abort();
  }, [repoId, snapshotId]);

  const job = useJob(jobId, terminal => {
    if (terminal.kind === 'import' && terminal.status === 'succeeded') {
      api<Repository>(`/repositories/${terminal.repository_id ?? repoId}`).then(updated => setRepositories(items => items.map(item => item.id === updated.id ? updated : item))).catch(error => setError(errorText(error)));
    }
    if (terminal.result?.run_id) void openRun(String(terminal.result.run_id));
  });

  function chooseRepository(id: string) {
    sourceRequest.current?.abort(); setRepoId(id); setSnapshotId(''); setSource(null); setTabs([]); setRun(null); setResults(null); setSelectedCitation(null); setError(null); setMode('overview'); setJobId(null);
  }
  function chooseSnapshot(id: string) {
    sourceRequest.current?.abort(); setSnapshotId(id); setSource(null); setRun(null); setResults(null); setSelectedCitation(null); setTabs([]); setError(null);
  }
  async function openFile(path: string, citation: Citation | null = null, targetSnapshot = snapshotId, start = 1) {
    if (!repoId || !targetSnapshot) return;
    sourceRequest.current?.abort(); const controller = new AbortController(); sourceRequest.current = controller;
    setSourceLoading(true); setSourceError(null); setSelectedCitation(citation); setMobilePane('source');
    if (citation) start = Math.max(1, citation.start_line - 8);
    try {
      const result = await api<Source>(`/repositories/${repoId}/files${params({ path, snapshot_id: targetSnapshot, start_line: start })}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setSource(result); setTabs(items => items.includes(path) ? items : [...items.slice(-7), path]);
    } catch (error) { if (!controller.signal.aborted) { setSource(null); setSourceError(errorText(error)); } }
    finally { if (!controller.signal.aborted) setSourceLoading(false); }
  }
  async function openRun(id: string) {
    try {
      const next = await api<Run>(`/runs/${id}`);
      setRun(next); setSnapshotId(next.snapshot_id); setMode('ask'); setError(null); setSelectedCitation(null); setResults(null);
      localStorage.setItem(`understory-run-${repoId}`, next.id);
      if (next.output?.citations[0]) void openFile(next.output.citations[0].path, next.output.citations[0], next.snapshot_id);
    } catch (error) { setError(errorText(error)); }
  }
  async function requestImport(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const target = await post<Repository>('/repositories', { github_repository: importName, default_ref: importRef });
      const accepted = await post<Accepted>(`/repositories/${target.id}/imports`, { ref: importRef });
      setRepositories(items => items.some(item => item.id === target.id) ? items : [...items, target]);
      if (target.id !== repoId) chooseRepository(target.id);
      setJobId(accepted.job_id); setShowImport(false);
    } catch (error) { setError(errorText(error)); }
    finally { setBusy(false); }
  }
  async function submitQuestion(event?: React.FormEvent, overview = false) {
    event?.preventDefault(); if (!repoId || !snapshotId) return;
    setBusy(true); setError(null); setRun(null); setMode('ask'); setMobilePane('question');
    try {
      const accepted = await post<Accepted>(`/repositories/${repoId}/${overview ? 'overviews' : 'questions'}`, overview ? { snapshot_id: snapshotId } : { question, snapshot_id: snapshotId, retrieval_mode: coverage?.capabilities.includes('hybrid') ? 'hybrid' : 'lexical' });
      setJobId(accepted.job_id); setQuestion('');
      if (accepted.run_id) { const next = await api<Run>(`/runs/${accepted.run_id}`); setRun(next); localStorage.setItem(`understory-run-${repoId}`, next.id); }
    } catch (error) { setError(errorText(error)); }
    finally { setBusy(false); }
  }
  async function submitSearch(event: React.FormEvent) {
    event.preventDefault(); if (!snapshotId || !query.trim()) return;
    setBusy(true); setError(null); setRun(null);
    try { setResults(await api<SearchResponse>(`/repositories/${repoId}/search${params({ query, mode: searchMode, snapshot_id: snapshotId, kinds: sourceKind, path_prefix: pathPrefix })}`)); }
    catch (error) { setError(errorText(error)); setResults(null); }
    finally { setBusy(false); }
  }
  async function showHistory() {
    setMode('history'); setMobilePane('question'); setError(null);
    try { setHistory(await allPages<RunSummary>(`/repositories/${repoId}/runs`)); } catch (error) { setError(errorText(error)); }
  }
  const activeJob = job && !['succeeded', 'failed', 'cancelled'].includes(job.status);
  const citations = run?.output?.citations ?? results?.results ?? [];

  return <div className={`workspace ${expanded ? 'expanded-workspace' : ''} ${collapsed ? 'sidebar-collapsed' : ''}`} data-mobile-pane={mobilePane}>
    <div className="mobile-tabs"><button className={mobilePane === 'files' ? 'active' : ''} onClick={() => setMobilePane('files')}><Icon name="folder" />Files</button><button className={mobilePane === 'question' ? 'active' : ''} onClick={() => setMobilePane('question')}><Icon name="search" />Workspace</button><button className={mobilePane === 'source' ? 'active' : ''} onClick={() => setMobilePane('source')}><Icon name="code" />Source</button></div>
    <aside className="repository-pane" aria-label="Repository">
      <div className="pane-toolbar sidebar-brand"><Wordmark onClick={home} /><button className="icon-button collapse-sidebar" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}><Icon name={collapsed ? 'chevron' : 'collapse'} size={15} /></button></div>
      <div className="sidebar-top"><label className="repository-picker"><span className="repository-symbol"><Icon name="branch" size={17} /></span><span><select aria-label="Repository" value={repoId} onChange={event => chooseRepository(event.target.value)}><option value="" disabled>{repoLoading ? 'Loading repositories…' : 'Choose a repository'}</option>{repositories.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select><span className="repository-ref">{repo ? `${repo.default_ref} @ ${snapshot?.commit_sha.slice(0, 7) ?? 'not indexed'}` : 'Your source, in context'}</span></span></label>
      {snapshots.length > 1 && <select className="snapshot-select" aria-label="Selected snapshot" value={snapshotId} onChange={event => chooseSnapshot(event.target.value)}>{snapshots.map(item => <option key={item.id} value={item.id}>{item.commit_sha.slice(0, 7)} · {new Date(item.ready_at).toLocaleDateString()}</option>)}</select>}
      <div className="segmented sidebar-segments"><button className={mode !== 'search' ? 'active' : ''} onClick={() => setMode('overview')}>Files</button><button className={mode === 'search' ? 'active' : ''} onClick={() => { setMode('search'); setMobilePane('question'); }}>Search</button></div>
      <label className="file-filter"><Icon name="search" size={14} /><span className="sr-only">Search files</span><input value={fileFilter} onChange={event => setFileFilter(event.target.value)} placeholder="Search files" /></label></div>
      <FileTree files={files} selected={source?.path ?? ''} openFile={path => void openFile(path)} filter={fileFilter} />
      <div className="sidebar-bottom"><div className="index-summary"><span><i className={`status-dot ${activeJob ? 'working-dot' : ''}`} />{snapshotId ? 'Indexed' : activeJob ? 'Indexing' : 'Not indexed'}</span><span className="mono">{coverage ? `${coverage.included_files} files` : 'code · tests · docs'}</span></div>{coverage?.synthetic && <span className="synthetic-label">Synthetic example repository</span>}
      <button className="sidebar-action" onClick={() => { setMode('overview'); setMobilePane('question'); }}><Icon name="book" />Overview</button><button className="sidebar-action" onClick={() => { setMode('ask'); setRun(null); setResults(null); setError(null); setMobilePane('question'); }}><Icon name="plus" />New question</button><button className="sidebar-action" disabled={!repoId} onClick={() => void showHistory()}><Icon name="history" />History</button><button className="sidebar-action" onClick={() => { setShowImport(!showImport); setMobilePane('question'); }}><Icon name="refresh" />Import repository</button><div className="sidebar-footer"><button className="icon-button" onClick={toggleTheme} aria-label={dark ? 'Use light theme' : 'Use dark theme'}><Icon name={dark ? 'sun' : 'moon'} /></button><span>Source-backed understanding</span></div></div>
    </aside>
    <section className="question-pane" aria-label="Question and search">
      <div className="pane-toolbar question-toolbar"><strong>{mode === 'search' ? 'Search the repository' : mode === 'history' ? 'Previous questions' : mode === 'overview' ? 'Repository overview' : run?.kind === 'overview' ? 'Architecture overview' : 'Understand the code'}</strong>{run?.output && <button className="icon-button" onClick={() => void download(`/runs/${run.id}/export`, `understory-${run.id}.json`).catch(error => setError(errorText(error)))} aria-label="Export answer" title="Export answer and evidence"><Icon name="download" size={15} /></button>}</div>
      <div className="question-content pane-scroll">
        {error && <div className="error-message" role="alert"><Icon name="info" size={15} />{error}</div>}
        {showImport && <form className="import-form" onSubmit={requestImport}><h2>Bring a repository<br /><em>into focus.</em></h2><p>Import an approved public Python repository, or explore the synthetic example.</p><label htmlFor="repo-name">GitHub repository</label><input id="repo-name" value={importName} onChange={event => setImportName(event.target.value)} placeholder="owner/repository" required /><label htmlFor="repo-ref">Branch, tag, or commit</label><input id="repo-ref" value={importRef} onChange={event => setImportRef(event.target.value)} required /><button className="solid" disabled={busy}>{busy ? <Icon name="spinner" className="spin" /> : <Icon name="plus" />} Import repository</button><p className="small-note">Owner-managed imports. Downloaded code is never executed. Approved: {capabilities.allowed_repositories.join(', ')}.</p></form>}
        {job && <JobPanel job={job} cancel={async () => { await post(`/jobs/${job.id}/cancel`, {}); }} />}
        {!showImport && mode === 'overview' && <div className="overview-content"><h1>{repo ? repo.name.split('/').at(-1) : 'A new perspective\non your code.'}</h1><p className="intro-copy">{repo ? 'Explore the structure. Find the behavior. Follow the evidence.' : 'Start with a small public Python repository. We’ll keep the source close, and the answers grounded.'}</p>{coverage ? <><dl className="inventory"><div><dt>Supported files</dt><dd>{coverage.included_files}</dd></div><div><dt>Symbols</dt><dd>{coverage.symbols}</dd></div><div><dt>Searchable passages</dt><dd>{coverage.passages}</dd></div><div><dt>Excluded files</dt><dd>{coverage.excluded_files + coverage.parse_failed_files}</dd></div></dl><div className="baseline-note"><Icon name="branch" /><span>Selected baseline <code>{snapshot?.commit_sha.slice(0, 7)}</code><small>{snapshot ? new Date(snapshot.ready_at).toLocaleString() : ''}</small></span></div>{coverage.partial && <p className="coverage-note">Partial source coverage. Skipped paths and reasons remain visible in the file tree.</p>}<button className="solid overview-button" disabled={busy || !capabilities.generation_enabled || coverage.empty} onClick={() => void submitQuestion(undefined, true)}><Icon name="book" />Generate cited overview</button>{!capabilities.generation_enabled && <p className="small-note">Generated explanations are not enabled yet. Configure Groq in the server environment. You can explore files and search now.</p>}<div className="starter-questions"><h3>A few places to start</h3>{['Where are incoming requests validated?', 'How does the request reach storage?', 'What are the main modules?'].map(text => <button key={text} onClick={() => { setQuestion(text); setMode(capabilities.generation_enabled ? 'ask' : 'search'); setQuery(text); }}><span>{text}</span><Icon name="arrow" size={14} /></button>)}</div></> : !repoLoading && <button className="solid" onClick={() => setShowImport(true)}>Import your first repository <Icon name="arrow" /></button>}</div>}
        {!showImport && mode === 'search' && <><form className="repository-search" onSubmit={submitSearch}><label htmlFor="source-query">Find the code you’re looking for.</label><div className="query-field"><Icon name="search" /><input id="source-query" value={query} onChange={event => setQuery(event.target.value)} placeholder="Symbol, behavior, or concept" required autoFocus /><button className="icon-button solid" aria-label="Run search" disabled={busy || !snapshotId}><Icon name={busy ? 'spinner' : 'arrow'} className={busy ? 'spin' : ''} /></button></div><div className="search-filters"><select aria-label="Search mode" value={searchMode} onChange={event => setSearchMode(event.target.value)}><option value="lexical">Lexical</option><option value="exact">Exact symbol</option><option value="semantic">Semantic</option><option value="hybrid">Hybrid</option></select><select aria-label="Source kind" value={sourceKind} onChange={event => setSourceKind(event.target.value)}><option value="">All sources</option><option value="code">Code</option><option value="test">Tests</option><option value="doc">Docs</option><option value="config">Config</option></select></div><input className="path-filter" aria-label="Path prefix" placeholder="Filter by path, e.g. app/" value={pathPrefix} onChange={event => setPathPrefix(event.target.value)} /></form>{results && <div className="search-results"><div className="result-summary">{results.results.length} results <span>{results.effective_mode} retrieval</span></div>{results.warnings.map(warning => <p className="coverage-note" key={warning}>{warning}</p>)}{results.results.length ? results.results.map((item, index) => <button className="search-result" key={item.evidence_id} onClick={() => void openFile(item.path, item)}><span className="result-path"><Icon name="file" size={13} />{item.path}<span>L{item.start_line}–{item.end_line}</span></span><strong>{item.label}</strong><pre>{item.excerpt.split('\n').slice(0, 4).join('\n')}</pre><span className="result-kind">{item.kind} <span>{index + 1}</span></span></button>) : <div className="empty-state"><Icon name="search" size={24} /><h2>No evidence found.</h2><p>Try a symbol name, fewer words, or a different filter. A missing result does not establish that a behavior is absent.</p></div>}</div>}</>}
        {!showImport && mode === 'history' && <div className="history-list">{history.length ? [...history].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(item => <button key={item.id} onClick={() => void openRun(item.id)}><Icon name={item.kind === 'overview' ? 'book' : 'history'} /><span>{item.kind === 'overview' ? 'Repository overview' : item.question}<small>{new Date(item.created_at).toLocaleString()}</small></span><Icon name="chevron" size={13} /></button>) : <div className="empty-state"><Icon name="history" size={26} /><h2>A fresh page.</h2><p>Your questions and generated overviews will stay here with their original evidence.</p></div>}</div>}
        {!showImport && mode === 'ask' && <div className="answer-content">{run && <h1 className="question-heading">{run.kind === 'overview' ? 'How this repository fits together' : run.question}</h1>}{run?.output ? <><div className="answer-baseline"><Icon name="branch" size={13} /><code>{run.output.commit_sha.slice(0, 7)}</code><span>{run.output.outcome.replaceAll('_', ' ')}</span></div>{run.output.segments.map((segment, index) => <p className="answer-paragraph" key={index}>{segment.text} {segment.evidence_ids.map(id => { const item = run.output?.citations.find(e => e.evidence_id === id); return item ? <button className="citation-number" key={id} title={`${item.path} L${item.start_line}–${item.end_line}`} onClick={() => void openFile(item.path, item, run.snapshot_id)}>{id.replace(/^e/, '')}</button> : null; })}</p>)}{run.output.gaps.length > 0 && <div className="evidence-gaps"><h3>What remains unclear</h3>{run.output.gaps.map(gap => <p key={gap}>{gap}</p>)}</div>}<div className="answer-limitations">{run.output.limitations.map(limit => <p key={limit}>{limit}</p>)}<p>{run.output.coverage.inspected_files} files inspected · {run.output.coverage.included_files} indexed files</p></div><div className="answer-sources"><h3>Sources inspected</h3>{run.output.citations.map(item => <button key={item.evidence_id} onClick={() => void openFile(item.path, item, run.snapshot_id)}><span className="citation-number">{item.evidence_id.replace(/^e/, '')}</span><span>{item.path}<small>L{item.start_line}–{item.end_line}</small></span><Icon name="external" size={12} /></button>)}</div></> : !activeJob && <div className="empty-state ask-empty"><Icon name="search" size={25} /><h2>Start with a question.</h2><p>Ask where a behavior lives, how modules connect, or what a function does. The answer will point back to its source.</p>{lastRunId && !run && <button className="text-action" onClick={() => void openRun(lastRunId)}>Reopen your last question <Icon name="arrow" size={14} /></button>}</div>}</div>}
      </div>
      {(mode === 'ask' || mode === 'overview') && !showImport && <form className="question-composer" onSubmit={submitQuestion}><label className="sr-only" htmlFor="question">Ask about this repository</label><textarea id="question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask about this repository" rows={2} maxLength={4000} /><div className="composer-actions"><span><Icon name="branch" size={12} />{snapshot?.commit_sha.slice(0, 7) ?? 'Select a ready snapshot'}</span><button type="submit" className="solid icon-button" aria-label="Ask question" disabled={busy || Boolean(activeJob) || !snapshotId || !question.trim() || !capabilities.generation_enabled}><Icon name="send" size={15} /></button></div>{!capabilities.generation_enabled && <p className="composer-note">Groq is not configured. File exploration and lexical search are ready.</p>}</form>}
    </section>
    <SourceViewer source={source} loading={sourceLoading} error={sourceError} citation={selectedCitation} citations={citations} tabs={tabs} openFile={path => void openFile(path)} closeTab={path => { setTabs(items => items.filter(item => item !== path)); if (source?.path === path) setSource(null); }} expanded={expanded} toggleExpanded={() => setExpanded(!expanded)} next={() => source?.next_start_line && void openFile(source.path, null, snapshotId, source.next_start_line)} previous={() => source && void openFile(source.path, null, snapshotId, Math.max(1, source.start_line - 300))} />
  </div>;
}

function JobPanel({ job, cancel }: { job: Job; cancel: () => Promise<void> }) {
  const pending = !['succeeded', 'failed', 'cancelled'].includes(job.status);
  const [error, setError] = useState<string | null>(null);
  return <div className={`job-panel job-${job.status}`} role="status" aria-live="polite"><div className="job-title"><Icon name={pending ? 'spinner' : job.status === 'succeeded' ? 'check' : 'info'} className={pending ? 'spin' : ''} size={15} /><strong>{job.kind === 'import' ? 'Repository import' : job.kind === 'overview' ? 'Building overview' : 'Inspecting evidence'}</strong><span>{job.status.replaceAll('_', ' ')}</span></div><div className="job-detail"><span>{job.stage.replaceAll('_', ' ')}</span><span>attempt {job.attempt}</span></div>{job.checkpoint.files_processed !== undefined && <p>{String(job.checkpoint.files_processed)} of {String(job.checkpoint.total_files)} files processed</p>}{job.checkpoint.evidence_count !== undefined && <p>{String(job.checkpoint.evidence_count)} source excerpts inspected</p>}{job.status === 'queued' && <p>Waiting for the local worker. Progress is saved if you leave this page.</p>}{job.error && <p className="job-error">{job.error.message}</p>}{error && <p>{error}</p>}{pending && <button className="text-action" onClick={() => void cancel().catch(error => setError(errorText(error)))} disabled={job.cancel_requested}>{job.cancel_requested ? 'Cancellation requested' : 'Cancel job'}</button>}</div>;
}
