import { useState } from 'react';
import { Icon, Wordmark } from './Icon';

export function Connect({ connect, home, busy, error }: { connect: (token: string) => void; home: () => void; busy: boolean; error: string | null }) {
  const [token, setToken] = useState('');
  return <div className="connect-page"><header><Wordmark onClick={home} /></header><main className="connect-form"><div className="connect-symbol"><Icon name="branch" size={26} /></div><h1>Your workspace,<br /><em>under the surface.</em></h1><p>Connect to your local repository workspace with the owner token from your server’s <code>.env</code> file.</p><form onSubmit={event => { event.preventDefault(); connect(token); }}><label htmlFor="owner-token">Owner token</label><input id="owner-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} placeholder="Enter your local owner token" autoFocus required /><button className="solid" disabled={busy || !token.trim()}>{busy ? <Icon name="spinner" className="spin" /> : <Icon name="arrow" />} {busy ? 'Connecting…' : 'Open workspace'}</button></form>{error && <p className="error-message" role="alert">{error}</p>}<p className="privacy-note"><Icon name="info" size={14} /> Your token stays in memory for this tab.</p></main></div>;
}
