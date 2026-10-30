import React, {useEffect, useRef, useState} from 'react';

type ImportItem = {
  id: number; import_id: number; kind: string; filename: string; at: string;
  added: number; skipped: number; affected_rows: number;
  can_delete: boolean; deletion_reason: string;
};
type LegacyStatus = {legacy_rows: number; legacy_imports: number};
type Props = {
  items: ImportItem[]; busy: boolean; onChanged: () => Promise<void>;
  onMessage: (message: string) => void;
};
const RESET = 'REINITIALISER ANCIENS NPS';

export default function NpsImportManagement({items, busy, onChanged, onMessage}: Props) {
  const [status, setStatus] = useState<LegacyStatus | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    setStatus(null);
    window.orbite.call('legacyImportStatus').then((value: LegacyStatus) => {
      if (active) setStatus(value);
    }).catch((error: Error) => {
      if (active) onMessage('État des anciens NPS indisponible : ' + error.message);
    });
    return () => {active = false;};
  }, [items, onMessage]);

  const execute = async (method: string, params: Record<string, unknown>) => {
    if (inFlight.current || busy) return;
    inFlight.current = true;
    setPending(true);
    try {
      const result = await window.orbite.call(method, params);
      setConfirmation('');
      onMessage(`${result.deleted} lignes NPS supprimées. ` +
        (result.backup ? `Sauvegarde : ${result.backup}` : 'Aucune donnée à supprimer.'));
      await onChanged();
    } catch (error: unknown) {
      onMessage('Opération refusée ou interrompue : ' +
        (error instanceof Error ? error.message : String(error)));
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  };
  const remove = (item: ImportItem) => {
    if (busy || inFlight.current || !item.can_delete) return;
    if (!window.confirm(`Supprimer le lot NPS #${item.import_id} « ${item.filename} » du ${item.at} (${item.affected_rows} lignes) ? Une sauvegarde SQLite vérifiée sera créée. Les autres lots, le référentiel et Google seront conservés.`)) return;
    void execute('deleteImport', {
      id: item.import_id, confirmation: `SUPPRIMER IMPORT NPS ${item.import_id}`,
    });
  };
  const reset = () => {
    if (!status || confirmation !== RESET || busy || inFlight.current) return;
    if (!window.confirm(`Réinitialiser uniquement les ${status.legacy_rows} lignes NPS non traçables et ${status.legacy_imports} anciens imports ? Cette opération est globale, indépendamment des filtres. Les lots traçables, les centres et Google seront conservés. Une sauvegarde SQLite vérifiée sera créée.`)) return;
    void execute('resetLegacyNps', {confirmation});
  };

  return <>
    <section className="card">
      <h3>Historique des imports</h3>
      <p>Chaque lot possède un identifiant stable. Les doublons restent rattachés à leur import d’origine.</p>
      <div className="tablewrap"><table>
        <thead><tr>{['Lot', 'Date', 'Type', 'Fichier', 'Ajoutées', 'Ignorées', 'Lignes rattachées', 'Action'].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{items.map(item => <tr key={item.id}>
          <td>{item.import_id}</td><td>{item.at}</td><td>{item.kind}</td><td>{item.filename}</td>
          <td>{item.added}</td><td>{item.skipped}</td><td>{item.affected_rows ?? 'N/C'}</td>
          <td>{item.can_delete ? <button className="outline" disabled={busy || pending} onClick={() => remove(item)}>Supprimer</button> :
            <span>Protégé — {item.deletion_reason || 'Traçabilité non établie'}</span>}</td>
        </tr>)}</tbody>
      </table>{items.length === 0 && <p>Aucun import enregistré.</p>}</div>
    </section>
    <section className="card">
      <h3>Réinitialisation des anciens NPS non traçables</h3>
      <p>Cette action ne dépend pas des filtres géographiques ou des dates. Elle ne supprime ni les lots NPS traçables, ni le référentiel des centres, ni les données Google, ni la bibliothèque des enquêtes.</p>
      <p>{status ? `${status.legacy_rows} lignes NPS non traçables ; ${status.legacy_imports} anciens imports.` : 'Vérification du périmètre…'}</p>
      <label htmlFor="legacy-nps-confirmation">Pour confirmer, saisir exactement : <strong>{RESET}</strong></label>
      <input id="legacy-nps-confirmation" value={confirmation} autoComplete="off" disabled={busy || pending} onChange={event => setConfirmation(event.target.value)} />
      <button className="outline" disabled={busy || pending || !status || !(status.legacy_rows || status.legacy_imports) || confirmation !== RESET} onClick={reset}>Sauvegarder puis réinitialiser les anciens NPS</button>
    </section>
  </>;
}
