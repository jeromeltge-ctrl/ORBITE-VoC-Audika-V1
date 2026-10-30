const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function bridge() {
  let api;
  const calls = [];
  const electron = {
    contextBridge: {exposeInMainWorld: (name, value) => {assert.equal(name, 'orbite'); api = value;}},
    ipcRenderer: {invoke: (...args) => {calls.push(args); return Promise.resolve('ok');}}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'preload.cjs'), 'utf8'), {
    require: name => {assert.equal(name, 'electron'); return electron;}
  });
  return {api, calls};
}

test('existing read, NPS and Google calls retain their contracts', async () => {
  const {api, calls} = bridge();
  for (const method of ['summary','npsDashboard','questionAnalysis','network','googleImport','googleExport']) {
    const params = {region:'Nord'};
    assert.equal(await api.call(method, params), 'ok');
    assert.deepEqual(calls.at(-1), ['orbite:call',method,params]);
  }
});
test('legacy inventory and reset are allowed through preload', async () => {
  const {api, calls} = bridge();
  await api.call('legacyImportStatus');
  await api.call('resetLegacyNps', {confirmation:'REINITIALISER ANCIENS NPS'});
  assert.equal(calls.length, 2);
  assert.equal(calls[1][1], 'resetLegacyNps');
});
test('unconfirmed deletion never reaches IPC', async () => {
  const {api, calls} = bridge();
  for (const params of [undefined, {}, {id:1}, {id:1,confirmation:'SUPPRIMER IMPORT NPS 2'}]) {
    await assert.rejects(api.call('deleteImport',params), /Confirmation explicite/);
  }
  assert.equal(calls.length, 0);
});
test('invalid destructive identifiers never reach IPC', async () => {
  const {api, calls} = bridge();
  for (const id of [true,false,0,-1,1.5,'1',NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    await assert.rejects(api.call('deleteImport',{id,confirmation:`SUPPRIMER IMPORT NPS ${id}`}), /Confirmation explicite/);
  }
  assert.equal(calls.length, 0);
});
test('confirmed deletion preserves the selected batch', async () => {
  const {api, calls} = bridge();
  const params = {id:42,confirmation:'SUPPRIMER IMPORT NPS 42'};
  await api.call('deleteImport',params);
  assert.deepEqual(calls, [['orbite:call','deleteImport',params]]);
});
test('unknown actions are rejected and file picking is unchanged', async () => {
  const {api, calls} = bridge();
  await assert.rejects(api.call('arbitrary-command'), /Action non autorisée/);
  assert.equal(calls.length, 0);
  const filters = [{name:'Excel',extensions:['xlsx']}];
  await api.pick(false, filters);
  assert.deepEqual(calls, [['orbite:pick',false,filters]]);
});
