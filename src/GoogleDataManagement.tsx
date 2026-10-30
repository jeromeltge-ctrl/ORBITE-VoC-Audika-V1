import React,{useEffect,useState} from 'react';
type Inventory={available:boolean;history:number;uberall:number;months:{month:string;rows:number}[];history_months?:{month:string;rows:number}[]};
export default function GoogleDataManagement({onError,onChanged}:{onError:(message:string)=>void;onChanged:()=>void}){
 const [data,setData]=useState<Inventory|null>(null),[busy,setBusy]=useState(false);
 const refresh=async()=>{try{setData(await window.orbite.call('googleDeleteInventory',{}))}catch(e:any){onError(e.message)}};
 useEffect(()=>{refresh()},[]);
 const remove=async(operation:string,phrase:string,period?:string)=>{
  const answer=window.prompt(`Opération irréversible dans la base active, avec sauvegarde automatique. Pour confirmer, saisir exactement : ${phrase}`);
  if(answer!==phrase)return;
  setBusy(true);
  try{const result=await window.orbite.call('googleDelete',{operation,period,confirmation:answer});onError(`${result.deleted} enregistrements Google supprimés. Sauvegarde : ${result.backup||'non nécessaire'}`);await refresh();onChanged()}
  catch(e:any){onError('Suppression Google refusée : '+e.message)}finally{setBusy(false)}
 };
 return <section className="card"><h3>Gérer les données E-réputation</h3><p>Les suppressions Google n'affectent ni les réponses NPS ni le référentiel réseau commun. Une sauvegarde SQLite est créée avant chaque suppression effective.</p>
 {!data?<p>Chargement…</p>:!data.available?<p>Aucune base Google importée.</p>:<><p><strong>{data.history}</strong> lignes historiques Google · <strong>{data.uberall}</strong> lignes Uberall</p>
 <div className="tablewrap"><table><thead><tr><th>Période Uberall</th><th>Lignes</th><th>Action</th></tr></thead><tbody>{data.months.map(m=><tr key={m.month}><td>{m.month}</td><td>{m.rows}</td><td><button type="button" className="outline" disabled={busy} onClick={()=>remove('uberall_month','SUPPRIMER UBERALL '+m.month,m.month)}>Supprimer ce mois</button></td></tr>)}</tbody></table></div>
 <div className="row"><button type="button" className="outline" disabled={busy||!data.history} onClick={()=>remove('history','SUPPRIMER HISTORIQUE GOOGLE')}>Vider l'historique Google</button><button type="button" className="outline" disabled={busy||!data.uberall} onClick={()=>remove('uberall','SUPPRIMER UBERALL')}>Vider toutes les données Uberall</button><button type="button" className="outline" disabled={busy||(!data.history&&!data.uberall)} onClick={()=>remove('all','REINITIALISER GOOGLE')}>Réinitialiser l'E-réputation</button></div>
 <p>La suppression individuelle d'un ancien import historique n'est pas proposée : le moteur historique ne conserve pas une provenance fiable par lot. Les mois Uberall sont identifiables.</p></>}
 </section>;
}
