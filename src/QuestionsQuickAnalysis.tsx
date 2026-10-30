import React, { useMemo, useState } from 'react';

export type QOccurrence = { occurrence_id:string; question_key:string; wording:string; respondents:number; responses:number };
export type QEpisode = { id:string; campaign:string; year:string; first_observation:string; last_observation:string; status:string; respondents:number; response_count:number; questions:QOccurrence[] };
export type QResult = { respondents_in_scope:number; question_present:number; valid_respondents:number; nonresponses:number; distribution:{label:string;count:number;percent:number|null}[] };
export default function QuestionsQuickAnalysis({episodes, loadResult}:{episodes:QEpisode[];loadResult:(episode:QEpisode,question:QOccurrence)=>Promise<QResult>}) {
 const [chosen,setChosen]=useState<string[]>([]),[results,setResults]=useState<Record<string,QResult>>({}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [search,setSearch]=useState('');
 const visible=useMemo(()=>episodes.filter(e=>(e.campaign+' '+e.year+' '+e.questions.map(q=>q.wording).join(' ')).toLocaleLowerCase('fr').includes(search.toLocaleLowerCase('fr'))),[episodes,search]);
 const grouped=useMemo(()=>{const g:Record<string,Record<string,QEpisode[]>>={};for(const e of visible){(g[e.campaign]??={})[e.year]??=[];g[e.campaign][e.year].push(e)}return g},[visible]);
 const toggle=(id:string)=>setChosen(old=>old.includes(id)?old.filter(x=>x!==id):[...old,id]);
 const run=async()=>{setBusy(true);setError('');try{const out:Record<string,QResult>={};for(const e of episodes)for(const q of e.questions)if(chosen.includes(q.occurrence_id))out[q.occurrence_id]=await loadResult(e,q);setResults(out)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 return <section aria-label="Analyse rapide des questions additionnelles" style={{color:'inherit'}}>
 <h2>Analyse rapide</h2><label>Rechercher campagne ou question <input value={search} onChange={e=>setSearch(e.target.value)}/></label>
 {Object.entries(grouped).map(([campaign,years])=><details key={campaign} open><summary><strong>{campaign}</strong></summary>{Object.entries(years).sort(([a],[b])=>b.localeCompare(a)).map(([year,items])=><details key={year} open><summary>{year}</summary>{items.map(ep=><details key={ep.id}><summary>Liste observée du {ep.first_observation} au {ep.last_observation} — {ep.questions.length} questions — {ep.respondents} répondants — {ep.status}</summary><button type="button" onClick={()=>{const ids=ep.questions.map(q=>q.occurrence_id);setChosen(old=>ids.every(id=>old.includes(id))?old.filter(id=>!ids.includes(id)):[...new Set([...old,...ids])])}}>Sélectionner / désélectionner la liste</button>{ep.questions.map(q=><label key={q.occurrence_id} style={{display:'block',margin:'8px 0'}}><input type="checkbox" checked={chosen.includes(q.occurrence_id)} onChange={()=>toggle(q.occurrence_id)}/>{q.wording}</label>)}</details>)}</details>)}</details>)}
 {!visible.length&&<p>Aucune liste historique disponible sur cette recherche.</p>}
 <p>{chosen.length} question(s) sélectionnée(s)</p><button type="button" disabled={!chosen.length||busy} onClick={run}>{busy?'Analyse en cours…':'Analyser la sélection'}</button>
 {error&&<p role="alert">{error}</p>}
 {episodes.flatMap(ep=>ep.questions.map(q=>({ep,q}))).filter(({q})=>chosen.includes(q.occurrence_id)&&results[q.occurrence_id]).map(({ep,q})=>{const r=results[q.occurrence_id];return <article key={q.occurrence_id} style={{border:'1px solid #64748b',padding:12,marginTop:12,borderRadius:8}}><h3>{q.wording}</h3><p>{ep.campaign} · {ep.first_observation} – {ep.last_observation}</p><p>Répondants exploitables : {r.valid_respondents} · Non-réponses : {r.nonresponses} · Dénominateur : répondants ayant répondu à cette question</p><ul>{r.distribution.map(v=><li key={v.label}>{v.label} : {v.count} ({v.percent===null?'N/C':v.percent+' %'})</li>)}</ul><small>Choix multiples : le total des pourcentages peut dépasser 100 %.</small></article>})}
 </section>
}
