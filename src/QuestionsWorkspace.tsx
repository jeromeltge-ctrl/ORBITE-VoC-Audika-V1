import React,{useEffect,useState} from 'react';
import QuestionsQuickAnalysis,{QEpisode,QOccurrence,QResult} from './QuestionsQuickAnalysis';

type Filters={region:string;sector:string;campaign:string;start:string;end:string};
type Widget={id:string;title:string;episode_id:string;occurrence_id:string;kind:'table'|'bar'};
const call=(name:string,params:Record<string,unknown>={})=>window.orbite.call(name,params);
export default function QuestionsWorkspace({filters,onError,Legacy}:{filters:Filters;onError:(s:string)=>void;Legacy:React.ComponentType<{filters:Filters;onError:(s:string)=>void}>}){
 const [tab,setTab]=useState<'quick'|'studio'|'old'>('quick');
 const [episodes,setEpisodes]=useState<QEpisode[]>([]),[review,setReview]=useState(0),[widgets,setWidgets]=useState<Widget[]>([]);
 const [results,setResults]=useState<Record<string,QResult>>({});
 const [title,setTitle]=useState('Mon analyse'),[saved,setSaved]=useState<{id:string;title:string}[]>([]),[activeId,setActiveId]=useState('');
 const [notice,setNotice]=useState('');
 const refresh=async()=>{try{const result=await call('qaHistoricalCatalog',filters);setEpisodes(result.episodes||[]);setReview((result.to_review||[]).length)}catch(e:any){onError(e.message)}};
 const refreshSaved=async()=>{try{setSaved(await call('qaDashboardList'))}catch(e:any){onError(e.message)}};
 useEffect(()=>{void refresh()},[filters.region,filters.sector,filters.campaign,filters.start,filters.end]);
 useEffect(()=>{void refreshSaved()},[]);
 const loadResult=(ep:QEpisode,q:QOccurrence)=>call('qaQuickResult',{...filters,episode_id:ep.id,occurrence_id:q.occurrence_id});
 const addWidget=()=>{const ep=episodes.find(e=>e.questions.length);if(!ep)return;const q=ep.questions[0];setWidgets(w=>[...w,{id:crypto.randomUUID(),title:q.wording,episode_id:ep.id,occurrence_id:q.occurrence_id,kind:'table'}])};
 const getResult=async(w:Widget)=>{try{const result=await call('qaQuickResult',{...filters,episode_id:w.episode_id,occurrence_id:w.occurrence_id});setResults(prev=>({...prev,[w.id]:result}))}catch(e:any){onError(e.message)}};
 const save=async()=>{try{const response=await call('qaDashboardSave',{id:activeId||undefined,title,configuration:{widgets,filters}});setActiveId(response.id);setNotice('Tableau de bord enregistré dans la base locale');await refreshSaved()}catch(e:any){onError(e.message)}};
 const load=async(id:string)=>{try{const r=await call('qaDashboardLoad',{id});setWidgets(r.configuration.widgets||[]);setTitle(r.title);setActiveId(id);setResults({});setNotice('Tableau de bord chargé')}catch(e:any){onError(e.message)}};
 const exportWidget=async(w:Widget,ext:'xlsx'|'pdf')=>{try{const path=await window.orbite.pick(true,[{name:ext==='xlsx'?'Excel':'PDF',extensions:[ext]}]);if(!path)return;const result=await call('qaExport',{...filters,episode_id:w.episode_id,occurrence_id:w.occurrence_id,path});setNotice('Export créé : '+result.path)}catch(e:any){onError(e.message)}};
 return <div><div className="row" style={{gap:8,marginBottom:12}}>
 <button className={tab==='quick'?'primary':'outline'} onClick={()=>setTab('quick')}>Analyse rapide</button>
 <button className={tab==='studio'?'primary':'outline'} onClick={()=>setTab('studio')}>Studio d'analyse</button>
 <button className={tab==='old'?'primary':'outline'} onClick={()=>setTab('old')}>Bibliothèque existante</button></div>
 {tab==='old'&&<Legacy filters={filters} onError={onError}/>}
 {tab==='quick'&&<><p>Compositions observées dans les réponses NPS. {review} journée(s) ambiguë(s) à vérifier.</p><QuestionsQuickAnalysis episodes={episodes} loadResult={loadResult}/></>}
 {tab==='studio'&&<section className="card"><h3>Studio d'analyse</h3><p>Tableau de bord personnalisable. Les widgets utilisent le même catalogue que l'Analyse rapide.</p>
 <label>Nom <input value={title} onChange={e=>setTitle(e.target.value)}/></label>
 <button className="primary" onClick={addWidget} disabled={!episodes.some(e=>e.questions.length)}>Ajouter un widget</button>
 <button className="outline" onClick={save}>Enregistrer</button>
 <label>Mes tableaux de bord <select value="" onChange={e=>{if(e.target.value)void load(e.target.value)}}><option value="">Charger…</option>{saved.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
 {!widgets.length&&<p>Tableau de bord vide : ajoutez un widget.</p>}
 {widgets.map(w=><article className="card" key={w.id} style={{marginTop:12}}><label>Titre <input value={w.title} onChange={e=>setWidgets(ws=>ws.map(x=>x.id===w.id?{...x,title:e.target.value}:x))}/></label>
 <label>Question <select value={w.occurrence_id} onChange={e=>{const ep=episodes.find(x=>x.questions.some(q=>q.occurrence_id===e.target.value));if(ep)setWidgets(ws=>ws.map(x=>x.id===w.id?{...x,episode_id:ep.id,occurrence_id:e.target.value}:x))}}>{episodes.flatMap(ep=>ep.questions.map(q=><option key={q.occurrence_id} value={q.occurrence_id}>{ep.campaign} · {ep.first_observation} · {q.wording}</option>))}</select></label>
 <label>Vue <select value={w.kind} onChange={e=>setWidgets(ws=>ws.map(x=>x.id===w.id?{...x,kind:e.target.value as Widget['kind']}:x))}><option value="table">Tableau</option><option value="bar">Barres</option></select></label>
 <div className="row"><button className="outline" onClick={()=>void getResult(w)}>Calculer</button><button className="outline" onClick={()=>void exportWidget(w,'xlsx')}>Excel</button><button className="outline" onClick={()=>void exportWidget(w,'pdf')}>PDF</button><button className="outline" onClick={()=>setWidgets(ws=>[...ws,{...w,id:crypto.randomUUID()}])}>Dupliquer</button><button className="outline" onClick={()=>setWidgets(ws=>ws.filter(x=>x.id!==w.id))}>Supprimer</button></div>
 {results[w.id]&&<><p>{results[w.id].valid_respondents} répondants exploitables · {results[w.id].nonresponses} non-réponses</p>{w.kind==='table'?<ul>{results[w.id].distribution.map(x=><li key={x.label}>{x.label} : {x.count} ({x.percent??'N/C'} %)</li>)}</ul>:<div>{results[w.id].distribution.map(x=><div key={x.label} style={{marginBottom:6}}>{x.label} · {x.count}<div style={{background:'#dbeafe',height:12,width:'100%'}}><div style={{background:'#1474c8',height:12,width:Math.max(0,Math.min(100,x.percent||0))+'%'}}/></div></div>)}</div>}</>}
 </article>)}
 {notice&&<p role="status">{notice}</p>}
 </section>}
 </div>;
}
