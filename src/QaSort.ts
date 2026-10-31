export type SortMode='percent-desc'|'percent-asc'|'count-desc'|'count-asc'|'alpha-asc'|'alpha-desc'|'original';
export type Distribution={label:string;count:number;percent:number|null};
export function sortDistribution(rows:Distribution[],mode:SortMode):Distribution[]{
 const out=[...rows];if(mode==='original')return out;
 const compare=(a:Distribution,b:Distribution)=>{
  const fallback=a.label.localeCompare(b.label,'fr');
  switch(mode){case 'percent-desc':return (b.percent??-Infinity)-(a.percent??-Infinity)||fallback;
   case 'percent-asc':return (a.percent??Infinity)-(b.percent??Infinity)||fallback;
   case 'count-desc':return b.count-a.count||fallback;
   case 'count-asc':return a.count-b.count||fallback;
   case 'alpha-asc':return fallback;
   case 'alpha-desc':return -fallback;
   default:return 0;}
 };
 return out.sort(compare);
}
