import { createRoot } from 'react-dom/client';
import { App } from './App';
import { RpcClient } from './api/client';
import { attachClient, view } from './store';
import { DEMO } from './demo/flag';
import './theme/tokens.css';
import './theme/app.css';
import './mechanics.css';
import { initDisplay } from './theme/prefs';
initDisplay();
createRoot(document.getElementById('root')!).render(<App />);
if (DEMO) {
  // GitHub Pages demo: no server. The in-browser backend answers the same RPC methods.
  void import('./demo/backend').then(({ DemoClient, DEMO_START_LAYER }) => {
    view({ layer: DEMO_START_LAYER, zoom: matchMedia('(max-width: 760px)').matches ? 6 : innerHeight < 860 ? 8 : 10 });
    attachClient(new DemoClient());
  });
} else {
  const token = location.hash.slice(1);
  if (token) {
    void fetch('/auth', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    attachClient(new RpcClient(token));
  }
}
