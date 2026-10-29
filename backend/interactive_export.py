"""Preserve the original Consolide2 workbook, charts, dropdowns and styles.
Rebuild its hidden source and helper calculations from V10's consolidated data.
"""
from datetime import date
from pathlib import Path
import re
from openpyxl import load_workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.datavalidation import DataValidation
from engine import Analysis,months

SHEETS=['01 VUE ENSEMBLE','02 MON SECTEUR','03 MES CENTRES','04 DONNÉES DÉTAILLÉES']
def build(con,template,out,start,end,region='Toutes',sector='Tous'):
 if not Path(template).is_file():raise FileNotFoundError('Modèle Consolide2 introuvable : '+str(template))
 a=Analysis(con);period=months(start,end)
 # Prefer adjacent-month cumulative differences when the source delta is missing.
 # Never turn a missing previous snapshot into zero reviews.
 def safe_delta(code, month):
  value=a.delta(code,month)
  if value is not None:return value
  year,mon=map(int,month.split('-'));prev=f'{year-1}-12' if mon==1 else f'{year}-{mon-1:02d}'
  current=a.snap.get((code,month));previous=a.snap.get((code,prev))
  if current is None or previous is None or current[0] is None or previous[0] is None:return None
  diff=current[0]-previous[0]
  return diff if diff>=0 else None
 if not a.centers or not a.snap:raise ValueError('Importer le référentiel et l’historique avant export')
 w=load_workbook(template)
 if any(x not in w for x in SHEETS+['_BASE','_LISTES']):raise ValueError('Le modèle n’est pas le Consolide2 attendu')
 # Explicitly preserve charts, original merged cells, validations, styling.
 v,s,c,d=[w[x] for x in SHEETS]
 base=w['_BASE'];base.delete_rows(2,base.max_row)
 base.append([]) if False else None
 for code,m in sorted(a.snap,key=lambda x:(x[0],x[1])):
  if code not in a.centers:continue
  _,name,reg,sec,_=a.centers[code];total,note=a.snap[code,m];delta=safe_delta(code,m)
  # A partial Uberall month remains available in detail but is NOT comparable.
  valid=1 if delta is not None else 0
  base.append([code,reg,sec,date(int(m[:4]),int(m[5:]),1),total,note,delta,valid])
  base.cell(base.max_row,4).number_format='mmm yyyy'
 last=base.max_row
 # Update detailed sheet, preserving the nine requested columns.
 if d.max_row>1:d.delete_rows(2,d.max_row-1)
 for row in base.iter_rows(min_row=2,values_only=True):
  code,reg,sec,dt,total,note,delta,valid=row
  month=a.u.get((code,dt.strftime('%Y-%m')))
  monthly=month[1] if month and isinstance(month[1],(int,float)) and 0<=month[1]<=5 else None
  # If Uberall lacks a monthly rating, derive a weighted monthly rating only
  # from two adjacent cumulative snapshots with a positive review delta.
  if monthly is None and isinstance(delta,(int,float)) and delta>0 and isinstance(note,(int,float)):
   ym=dt.year*12+dt.month-2
   previous=f'{ym//12:04d}-{ym%12+1:02d}'
   prev=a.snap.get((code,previous))
   if prev and isinstance(prev[0],(int,float)) and isinstance(prev[1],(int,float)) and total-prev[0]==delta:
    estimate=(total*note-prev[0]*prev[1])/delta
    if -0.001<=estimate<=5.001:monthly=round(max(0,min(5,estimate)),2)
  d.append([dt.year,dt,code,sec,reg,delta,total,monthly if monthly is not None else 'N/A',note if note is not None else 'N/A'])
  d.cell(d.max_row,2).number_format='mmm yyyy'
 d.auto_filter.ref=f'A1:I{d.max_row}'
 # Dynamic lists, rebuilt from the CURRENT reference (not the obsolete template).
 lists=w['_LISTES'];lists.delete_rows(1,lists.max_row)
 regs=sorted({x[2] for x in a.centers.values()});pairs=sorted({(x[2],x[3]) for x in a.centers.values()})
 lists['A1']='Regions';lists['A2']='Toutes';lists['B1']='Mois disponibles'
 for i,r in enumerate(regs,3):lists.cell(i,1,r)
 available=sorted({m for code,m in a.snap})
 for i,m in enumerate(available,2):lists.cell(i,2,date(int(m[:4]),int(m[5:]),1)).number_format='mmm yyyy'
 lists['C1']='Tous'
 for name in list(w.defined_names):
  if name.startswith('Secteurs') or name in ('RegionsDisponibles','DatesDisponibles'):del w.defined_names[name]
 w.defined_names.add(DefinedName('RegionsDisponibles',attr_text=f"'_LISTES'!$A$2:$A${len(regs)+2}"))
 w.defined_names.add(DefinedName('DatesDisponibles',attr_text=f"'_LISTES'!$B$2:$B${len(available)+1}"))
 all_sectors=sorted({sec for _,sec in pairs})
 for j,sec in enumerate(all_sectors,2):lists.cell(j,3,sec)
 w.defined_names.add(DefinedName('SecteursTous',attr_text=f"'_LISTES'!$C$1:$C${len(all_sectors)+1}"))
 from openpyxl.utils import get_column_letter
 for i,r in enumerate(regs,1):
  col=4+i;letter=get_column_letter(col);lists.cell(1,col,'Tous');secs=[sec for rr,sec in pairs if rr==r]
  for j,sec in enumerate(secs,2):lists.cell(j,col,sec)
  w.defined_names.add(DefinedName('Secteurs'+str(i),attr_text=f"'_LISTES'!${letter}$1:${letter}${len(secs)+1}"))
 # Excel references in the Consolide2 formulas must point at the newly sized source.
 old_end=20647
 for sh in [v,s,c]:
  for row in sh:
   for cell in row:
    if cell.data_type=='f' and isinstance(cell.value,str):
     cell.value=cell.value.replace('$20647',f'${last}')
  sh['J6']=date(int(start[:4]),int(start[5:]),1)
  sh['M6']=date(int(end[:4]),int(end[5:]),1)
  sh['J6'].number_format=sh['M6'].number_format='mmm yyyy'
  sh['B6']=region if region in regs or region=='Toutes' else 'Toutes'
  if sh!=v:sh['F6']=sector if sector=='Tous' or (region=='Toutes' and sector in [x[1] for x in pairs]) or (region,sector) in pairs else 'Tous'
 # Rewrite helper rows to match the current reference and avoid stale hard-coded centre counts.
 # Original helper columns S:AF are retained, including the exact same comparison semantics.
 N=len(a.centers);startrow=21;endrow=20+N
 for sh in [v,s,c]:
  is_sector=sh!=v
  for i,(code,name,reg,sec,addr) in enumerate(a.centers.values(),startrow):
   sh[f'S{i}']=code;sh[f'T{i}']=reg;sh[f'U{i}']=sec
   scope=f'AND(OR($B$6="Toutes",$B$6=T{i})'+(f',OR($F$6="Tous",$F$6=U{i})' if is_sector else '')+')'
   B="'_BASE'!";bc=f'{B}$A$2:$A${last}';bd=f'{B}$D$2:$D${last}';bf=f'{B}$G$2:$G${last}';bv=f'{B}$H$2:$H${last}';bt=f'{B}$E$2:$E${last}';br=f'{B}$F$2:$F${last}'
   sh[f'V{i}']=f'=IF({scope},SUMIFS({bf},{bc},S{i},{bd},">="&$J$6,{bd},"<="&$M$6),"")'
   sh[f'W{i}']=f'=IF({scope},SUMIFS({bf},{bc},S{i},{bd},">="&EDATE($J$6,-12),{bd},"<="&EDATE($M$6,-12)),"")'
   sh[f'X{i}']=f'=IF({scope},COUNTIFS({bc},S{i},{bd},">="&$J$6,{bd},"<="&$M$6,{bv},1),"")'
   sh[f'Y{i}']=f'=IF({scope},COUNTIFS({bc},S{i},{bd},">="&EDATE($J$6,-12),{bd},"<="&EDATE($M$6,-12),{bv},1),"")'
   sh[f'Z{i}']='=12*(YEAR($M$6)-YEAR($J$6))+MONTH($M$6)-MONTH($J$6)+1'
   sh[f'AA{i}']=f'=IF(AND(ISNUMBER(X{i}),ISNUMBER(Y{i}),X{i}=Z{i},Y{i}=Z{i}),1,0)'
   sh[f'AB{i}']=f'=IF(OR(NOT({scope}),COUNTIFS({bc},S{i},{bd},$M$6)=0),"",SUMIFS({bt},{bc},S{i},{bd},$M$6))'
   sh[f'AC{i}']=f'=IF(OR(AB{i}="",AB{i}=0,COUNTIFS({bc},S{i},{bd},$M$6,{br},">0")=0),"",SUMIFS({br},{bc},S{i},{bd},$M$6))'
   sh[f'AD{i}']=f'=IF(OR(AC{i}="",AB{i}=""),0,AB{i})'
   sh[f'AE{i}']=f'=IF(OR(V{i}="",X{i}<>Z{i}),"",IF(V{i}=0,1,0))'
   sh[f'AF{i}']=f'=IF(AB{i}="","",IF(AB{i}=0,1,0))'
  for row in range(endrow+1,max(sh.max_row,671)):
   for col in range(19,33):sh.cell(row,col).value=None
  for row in sh:
   for cell in row:
    if cell.data_type=='f' and isinstance(cell.value,str):cell.value=re.sub(r'(?<=[A-Z]\$)670(?!\d)',str(endrow),cell.value)
 # Rebuild the visible centre list in the CURRENT reference order.
 # The old template had static references to obsolete centre rows.
 for i,(code,name,reg,sec,addr) in enumerate(a.centers.values(),22):
  helper=i-1
  scope=f'AND(OR($B$6="Toutes",$B$6="{reg}"),OR($F$6="Tous",$F$6="{sec}"))'
  for col,value in [(2,code),(3,name),(4,reg),(5,sec)]:
   c.cell(i,col,f'=IF({scope},"{value}","")')
  c.cell(i,6,f'=IF(B{i}="","",V{helper})')
  c.cell(i,7,f'=IF(B{i}="","",W{helper})')
  c.cell(i,8,f'=IF(OR(B{i}="",X{helper}=0,Y{helper}=0),"",F{i}-G{i})')
  c.cell(i,9,f'=IF(B{i}="","",IFERROR(H{i}/G{i},"N/C"))')
  c.cell(i,9).number_format='0.0%'
  c.cell(i,10,f'=IF(B{i}="","",IF(AC{helper}="","N/A",AC{helper}))')
  c.cell(i,11,f'=IF(B{i}="","",IF(X{helper}<>Z{helper},"Données manquantes",IF(F{i}=0,"Sans nouvel avis","Avis reçus")))')
  c.cell(i,12,f'=IF(B{i}="","",IF(K{i}="Sans nouvel avis","Relancer collecte","OK"))')
 for row in range(22+N,max(c.max_row,672)):
  for col in range(2,13):c.cell(row,col).value=None
 c.auto_filter.ref=f'B21:L{21+N}'
 # Main KPI correction: constant-cohort Avis N, Avis N-1, evolution and weighted note.
 v['B11']='AVIS N';v['F11']='AVIS N-1';v['J11']='ÉVOLUTION N/N-1';v['N11']='NOTE GOOGLE GLOBALE'
 v['B12']=f'=SUM(V21:V{endrow})'
 v['F12']=f'=SUM(W21:W{endrow})'
 v['J12']='=IFERROR((B12-F12)/F12,"N/C")';v['J12'].number_format='0.0%'
 v['N12']=f'=IFERROR(SUMPRODUCT(AC21:AC{endrow},AD21:AD{endrow})/SUM(AD21:AD{endrow}),"N/A")';v['N12'].number_format='0.00'
 v['B16']='MOYENNE AVIS / CENTRE / MOIS';v['D16']=f'=IFERROR(B12/COUNTA(S21:S{endrow})/(12*(YEAR(M6)-YEAR(J6))+MONTH(M6)-MONTH(J6)+1),"N/C")';v['D16'].number_format='0.00'
 v['B17']='CENTRES DU RÉFÉRENTIEL';v['D17']=f'=COUNTA(S21:S{endrow})'
 v['L16']='SANS NOUVEL AVIS SUR PÉRIODE';v['O16']=f'=COUNTIF(AE21:AE{endrow},1)'
 # Keep existing merged dashboard zones; put definition in a comment instead of shifting the chart.
 from openpyxl.comments import Comment
 v['B11'].comment=Comment('Tous les centres du référentiel. Mois partiels Uberall provisoires. Les mois manquants ne sont pas des zéros.','Audika')
 v['B16'].comment=Comment('Avis N connus / nombre de centres du référentiel / nombre de mois sélectionnés. Les mois manquants ne sont pas des zéros.','Audika')
 # Prevent stale dropdown source formulas from surviving a changed reference.
 for sh in (v,s,c):
  for dv in sh.data_validations.dataValidation:
   if str(dv.sqref)=='B6':dv.formula1='RegionsDisponibles'
   if 'J6' in str(dv.sqref):dv.formula1='DatesDisponibles'
   if str(dv.sqref)=='F6':dv.formula1=f'=INDIRECT(IF($B$6="Toutes","SecteursTous","Secteurs"&MATCH($B$6,\'_LISTES\'!$A$3:$A${len(regs)+2},0)))' 
 for sh in (s,c):
  sector_rules=[dv for dv in sh.data_validations.dataValidation if 'F6' in str(dv.sqref)]
  if not sector_rules:
   dv=DataValidation(type='list',allow_blank=False)
   sh.add_data_validation(dv);dv.add('F6');sector_rules=[dv]
  for dv in sector_rules:
   dv.type='list';dv.showDropDown=False
   dv.formula1=f'=INDIRECT(IF($B$6="Toutes","SecteursTous","Secteurs"&MATCH($B$6,\'_LISTES\'!$A$3:$A${len(regs)+2},0)))'
 # All visible metrics must be based on the reference perimeter, not AA comparable flag.
 for sh in (v,s,c):
  for row in sh:
   for cell in row:
    if not isinstance(cell.value,str):continue
    if cell.data_type=='f':
     formula=re.sub(r',\$?AA\$?21:\$?AA\$?\d+,1(?=\))','',cell.value)
     formula=re.sub(r'SUMIFS\((\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+)\)',r'SUM(\1)',formula)
     cell.value=formula
    else:
     text=cell.value.replace('AVIS N COMPARABLES','AVIS N').replace('Avis N comparables','Avis N').replace('CENTRES COMPARABLES','CENTRES DU RÉFÉRENTIEL').replace('PÉRIMÈTRE CONSTANT','RÉFÉRENTIEL COMPLET')
     if 'centres comparables' in text.lower():text='Période : tous les centres du référentiel. Données manquantes signalées.'
     cell.value=text
 w.calculation=CalcProperties(calcMode='auto',fullCalcOnLoad=True,forceFullCalc=True)
 w.save(out)
 return {'centres':N,'base_rows':last-1,'template':'Consolide2'}
