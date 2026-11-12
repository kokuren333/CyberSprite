import { useText, type TextKey } from '../i18n';
import { collectTerms, termsTone } from '../platforms';
import { Icon, type IconName } from './chrome';
const tone: Record<ReturnType<typeof termsTone>, { key: TextKey; icon: IconName }> = {
  ok: { key: 'termsOk', icon: 'validate-ok' },
  restricted: { key: 'termsRestricted', icon: 'warning' },
  nc: { key: 'termsNonCommercial', icon: 'error' },
  review: { key: 'termsReview', icon: 'warning' },
};
/** Model licence badges (SPEC §12.7, H-21): plain text, icon plus words, never colour alone.
 * The server's English badge and message stay visible as the authoritative wording. */
export function TermsBadges({ value }: { value: unknown }) {
  const t = useText(), terms = collectTerms(value);
  if (!terms.length) return null;
  return <section className="terms" aria-labelledby="terms-title">
    <h3 className="terms-title lbl" id="terms-title">{t('modelTerms')}</h3>
    <ul className="terms-list">{terms.map(entry => {
      const kind = termsTone(entry.badge), { key, icon } = tone[kind];
      return <li key={`${entry.id}:${entry.badge}`} className={`terms-badge ${kind}`}>
        <Icon name={icon} /><span className="terms-body"><span className="terms-head"><b>{t(key)}</b><code className="mono">{entry.id}</code></span>
          <span className="soft mono">{entry.license} · commercial_use={entry.commercial_use} · {entry.badge}</span></span></li>;
    })}</ul>
    <p className="soft terms-note">{t('termsNote')}</p>
  </section>;
}
