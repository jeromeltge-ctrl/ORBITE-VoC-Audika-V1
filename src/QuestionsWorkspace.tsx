import React,{useEffect,useMemo,useState} from 'react';
import QuestionsQuickAnalysis,{QEpisode,QOccurrence,QResult} from './QuestionsQuickAnalysis';
import QuestionsStudio from './QuestionsStudio';
import './questions-audika.css';
type Filters={region:string;sector:string;campaign:string;start:string;end:string};
const call=(name:string,p:Record<string,unknown>={})=>window.orbite.call(name,p);
export default function QuestionsWorkspace({filters,onError,Legacy}:{filters:Filters;onError:(s:string)=>void;Legacy:React.ComponentType<{filters:Filters;onError:(s:string)=>void}>}){
 const [tab,setTab]=useState<'quick'|'studio'|'old'>('quick');
 const [episodes,setEpisodes]=useState<QEpisode[]>([]),[review,setReview]=useState(0);
 const [local,setLocal]=useState({campaign:'',year:'',start:'',end:''});
 const [notice,setNotice]=useState('');
 const effective={...filters,campaign:local.campaign||filters.campaign,start:local.start||filters.start,end:local.end||filters.end};
 useEffect(()=>{let mounted=true;(async()=>{try{const r=await call('qaHistoricalCatalog',effective);if(mounted){setEpisodes(r.episodes||[]);setReview((r.to_review||[]).length)}}catch(e:any){if(mounted)onError(e.message)}})();return()=>{mounted=false}},[filters.region,filters.sector,filters.campaign,filters.start,filters.end,local.campaign,local.start,local.end]);
 const shown=useMemo(()=>episodes.filter(e=>!local.year||e.year===local.year),[episodes,local.year]);
 const loadResult=(e:QEpisode,q:QOccurrence):Promise<QResult>=>call('qaQuickResult',{...effective,episode_id:e.id,occurrence_id:q.occurrence_id});
 return <div className="qa-root"><div className="qa-top"><div><div className="qa-eyebrow">AUDIKA · EXPÉRIENCE CLIENT</div><h2>Questions additionnelles</h2><p>Explorez les questionnaires historiques et construisez vos analyses.</p></div><button type="button" className="outline" onClick={()=>{setLocal({campaign:'',year:'',start:'',end:''});setNotice('Filtres locaux réinitialisés')}}>↺ Réinitialiser</button></div>
 <div className="qa-tabs" role="tablist"><button role="tab" aria-selected={tab==='quick'} className={tab==='quick'?'qa-active':''} onClick={()=>setTab('quick')}>Analyse rapide</button><button role="tab" aria-selected={tab==='studio'} className={tab==='studio'?'qa-active':''} onClick={()=>setTab('studio')}>Studio d'analyse</button><button role="tab" aria-selected={tab==='old'} className={tab==='old'?'qa-active':''} onClick={()=>setTab('old')}>Bibliothèque existante</button></div>
 {tab!=='old'&&<div className="qa-filterbar"><label>Campagne<select value={local.campaign} onChange={e=>setLocal(v=>({...v,campaign:e.target.value}))}><option value="">Toutes les campagnes</option>{[...new Set(episodes.map(e=>e.campaign))].sort().map(c=><option key={c}>{c}</option>)}</select></label><label>Année<select value={local.year} onChange={e=>setLocal(v=>({...v,year:e.target.value}))}><option value="">Toutes les années</option>{[...new Set(episodes.map(e=>e.year))].sort().reverse().map(y=><option key={y}>{y}</option>)}</select></label><label>Début<input type="date" value={local.start} onChange={e=>setLocal(v=>({...v,start:e.target.value}))}/></label><label>Fin<input type="date" min={local.start||undefined} value={local.end} onChange={e=>setLocal(v=>({...v,end:e.target.value}))}/></label><div className="qa-scope">Région : {filters.region||'Toutes'} · Secteur : {filters.sector||'Tous'}</div></div>}
 {tab==='old'&&<Legacy filters={filters} onError={onError}/>}
 {tab==='quick'&&<><div className="qa-review">{review} journée(s) avec compositions ambiguës à vérifier — aucune date de diffusion déduite.</div><QuestionsQuickAnalysis episodes={shown} loadResult={loadResult} onError={onError}/></>}
 {tab==='studio'&&<QuestionsStudio episodes={shown} filters={effective} onError={onError}/>}
 {notice&&<div className="qa-notice" role="status">{notice}</div>}</div>;
}
