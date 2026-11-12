import { useState, type DragEvent } from 'react';
import { useText } from '../i18n';
import { act, rpc, view } from '../store';
import { DEMO } from '../demo/flag';
import { Icon } from './chrome';
import { REFERENCE_MAX_BYTES, REFERENCE_TYPES, referenceArgs } from '../api/reference';

/**
 * Attach a hand-picked reference image to the project (Sources tab).
 * It goes through the same core Op as the CLI and MCP, so the agent sees it
 * in list_sources. References are for measuring: they get no underlay button.
 */
export function ReferenceAttach() {
  const t = useText();
  const [file, setFile] = useState<File | null>(null), [note, setNote] = useState(''), [license, setLicense] = useState('unknown'), [over, setOver] = useState(false);
  const tooLarge = !!file && file.size > REFERENCE_MAX_BYTES;
  const ready = !!file && !tooLarge && note.trim().length > 0 && !DEMO;
  async function attach() {
    if (!file || !ready) return;
    const bytes = new Uint8Array(await file.arrayBuffer());
    await rpc('op.apply', { op: 'register_reference', args: referenceArgs(bytes, note, license) });
    setFile(null); setNote('');
    view({ sources: await rpc('sources.list') });
  }
  function drop(event: DragEvent) {
    event.preventDefault(); setOver(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }
  return <form className={`reference-attach${over ? ' over' : ''}`} aria-label={t('attachReference')}
    onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}
    onSubmit={e => { e.preventDefault(); void act(attach); }}>
    <p className="lbl">{t('attachReference')}</p>
    <p className="soft small-note">{DEMO ? t('demoNotAvailable') : t('referenceHint')}</p>
    <label className="fld"><span className="lbl">{t('referenceFile')}</span>
      <input className="field" type="file" accept={REFERENCE_TYPES.join(',')} disabled={DEMO} onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
    {file && <p className="mono soft small-note">{file.name} · {Math.ceil(file.size / 1024)} KiB{tooLarge ? ` — ${t('referenceTooLarge')}` : ''}</p>}
    <label className="fld"><span className="lbl">{t('referenceRights')}</span>
      <input className="field" required maxLength={2000} placeholder={t('referenceRightsPlaceholder')} value={note} disabled={DEMO} onChange={e => setNote(e.target.value)} /></label>
    <label className="fld"><span className="lbl">{t('referenceLicense')}</span>
      <input className="field mono" maxLength={200} value={license} disabled={DEMO} onChange={e => setLicense(e.target.value)} /></label>
    <div className="row-actions"><button className="pad small" type="submit" disabled={!ready}><Icon name="sources" />{t('attach')}</button></div>
  </form>;
}
