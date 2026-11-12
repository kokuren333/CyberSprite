import { useText } from '../i18n';
import { REPO_URL } from '../demo/flag';
import { act, refresh, rpc, view } from '../store';
import { Icon, Silk } from './chrome';
/** Always-visible strip in the demo build (npm run build:demo): says this page is a
 * browser-only demo and that the real tool is cloned and used with an AI agent. */
export function DemoNotice() {
  const t = useText();
  return <aside className="demo-notice" role="note" aria-label={t('demoBadge')}>
    <span className="demo-chip"><Silk text="DEMO" /><span className="demo-chip-name">{t('demoBadge')}</span></span>
    <p className="demo-text"><span className="demo-long">{t('demoNotice')}</span><span className="demo-short">{t('demoNoticeShort')}</span>
      {REPO_URL && <> <a className="demo-link" href={REPO_URL} target="_blank" rel="noopener noreferrer">{t('demoRepo')}</a></>}</p>
    <span className="demo-actions">
      <button className="pad small" onClick={() => void act(() => rpc('demo.agent_commit'))}><Icon name="agent" /><span>{t('demoAgent')}</span></button>
      <button className="pad small" onClick={() => void act(async () => { await rpc('demo.reset'); view({ change: null, delta: null, diff: null, status: '' }); await refresh(); })}><Icon name="undo" /><span>{t('demoReset')}</span></button>
    </span>
  </aside>;
}
