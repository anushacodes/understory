import { useEffect, useState } from 'react';
import { api, setToken } from './api';
import { Connect } from './components/Connect';
import { Landing } from './components/Landing';
import { Workspace } from './components/Workspace';
import type { Capabilities } from './types';

export function App() {
  const [screen, setScreen] = useState(location.hash.startsWith('#workspace') ? 'connect' : 'landing');
  const [dark, setDark] = useState(localStorage.getItem('understory-theme') === 'dark');
  const [initialQuery, setInitialQuery] = useState('');
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('understory-theme', dark ? 'dark' : 'light'); }, [dark]);
  async function connect(token: string) {
    setBusy(true); setError(null); setToken(token);
    try { setCapabilities(await api<Capabilities>('/settings')); setScreen('workspace'); location.hash = 'workspace'; }
    catch (error) { setToken(''); setError(error instanceof Error ? error.message : 'Connection failed.'); }
    finally { setBusy(false); }
  }
  function home() { setScreen('landing'); location.hash = ''; }
  function open(query = '') { setInitialQuery(query); setScreen(capabilities ? 'workspace' : 'connect'); location.hash = 'workspace'; }
  if (screen === 'landing') return <Landing dark={dark} toggleTheme={() => setDark(!dark)} open={open} />;
  if (screen === 'connect' || !capabilities) return <Connect connect={connect} home={home} busy={busy} error={error} />;
  return <Workspace dark={dark} toggleTheme={() => setDark(!dark)} home={home} capabilities={capabilities} initialQuery={initialQuery} />;
}
