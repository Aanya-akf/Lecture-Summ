import './style.css';
import { Streamlit } from 'streamlit-component-lib';

const root = document.querySelector('#app');

root.innerHTML = `
  <div class="uploader">
    <div class="upload-icon">↑</div>
    <h2>Upload your lecture</h2>
    <p class="subtitle">Choose an audio or video recording to upload to your private Drive storage.</p>

    <label class="file-picker" for="file-input">
      <span id="file-label">Choose an audio or video file</span>
      <input
        id="file-input"
        type="file"
        accept=".mp3,.wav,.m4a,.mp4,.mkv,.webm,.ogg,.mpeg,.avi,.mov,.m4v,.mpg,.3gp,.flac,.aac,.opus"
      />
    </label>

    <div id="file-info" class="file-info">Maximum file size: 1 GB</div>

    <button id="upload-button" disabled>Upload lecture</button>

    <div id="progress-area" hidden>
      <div class="progress-track">
        <div id="progress-bar"></div>
      </div>
      <p id="status">Preparing upload...</p>
    </div>

    <div id="message" role="status"></div>
  </div>
`;

const fileInput    = document.querySelector('#file-input');
const fileLabel    = document.querySelector('#file-label');
const fileInfo     = document.querySelector('#file-info');
const uploadButton = document.querySelector('#upload-button');
const progressArea = document.querySelector('#progress-area');
const progressBar  = document.querySelector('#progress-bar');
const statusText   = document.querySelector('#status');
const message      = document.querySelector('#message');

const MAX_SIZE = 1024 * 1024 * 1024;
let componentArgs = {};

// ── Helpers ─────────────────────────────────────────────────────────────────
function showMessage(text, type = '') {
  message.textContent = text;
  message.className = type;
}

function setProgress(percent, text) {
  progressArea.hidden = false;
  progressBar.style.width = `${percent}%`;
  statusText.textContent = text;
}

// ── Theme bridge ─────────────────────────────────────────────────────────────
// The site's light/dark toggle lives in Python (st.session_state.dark_mode),
// NOT in Streamlit's own theme, so Python passes the real palette in
// args.theme. We mirror those tokens onto :root so this component always
// matches the page.
function readParentTheme() {
  try {
    const cs = getComputedStyle(window.parent.document.documentElement);
    const g = n => cs.getPropertyValue(n).trim();
    const t = {
      dark: cs.colorScheme.includes('dark'),
      text: g('--text'), muted: g('--muted'), surface: g('--surface'), surface2: g('--surface-2'),
      accent: g('--accent'), accent2: g('--accent-2'), border: g('--border'), glow: g('--glow'),
      good: g('--good'), titleA: g('--title-a'), titleB: g('--title-b'),
      primaryBg: g('--primary-bg'), primaryShadow: g('--primary-shadow'),
      primaryShadowHover: g('--primary-shadow-hover'),
    };
    return t.surface ? t : {};
  } catch (e) { return {}; }
}

function applyTheme(args, streamlitTheme) {
  const t = args.theme || readParentTheme();
  const dark = typeof t.dark === 'boolean' ? t.dark : streamlitTheme?.base === 'dark';
  const rootEl = document.documentElement;

  // The iframe is only transparent when its color-scheme matches the element
  // that embeds it. Otherwise the browser paints an opaque (black) canvas.
  let scheme = dark ? 'dark' : 'light';
  try {
    const cs = getComputedStyle(window.frameElement).colorScheme || '';
    scheme = cs.includes('dark') && !cs.includes('light') ? 'dark' : 'light';
  } catch (e) { /* cross-origin: fall back to the dark flag */ }
  rootEl.style.colorScheme = scheme;

  const map = {
    '--text': t.text, '--muted': t.muted, '--surface': t.surface, '--surface-2': t.surface2,
    '--accent': t.accent, '--accent-2': t.accent2, '--border': t.border, '--glow': t.glow,
    '--success': t.good, '--title-a': t.titleA, '--title-b': t.titleB,
    '--primary-bg': t.primaryBg, '--primary-shadow': t.primaryShadow,
    '--primary-shadow-hover': t.primaryShadowHover,
  };
  Object.entries(map).forEach(([k, v]) => { if (v) rootEl.style.setProperty(k, v); });
  rootEl.style.setProperty('--danger', dark ? '#ff7a7a' : '#e05252');
  rootEl.dataset.theme = dark ? 'dark' : 'light';

  // Force the card surface on every element that could paint a box behind the
  // component (inline !important beats any stylesheet, including index.html's).
  const surface = t.surface || (dark ? '#171C2F' : '#FFFFFF');
  [document.documentElement, document.body, document.querySelector('#app')].forEach(el => {
    if (!el) return;
    el.style.setProperty('background', surface, 'important');
    el.style.setProperty('background-color', surface, 'important');
  });
}

// ── File validation ──────────────────────────────────────────────────────────
fileInput.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  showMessage('');

  if (!file) {
    uploadButton.disabled = true;
    return;
  }

  if (file.size <= 0 || file.size > MAX_SIZE) {
    showMessage('Please select a file between 1 byte and 1 GB.', 'error');
    fileInput.value = '';
    uploadButton.disabled = true;
    return;
  }

  fileLabel.textContent = file.name;
  fileInfo.textContent  = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  uploadButton.disabled = false;
});

// ── Upload session ───────────────────────────────────────────────────────────
function requestUploadSession(file, args) {
  return fetch(`${args.functionUrl}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': args.anonKey,
      'Authorization': `Bearer ${args.accessToken}`,
    },
    body: JSON.stringify({
      action:    'start-upload',
      file_name:  file.name,
      size_bytes: file.size,
      mime_type:  file.type || 'application/octet-stream',
      origin:     window.location.origin,
    }),
  }).then(async response => {
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Could not start the upload.');
    return data;
  });
}

// ── Chunk upload ─────────────────────────────────────────────────────────────
function uploadChunk(uploadUrl, chunk, start, end, total, mimeType) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', uploadUrl);
    xhr.setRequestHeader('Content-Type',  mimeType || 'application/octet-stream');
    xhr.setRequestHeader('Content-Range', `bytes ${start}-${end}/${total}`);

    xhr.onload = () => {
      if (xhr.status === 308) {
        resolve(null);
      } else if (xhr.status === 200 || xhr.status === 201) {
        try   { resolve(JSON.parse(xhr.responseText)); }
        catch { reject(new Error('Google Drive returned an invalid response.')); }
      } else {
        reject(new Error(
          `Google Drive upload failed (${xhr.status}): ${xhr.responseText.slice(0, 300)}`
        ));
      }
    };

    xhr.onerror = () => {
      const err = new Error('The browser could not reach Google Drive. This may be a CORS restriction or network issue.');
      err.isNetworkError = true;
      reject(err);
    };
    xhr.onabort = () => reject(new Error('Upload was cancelled.'));
    xhr.send(chunk);
  });
}

// ── Full upload flow ─────────────────────────────────────────────────────────
async function uploadToDrive(file, session) {
  const chunkSize = session.chunk_size || 8 * 1024 * 1024;
  let offset   = 0;
  let driveFile = null;

  while (offset < file.size) {
    const endExclusive = Math.min(offset + chunkSize, file.size);
    const chunk = file.slice(offset, endExclusive);

    let result    = null;
    let lastError = null;

    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        result    = await uploadChunk(session.upload_url, chunk, offset, endExclusive - 1, file.size, file.type);
        lastError = null;
        break;
      } catch (error) {
        lastError = error;
        if (attempt < 3) await new Promise(r => setTimeout(r, attempt * 1500));
      }
    }

    if (lastError) {
      const isLastChunk = endExclusive === file.size;
      if (isLastChunk && lastError.isNetworkError) {
        driveFile = { id: null, unverified: true };
        offset = endExclusive;
        break;
      }
      throw lastError;
    }

    offset = endExclusive;
    const percent = Math.min(99, Math.floor((offset / file.size) * 100));
    setProgress(percent, `Uploading… ${percent}%`);
    if (result) driveFile = result;
  }

  if (!driveFile?.id && !driveFile?.unverified) {
    throw new Error('Upload finished, but Google Drive did not return a file ID.');
  }
  return driveFile;
}

// ── Confirm upload ───────────────────────────────────────────────────────────
async function confirmUpload(session, driveFile, args) {
  const response = await fetch(args.functionUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': args.anonKey,
      'Authorization': `Bearer ${args.accessToken}`,
    },
    body: JSON.stringify({
      action:        'complete-upload',
      upload_id:     session.upload_id,
      drive_file_id: driveFile.id,
    }),
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(data.error || 'Could not verify the uploaded file.');
  return data;
}

// ── Upload button click ──────────────────────────────────────────────────────
uploadButton.addEventListener('click', async () => {
  const file = fileInput.files?.[0];
  if (!file || uploadButton.disabled) return;

  if (!componentArgs.accessToken || !componentArgs.anonKey || !componentArgs.functionUrl) {
    showMessage('Your login session is unavailable. Please sign in again.', 'error');
    return;
  }

  uploadButton.disabled = true;
  fileInput.disabled    = true;
  showMessage('');

  try {
    setProgress(0, 'Creating secure upload session…');
    const session = await requestUploadSession(file, componentArgs);

    if (!session.upload_url || !session.upload_id) {
      throw new Error('Supabase did not return a valid upload session.');
    }

    setProgress(0, 'Uploading directly to Google Drive…');
    const driveFile = await uploadToDrive(file, session);

    setProgress(100, 'Verifying upload…');
    const result = await confirmUpload(session, driveFile, componentArgs);

    setProgress(100, 'Upload complete!');
    statusText.style.color      = 'var(--success)';
    statusText.style.fontWeight = '700';

    showMessage(result.message || 'Your lecture was saved successfully.', 'success');

    Streamlit.setComponentValue({
      status:     'completed',
      upload_id:  result.upload_id,
      file_name:  result.file_name,
      size_bytes: file.size,
    });

  } catch (error) {
    console.error('Lecture upload error:', error);
    showMessage(error.message || 'Upload failed. Please try again.', 'error');
    uploadButton.disabled = false;
    fileInput.disabled    = false;
  }
});

// ── Frame height ─────────────────────────────────────────────────────────────
function fitHeight() {
  const height = document.querySelector('.uploader').offsetHeight + 16;
  Streamlit.setFrameHeight(height);
}

// ── Render event ─────────────────────────────────────────────────────────────
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, event => {
  componentArgs = event.detail.args || {};
  applyTheme(componentArgs, event.detail.theme);
  fitHeight();
});

new ResizeObserver(fitHeight).observe(document.querySelector('.uploader'));

Streamlit.setComponentReady();
fitHeight();