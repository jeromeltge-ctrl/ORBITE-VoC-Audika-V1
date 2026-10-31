const {contextBridge,ipcRenderer}=require('electron');
const allowed=new Set([
 'summary','campaigns','timeline','verbatims','network','filters','questions',
 'surveyDetail','compareSurveys','imports','importReference','importNps',
 'publish','loadPublication','exportVerbatims','exportEreputation','surveyCreate',
 'health','npsDashboard','questionAnalysis','questionHistory','questionProfile',
 'questionResults','googleInspect','googleImport','googleSummary','googleExport',
 'deleteImport','legacyImportStatus','resetLegacyNps',
 'qaHistoricalCatalog','qaQuickResult','qaDashboardSave','qaDashboardList',
 'qaDashboardLoad','qaDashboardDuplicate','qaDashboardDelete','qaStatistics',
 'qaExport','qaDashboardExport'
]);
contextBridge.exposeInMainWorld('orbite',{
 call:(name,params)=>{
  if(!allowed.has(name))return Promise.reject(new Error('Action non autorisée'));
  if(name==='deleteImport' && (!Number.isSafeInteger(params?.id)||params.id<=0||
    params.confirmation!==`SUPPRIMER IMPORT NPS ${params.id}`)){
   return Promise.reject(new Error('Confirmation explicite de suppression requise'));
  }
  return ipcRenderer.invoke('orbite:call',name,params);
 },
 pick:(save,filters)=>ipcRenderer.invoke('orbite:pick',!!save,filters)
});
