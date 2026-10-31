import React,{useEffect,useState} from 'react';
import QuestionsQuickAnalysis,{QEpisode,QOccurrence,QResult} from './QuestionsQuickAnalysis';
import QuestionsStudio from './QuestionsStudio';
import './questions-audika.css';
type Filters={region:string;sector:string;campaign:string;start:string;end:string};
const call=(name:string,params:Record<string,unknown>={})=>window.orbite.call(name,params);
export default function QuestionsWorkspace({filters,onError}:{filters:Filters;onError:(message:string)=>void;Legacy?:React.ComponentType<any>}){
 const [tab,setTab]=useState<'quick'|'studio'>('quick'),[episodes,setEpisodes]=useState<QEpisode[]>([]),[review,setReview]=useState(0),[geo,setGeo]=useState<any>({regions:[],sectors:[],centers:[]});
 useEffect(()=>{let active=true;Promise.all([call('qaHistoricalCatalog'),call('qaFilterOptions')]).then(([history,options])=>{if(active){setEpisodes(history.episodes||[]);setReview((history.to_review||[]).length);setGeo(options)}}).catch((e:any)=>{if(active)onError(e.message)});return()=>{active=false}},[]);
 const loadResult=(e:QEpisode,q:QOccurrence,selection:Record<string,unknown>={}):Promise<QResult>=>call('qaQuickResult',{...filters,...selection,episode_id:e.id,occurrence_id:q.occurrence_id});
 return <div className="qa-root qa-refonte"><div className="qa-tabs" role="tablist"><button role="tab" aria-selected={tab==='quick'} className={tab==='quick'?'qa-active':''} onClick={()=>setTab('quick')}>Analyse rapide</button><button role="tab" aria-selected={tab==='studio'} className={tab==='studio'?'qa-active':''} onClick={()=>setTab('studio')}>Studio d'analyse</button></div>
 {tab==='quick'&&<QuestionsQuickAnalysis episodes={episodes} loadResult={loadResult} onError={onError} globalFilters={filters} reviewCount={review} geo={geo}/>}
 {tab==='studio'&&<QuestionsStudio episodes={episodes} filters={filters} geo={geo} onError={onError}/>}
 </div>;
}
