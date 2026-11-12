import { createRoot } from 'react-dom/client';
import { App } from './App';
import { RpcClient } from './api/client';
import { attachClient } from './store';
import './theme/tokens.css';
import './theme/app.css';
import './mechanics.css';
import { initDisplay } from './theme/prefs';
initDisplay();
createRoot(document.getElementById('root')!).render(<App />);
const token = location.hash.slice(1);
if (token) {
  void fetch('/auth', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
  attachClient(new RpcClient(token));
}
