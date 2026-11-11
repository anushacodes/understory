import { useState } from 'react';
import type { FileEntry } from '../types';
import { Icon } from './Icon';

type Node = { name: string; path: string; children: Map<string, Node>; file?: FileEntry };
function build(files: FileEntry[]) {
  const root: Node = { name: '', path: '', children: new Map() };
  for (const file of files) {
    let node = root;
    const parts = file.path.split('/');
    parts.forEach((name, i) => {
      if (!node.children.has(name)) node.children.set(name, { name, path: parts.slice(0, i + 1).join('/'), children: new Map() });
      node = node.children.get(name)!;
    });
    node.file = file;
  }
  return root;
}

function Branch({ node, depth, selected, openFile, filter }: { node: Node; depth: number; selected: string; openFile: (path: string) => void; filter: string }) {
  const [expanded, setExpanded] = useState(depth < 2);
  if (node.file) return <button className={`tree-row ${selected === node.path ? 'selected' : ''} ${node.file.state !== 'included' ? 'excluded' : ''}`} style={{ paddingLeft: 12 + depth * 16 }} onClick={() => openFile(node.path)} title={node.file.reason ? `${node.path} — ${node.file.reason.replaceAll('_', ' ')}` : node.path} aria-current={selected === node.path ? 'true' : undefined}><Icon name="file" size={14} /><span>{node.name}</span>{node.file.state !== 'included' ? <span className="file-state">skipped</span> : node.file.kind === 'test' ? <span className="status-dot test-dot" /> : null}</button>;
  const children = [...node.children.values()].sort((a, b) => Number(Boolean(a.file)) - Number(Boolean(b.file)) || a.name.localeCompare(b.name));
  return <div><button className="tree-row directory" style={{ paddingLeft: 10 + depth * 16 }} onClick={() => setExpanded(!expanded)} aria-expanded={expanded || Boolean(filter)}><Icon name={expanded || filter ? 'down' : 'chevron'} size={12} /><Icon name="folder" size={15} /><span>{node.name}</span></button>{(expanded || filter) && children.map(child => <Branch key={child.path} node={child} depth={depth + 1} selected={selected} openFile={openFile} filter={filter} />)}</div>;
}

export function FileTree({ files, selected, openFile, filter }: { files: FileEntry[]; selected: string; openFile: (path: string) => void; filter: string }) {
  const root = build(files.filter(file => file.path.toLowerCase().includes(filter.toLowerCase())));
  const nodes = [...root.children.values()].sort((a, b) => Number(Boolean(a.file)) - Number(Boolean(b.file)) || a.name.localeCompare(b.name));
  return <nav className="file-tree pane-scroll" aria-label="Repository files">{nodes.length ? nodes.map(node => <Branch key={node.path} node={node} depth={0} selected={selected} openFile={openFile} filter={filter} />) : <p className="small-empty">{filter ? 'No matching files.' : 'Files appear after a completed import.'}</p>}</nav>;
}
