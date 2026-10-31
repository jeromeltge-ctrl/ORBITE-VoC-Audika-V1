import React,{useMemo,useState} from 'react';
export type Choice={value:string;label:string};
export default function QaMultiSelect({label,options,value,onChange,placeholder='Tous',disabled=false}:{label:string;options:Choice[];value:string[];onChange:(value:string[])=>void;placeholder?:string;disabled?:boolean}){
 const [open,setOpen]=useState(false),[search,setSearch]=useState('');
 const filtered=useMemo(()=>options.filter(x=>x.label.toLocaleLowerCase('fr').includes(search.toLocaleLowerCase('fr'))),[options,search]);
 const toggle=(v:string)=>onChange(value.includes(v)?value.filter(x=>x!==v):[...value,v]);
 return <div className="qa-ms"><label>{label}</label><button type="button" className="qa-ms-trigger" disabled={disabled} aria-expanded={open} onClick={()=>setOpen(o=>!o)}>{value.length?`${value.length} sélection(s)`:`${placeholder} ▾`}</button>{open&&<div className="qa-ms-pop"><input aria-label={`Rechercher ${label}`} placeholder="Rechercher…" value={search} onChange={e=>setSearch(e.target.value)}/><div className="qa-ms-actions"><button type="button" onClick={()=>onChange(options.map(o=>o.value))}>Tout sélectionner</button><button type="button" onClick={()=>onChange([])}>Toutes (aucune restriction)</button></div><div className="qa-ms-list">{filtered.map(o=><label key={o.value}><input type="checkbox" checked={value.includes(o.value)} onChange={()=>toggle(o.value)}/>{o.label}</label>)}</div><button type="button" className="qa-ms-done" onClick={()=>setOpen(false)}>Appliquer</button></div>}</div>;
}
