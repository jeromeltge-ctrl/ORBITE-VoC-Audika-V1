const {
  app,
  BrowserWindow,
  ipcMain,
  dialog
} = require('electron');

const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

let win = null;
let backend = null;
let buffer = '';
let sequence = 0;

const pending = new Map();
function writeBackendLog(text) {
  try { fs.appendFileSync(path.join(app.getPath('userData'),'orbite-backend.log'),new Date().toISOString()+' '+text+'\n','utf8'); }
  catch (error) { console.error('ORBITE log:',error); }
}

const IMPORT_METHODS = new Set([
  'importReference',
  'importNps',
  'googleInspect',
  'googleImport'
]);

const IMPORT_EXTENSIONS = new Set([
  '.xlsx'
]);

// ======================================================
// 1. PREPARATION DES FICHIERS D'IMPORT
// ======================================================

async function prepareImportFile(method, params = {}) {

  if (!IMPORT_METHODS.has(method)) {
    return {
      params,
      temporaryDirectory: null
    };
  }

  if (
    typeof params.path !== 'string' ||
    !params.path.trim()
  ) {
    throw new Error(
      'Aucun fichier sélectionné pour l’import.'
    );
  }

  const sourcePath = path.resolve(params.path);

  const extension = path.extname(sourcePath).toLowerCase();

  if (!IMPORT_EXTENSIONS.has(extension)) {
    throw new Error(
      'Format non autorisé. Sélectionnez un fichier .xlsx.'
    );
  }

  let stats;

  try {
    stats = await fs.promises.stat(sourcePath);
  } catch (error) {
    throw new Error(
      'Le fichier sélectionné est introuvable ou inaccessible : ' +
      sourcePath
    );
  }

  if (!stats.isFile()) {
    throw new Error(
      'Le chemin sélectionné ne correspond pas à un fichier.'
    );
  }

  const temporaryDirectory = await fs.promises.mkdtemp(
    path.join(os.tmpdir(), 'orbite-import-')
  );

  const temporaryPath = path.join(
    temporaryDirectory,
    'import.xlsx'
  );

  try {

    await fs.promises.copyFile(
      sourcePath,
      temporaryPath
    );

    const copiedStats = await fs.promises.stat(
      temporaryPath
    );

    if (
      !copiedStats.isFile() ||
      copiedStats.size !== stats.size
    ) {
      throw new Error(
        'La copie temporaire du fichier est incomplète.'
      );
    }

    return {
      params: {
        ...params,
        path: temporaryPath
      },
      temporaryDirectory
    };

  } catch (error) {

    await fs.promises.rm(
      temporaryDirectory,
      {
        recursive: true,
        force: true
      }
    );

    throw error;
  }
}

// ======================================================
// 2. NETTOYAGE DES FICHIERS TEMPORAIRES
// ======================================================

async function cleanupTemporaryDirectory(directory) {

  if (!directory) {
    return;
  }

  try {

    await fs.promises.rm(
      directory,
      {
        recursive: true,
        force: true,
        maxRetries: 3,
        retryDelay: 200
      }
    );

  } catch (error) {

    console.error(
      'ORBITE - Nettoyage temporaire impossible :',
      error
    );
  }
}

// ======================================================
// 3. GESTION DES REQUETES EN ATTENTE
// ======================================================

function rejectAllPending(message) {

  for (const [, job] of pending) {

    clearTimeout(job.timeout);

    job.reject(
      new Error(message)
    );
  }

  pending.clear();
}

// ======================================================
// 4. DEMARRAGE DU MOTEUR PYTHON
// ======================================================

function launch() {

  const exe = app.isPackaged
    ? path.join(
        process.resourcesPath,
        'backend',
        'orbite_backend.exe'
      )
    : null;

  const script = path.join(
    __dirname,
    '..',
    'backend',
    'orbite_backend.py'
  );

  const cmd = exe || (
    process.platform === 'win32'
      ? 'python'
      : 'python3'
  );

  const args = exe ? [] : [script];

  const environment = {
    ...process.env,

    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',

    ORBITE_DATA_DIR: app.getPath('userData'),

    ORBITE_MODEL_PATH: app.isPackaged
      ? path.join(
          process.resourcesPath,
          'backend',
          'modele_consolide2.xlsx'
        )
      : path.join(
          __dirname,
          '..',
          'backend',
          'modele_consolide2.xlsx'
        )
  };

  writeBackendLog('Starting backend: '+cmd);
  backend = spawn(
    cmd,
    args,
    {
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
      env: environment
    }
  );

  backend.stdout.setEncoding('utf8');

  backend.stdout.on('data', chunk => {

    buffer += chunk;

    let pos;

    while ((pos = buffer.indexOf('\n')) >= 0) {

      const line = buffer.slice(0, pos).trim();

      buffer = buffer.slice(pos + 1);

      if (!line) {
        continue;
      }

      try {

        const msg = JSON.parse(line);

        const job = pending.get(msg.id);

        if (!job) {
          continue;
        }

        pending.delete(msg.id);

        clearTimeout(job.timeout);

        if (msg.error) {

          job.reject(
            new Error(msg.error)
          );

        } else {

          job.resolve(msg.data);
        }

      } catch (error) {

        console.error(
          'ORBITE - Erreur protocole Python :',
          error
        );
      }
    }
  });

  backend.stderr.on('data', data => {
    writeBackendLog('Python stderr: '+data.toString('utf8'));

    console.error(
      'ORBITE - Python :',
      data.toString('utf8')
    );
  });

  backend.on('error', error => {
    writeBackendLog('Spawn error: '+error.message);

    console.error(
      'ORBITE - Démarrage Python impossible :',
      error
    );

    rejectAllPending(
      'Impossible de démarrer le moteur ORBITE.'
    );
  });

  backend.on('exit', (code,signal) => {
    writeBackendLog('Backend exit code='+code+' signal='+signal);

    rejectAllPending(
      'Le moteur local ORBITE est indisponible.'
    );
  });
}

// ======================================================
// 5. COMMUNICATION ELECTRON / PYTHON
// ======================================================

function invokeBackend(method, params = {}) {

  return new Promise((resolve, reject) => {

    if (
      !backend ||
      backend.exitCode !== null ||
      backend.killed ||
      !backend.stdin.writable
    ) {

      return reject(
        new Error(
          'Le moteur ORBITE est indisponible.'
        )
      );
    }

    const id = ++sequence;

    const timeout = setTimeout(() => {

      if (pending.has(id)) {

        pending.delete(id);

        reject(
          new Error(
            'Le moteur ORBITE ne répond pas.'
          )
        );
      }

    }, method === 'googleExport' ? 1200000 : method === 'googleImport' ? 300000 : 120000);

    pending.set(id, {
      resolve,
      reject,
      timeout
    });

    const payload = JSON.stringify({
      id,
      method,
      params
    }) + '\n';

    backend.stdin.write(
      payload,
      'utf8',
      error => {

        if (
          error &&
          pending.has(id)
        ) {

          pending.delete(id);

          clearTimeout(timeout);

          reject(error);
        }
      }
    );
  });
}

// ======================================================
// 6. IMPORT AVEC COPIE TEMPORAIRE
// ======================================================

async function invoke(method, params = {}) {

  let temporaryDirectory = null;

  try {

    const prepared = await prepareImportFile(
      method,
      params
    );

    temporaryDirectory = prepared.temporaryDirectory;

    return await invokeBackend(
      method,
      prepared.params
    );

  } finally {

    await cleanupTemporaryDirectory(
      temporaryDirectory
    );
  }
}

// ======================================================
// 7. INITIALISATION ELECTRON
// ======================================================

app.whenReady().then(() => {

  launch();

  ipcMain.handle(
    'orbite:call',
    async (_event, method, params) => {

      return await invoke(
        method,
        params || {}
      );
    }
  );

  ipcMain.handle(
    'orbite:pick',
    async (_event, save, filters) => {

      const options = {
        filters: filters || [
          {
            name: 'Excel',
            extensions: ['xlsx']
          }
        ]
      };

      const result = save
        ? await dialog.showSaveDialog(
            win,
            options
          )
        : await dialog.showOpenDialog(
            win,
            {
              ...options,
              properties: ['openFile']
            }
          );

      if (result.canceled) {
        return null;
      }

      return save
        ? result.filePath
        : result.filePaths[0];
    }
  );

  win = new BrowserWindow({

    width: 1500,
    height: 940,

    minWidth: 1050,
    minHeight: 700,

    backgroundColor: '#f3f7fb',

    webPreferences: {

      preload: path.join(
        __dirname,
        'preload.cjs'
      ),

      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.removeMenu();

  if (
    !app.isPackaged &&
    process.env.ORBITE_DEV_URL
  ) {

    win.loadURL(
      process.env.ORBITE_DEV_URL
    );

  } else {

    win.loadFile(
      path.join(
        __dirname,
        '..',
        'dist',
        'index.html'
      )
    );
  }
});

// ======================================================
// 8. FERMETURE
// ======================================================

app.on('before-quit', () => {

  rejectAllPending(
    'ORBITE est en cours de fermeture.'
  );

  if (backend) {
    backend.kill();
  }
});

app.on('window-all-closed', () => {

  if (process.platform !== 'darwin') {
    app.quit();
  }
});
