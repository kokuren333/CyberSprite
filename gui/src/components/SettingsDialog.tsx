import { useEffect, useRef } from 'react';
import { useLanguage, useText } from '../i18n';
import { act, rpc } from '../store';
import { useDisplay } from '../theme/prefs';
import { Icon, Notch } from './chrome';
/** Display settings (SPEC §14.2 dialog list, §14.3.3 high contrast / reduced motion, §14.7 language). */
export function SettingsDialog({ close }: { close: () => void }) {
  const t = useText(), language = useLanguage(), d = useDisplay(), dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close(); }, []);
  const seg = <T extends string | number>(name: string, value: T, options: [T, string][], set: (v: T) => void) =>
    <span className="seg" role="radiogroup" aria-labelledby={`set-${name}`}>{options.map(([v, label]) =>
      <button key={String(v)} role="radio" aria-checked={value === v} className={`pad ${value === v ? 'on' : ''}`} onClick={() => set(v)}>{label}</button>)}</span>;
  return <dialog ref={dialog} className="settings-dialog panel" onCancel={close} aria-labelledby="set-title"><Notch />
    <header className="ph"><Icon name="settings" /><h2 className="ph-title" id="set-title"><span className="ph-name">{t('settings')}</span></h2></header>
    <div className="dlg-body settings-grid">
      <span className="lbl" id="set-language">{t('language')}</span>
      {seg('language', language.language, [['ja', '日本語'], ['en', 'English']], v => { language.setLanguage(v); void act(() => rpc('prefs.set', { language: v })); })}
      <span className="lbl" id="set-contrast">{t('contrast')}</span>
      {seg('contrast', d.contrast, [['auto', t('followOs')], ['normal', t('contrastNormal')], ['high', t('contrastHigh')]], v => d.set({ contrast: v }))}
      <span className="lbl" id="set-text">{t('textSize')}</span>
      {seg('text', d.text, [[12, '12 px'], [13, '13 px'], [14, '14 px']], v => d.set({ text: v }))}
      <span className="lbl" id="set-scale">{t('uiScale')}</span>
      {seg('scale', d.scale, [[1, '1×'], [2, '2×'], [3, '3×']], v => d.set({ scale: v }))}
      <span className="lbl" id="set-motion">{t('motion')}</span>
      {seg('motion', d.motion, [['auto', t('followOs')], ['reduce', t('motionReduce')]], v => d.set({ motion: v }))}
      <p className="soft settings-note">{t('settingsNote')}</p>
      <p className="soft settings-note mono">{t('about')}</p>
    </div>
    <footer className="dlg-actions"><span className="grow" /><button className="pad primary" onClick={close}>{t('done')}</button></footer>
  </dialog>;
}
