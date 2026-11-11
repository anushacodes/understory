import type { CSSProperties } from 'react';

const paths: Record<string, string[]> = {
  arrow: ['M5 12h14', 'M13 6l6 6-6 6'],
  send: ['M12 19V5', 'M5.5 11.5L12 5l6.5 6.5'],
  search: ['M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13', 'M15.5 15.5L20 20'],
  file: ['M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'M14 3v5h5'],
  folder: ['M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z'],
  chevron: ['M9 6l6 6-6 6'], down: ['M7 10l5 5 5-5'],
  branch: ['M6 8.5v7', 'M18 10.5c0 4-6 3-11 6', 'M6 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5', 'M6 20.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5', 'M18 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5'],
  plus: ['M12 5v14', 'M5 12h14'],
  history: ['M3 11a9 9 0 1 1 2 7', 'M3 4v7h7', 'M12 7v5l3 2'],
  check: ['M5 12l4 4L19 6'], close: ['M6 6l12 12', 'M18 6L6 18'],
  external: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'],
  copy: ['M8 8h12v12H8Z', 'M16 8V4H4v12h4'],
  expand: ['M14 4h6v6', 'M10 20H4v-6', 'M20 4l-6 6', 'M4 20l6-6'],
  collapse: ['M10 4v6H4', 'M14 20v-6h6', 'M10 10L4 4', 'M14 14l6 6'],
  moon: ['M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z'],
  sun: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8', 'M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5'],
  book: ['M4 4h7a3 3 0 0 1 3 3v14a3 3 0 0 0-3-3H4Z', 'M14 7a3 3 0 0 1 3-3h4v14h-4a3 3 0 0 0-3 3'],
  download: ['M12 3v12', 'M7 10l5 5 5-5', 'M4 16v4h16v-4'],
  refresh: ['M20 11a8 8 0 0 0-14-5L3 9', 'M3 3v6h6', 'M4 13a8 8 0 0 0 14 5l3-3', 'M15 15h6v6'],
  info: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20', 'M12 11v6', 'M12 7h.01'],
  code: ['M8 6l-6 6 6 6', 'M16 6l6 6-6 6', 'M14 3l-4 18'],
  spinner: ['M12 3a9 9 0 1 0 9 9'],
};

export function Icon({ name, size = 16, className = '', style }: { name: string; size?: number; className?: string; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className} style={style}>{(paths[name] ?? paths.file).map((d, i) => <path key={i} d={d} />)}</svg>;
}

export function Wordmark({ onClick }: { onClick: () => void }) {
  return <button className="wordmark" onClick={onClick} aria-label="Understory home"><em>under</em>story</button>;
}
