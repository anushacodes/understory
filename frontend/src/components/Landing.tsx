import { useState } from 'react';
import { Icon, Wordmark } from './Icon';

export function Landing({ dark, toggleTheme, open }: { dark: boolean; toggleTheme: () => void; open: (query?: string) => void }) {
  const [query, setQuery] = useState('');
  return <div className={`landing ${dark ? 'landing-dark' : ''}`}>
    <div className="meadow" aria-hidden="true" /><div className="land-wash" aria-hidden="true" />
    {dark && <div className="fireflies" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <i key={i} style={{ left: `${14 + i * 17}%`, top: `${65 + (i % 3) * 7}%`, animationDelay: `${i * -4}s` }} />)}</div>}
    <header className="landing-header"><Wordmark onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} /><div className="header-actions"><button className="icon-button" onClick={toggleTheme} aria-label={dark ? 'Use light theme' : 'Use dark theme'}><Icon name={dark ? 'sun' : 'moon'} size={19} /></button><button className="pill solid" onClick={() => open()}>Open Understory <Icon name="arrow" /></button></div></header>
    <main className="landing-main">
      <h1><span>Understand the code</span><em>beneath the surface.</em></h1>
      <p className="landing-description">Search a repository by meaning, ask questions answered with cited code, and understand how the pieces fit together.</p>
      <form className="hero-search" onSubmit={event => { event.preventDefault(); open(query); }}><label className="sr-only" htmlFor="landing-query">Repository or question</label><input id="landing-query" value={query} onChange={event => setQuery(event.target.value)} placeholder="Paste a GitHub repo, or ask about one" /><button className="solid" type="submit">Search <Icon name="arrow" /></button></form>
      <p className="landing-proof">Public GitHub repos <span>·</span> Pinned to a commit <span>·</span> Every answer cited</p>
    </main>
    <footer className="landing-footer"><span>A little less searching. A little more understanding.</span><button onClick={() => open('understory/fixture')}>Explore the example <Icon name="arrow" size={14} /></button></footer>
  </div>;
}
