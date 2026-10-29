from datetime import date
from openpyxl import Workbook
from openpyxl.chart import BarChart,Reference
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
from engine import Analysis,months,yearback
DARK='173852';TEAL='087E79';LIGHT='EAF4F7'
def make(con,path,start,end,region='Toutes',sector='Tous'):
 a=Analysis(con);period=months(start,end);codes=a.codes(region,sector)
 if not codes:raise ValueError('Aucun centre pour ce périmètre')
 st=a.stats(period,codes);w=Workbook();v=w.active;v.title='01 VUE ENSEMBLE';s=w.create_sheet('02 MON SECTEUR');c=w.create_sheet('03 MES CENTRES');d=w.create_sheet('04 DONNÉES DÉTAILLÉES')
 def title(sh,text):
  sh.merge_cells('A1:H2');cell=sh['A1'];cell.value=text;cell.fill=PatternFill('solid',fgColor=DARK);cell.font=Font(size=20,bold=True,color='FFFFFF');cell.alignment=Alignment(vertical='center');sh.row_dimensions[1].height=30
 def kpi(sh,labels,values):
  for j,(label,val) in enumerate(zip(labels,values),1):
   h=sh.cell(5,j,label);h.fill=PatternFill('solid',fgColor=DARK);h.font=Font(color='FFFFFF',bold=True)
   x=sh.cell(6,j,val);x.fill=PatternFill('solid',fgColor=LIGHT);x.font=Font(color=TEAL,bold=True,size=18)
  sh.row_dimensions[6].height=34
 title(v,'AUDIKA  |  VUE D’ENSEMBLE');v['A3']=f'Région : {region}   |   Début : {start}   |   Fin : {end}'
 kpi(v,['AVIS N','AVIS N-1','ÉVOLUTION','NOTE GOOGLE /5','AVIS / CENTRE / MOIS'],[st['n'],st['n1'],st['evolution'],st['note'],st['moyenne']]);v['C6'].number_format='0.0%';v['D6'].number_format='0.00';v['E6'].number_format='0.00'
 v['A8']='Centres comparables';v['B8']=st['comparable'];v['D8']='Centres sans avis au total';v['E8']=st['zero_total'];v['F8']='Sans nouvel avis sur la période';v['G8']=st['zero_periode']
 v.merge_cells('A10:H11');v['A10']='Centres comparables : centres du référentiel ayant des données permettant de calculer les nouveaux avis de chaque mois en N et sur les mois équivalents N-1. Seuls ces mêmes centres sont utilisés pour les deux volumes comparés.';v['A10'].alignment=Alignment(wrap_text=True,vertical='center');v['A10'].fill=PatternFill('solid',fgColor=LIGHT);v.row_dimensions[10].height=35
 v.append([])
 for j,h in enumerate(['Région','Avis N','Avis N-1','Écart','Évolution','Centres','Avis / centre / mois'],1):v.cell(14,j,h)
 regs=sorted({a.centers[code][2] for code in codes})
 for reg in regs:
  group=[code for code in codes if a.centers[code][2]==reg];z=a.stats(period,group);v.append([reg,z['n'],z['n1'],z['n']-z['n1'],z['evolution'],len(group),z['moyenne']]);v.cell(v.max_row,5).number_format='0.0%'
 v.append(['TOTAL',st['n'],st['n1'],st['n']-st['n1'],st['evolution'],len(codes),st['moyenne']]);v.cell(v.max_row,5).number_format='0.0%'
 if regs:
  ch=BarChart();ch.title='Comparaison régionale N / N-1';ch.add_data(Reference(v,min_col=2,max_col=3,min_row=14,max_row=14+len(regs)),titles_from_data=True);ch.set_categories(Reference(v,min_col=1,min_row=15,max_row=14+len(regs)));ch.width=20;ch.height=10;v.add_chart(ch,'I14')
 title(s,'AUDIKA  |  MON SECTEUR');s['A3']=f'Région : {region}   Secteur : {sector}   Période : {start} — {end}'
 kpi(s,['AVIS N','ÉVOLUTION N/N-1','NOTE GOOGLE /5','AVIS / CENTRE / MOIS'],[st['n'],st['evolution'],st['note'],st['moyenne']]);s['B6'].number_format='0.0%'
 for j,h in enumerate(['Mois','Avis N comparables','Avis N-1 comparables','Écart','Évolution','Centres cumul = 0'],1):s.cell(10,j,h)
 for m in period:
  eligible=[code for code in codes if a.comparable(code,[m]) is not None];n=sum(a.delta(code,m) for code in eligible);p=sum(a.delta(code,yearback(m)) for code in eligible)
  zeros=sum((code,m) in a.snap and a.snap[code,m][0]==0 for code in codes)
  s.append([date.fromisoformat(m+'-01'),n,p,n-p,(n/p-1 if p else None),zeros]);s.cell(s.max_row,1).number_format='mmm yyyy';s.cell(s.max_row,5).number_format='0.0%'
 if period:
  ch=BarChart();ch.title='Avis mensuels N / N-1';ch.add_data(Reference(s,min_col=2,max_col=3,min_row=10,max_row=10+len(period)),titles_from_data=True);ch.set_categories(Reference(s,min_col=1,min_row=11,max_row=10+len(period)));ch.width=21;ch.height=10;s.add_chart(ch,'H10')
 title(c,'AUDIKA  |  MES CENTRES');c['A3']=f'Région : {region}   Secteur : {sector}   Période : {start} — {end}'
 kpi(c,['CENTRES','SANS AVIS TOTAL','SANS AVIS PÉRIODE','CENTRES COMPARABLES'],[len(codes),st['zero_total'],st['zero_periode'],st['comparable']])
 for j,h in enumerate(['Code','Centre','Région','Secteur','Avis N','Avis N-1','Écart','Évolution','Note cumulée','Statut'],1):c.cell(10,j,h)
 for code in codes:
  _,name,reg,sec,_=a.centers[code];p=a.comparable(code,period);latest=a.snap.get((code,end));values=[a.delta(code,m) for m in period];status='Données manquantes' if any(x is None for x in values) else 'Sans nouvel avis' if sum(values)==0 else 'Avis reçus'
  n,old=p if p else (None,None);c.append([code,name,reg,sec,n,old,n-old if p else None,n/old-1 if p and old else None,latest[1] if latest else None,status]);c.cell(c.max_row,8).number_format='0.0%'
 d.append(['Année','Mois','Code centre','Secteur','Région','Nouveaux avis mois','Nb avis cumul','Note Google mois','Note cumul'])
 for code,m in sorted(a.snap,key=lambda x:(x[1],x[0])):
  if code not in a.centers:continue
  val=a.snap[code,m];monthly=a.u.get((code,m));d.append([int(m[:4]),date.fromisoformat(m+'-01'),code,a.centers[code][3],a.centers[code][2],a.delta(code,m),val[0],monthly[1] if monthly else None,val[1]]);d.cell(d.max_row,2).number_format='mmm yyyy'
 for sh in w:
  sh.sheet_view.showGridLines=False;sh.freeze_panes='A11' if sh in (s,c) else 'A2'
  if sh in (c,d):sh.auto_filter.ref=(f'A10:J{sh.max_row}' if sh==c else sh.dimensions)
  for col in sh.columns:
   letter=get_column_letter(col[0].column);sh.column_dimensions[letter].width=min(38,max(15,max(len(str(x.value or '')) for x in list(col)[:90])+2))
 w.save(path)
 return st
