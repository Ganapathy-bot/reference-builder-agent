const form = document.querySelector('#citation-form');
const input = document.querySelector('#reference-input');
const results = document.querySelector('#results');
const progress = document.querySelector('#progress');
const submitButton = document.querySelector('#submit-button');
let lastResults = [];

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function selectedStyles() {
  return [...document.querySelectorAll('#style-options input:checked')].map((item) => item.value);
}

function authorLine(metadata) {
  return (metadata.authors || []).map((author) => [author.given, author.family].filter(Boolean).join(' ')).join(', ');
}

function renderSuccess(result, index = 0) {
  const metadata = result.metadata || {};
  const percent = Math.round((result.verification?.score || 0) * 100);
  const citations = Object.entries(result.citations || {}).map(([style, text]) => `
    <article class="citation-block">
      <div class="block-heading"><span>${escapeHtml(style.toUpperCase())}</span><button class="icon-button" data-copy="${escapeHtml(text)}">Copy</button></div>
      <p class="citation-text">${escapeHtml(text)}</p>
      ${result.citation_notes?.[style]?.length ? `<div class="notes">${result.citation_notes[style].map(escapeHtml).join('<br>')}</div>` : ''}
    </article>`).join('');
  const bibtex = result.bibtex ? `<div class="bibtex-block"><div class="bibtex-head"><span>BIBTEX</span><button class="icon-button" data-copy="${escapeHtml(result.bibtex)}">Copy</button></div><pre>${escapeHtml(result.bibtex)}</pre></div>` : '';
  const warnings = (result.warnings || []).length ? `<div class="warnings">${result.warnings.map(escapeHtml).join('<br>')}</div>` : '';
  return `
    <div class="result-banner"><div class="result-status"><span class="status-mark">✓</span><span>RECORD FOUND</span></div><div class="confidence">METADATA CONFIDENCE <strong>${percent}%</strong></div></div>
    <div class="metadata-strip"><div><div class="metadata-title">${escapeHtml(metadata.title || 'Untitled record')}</div><div class="metadata-byline">${escapeHtml(authorLine(metadata))}${metadata.year ? ` · ${escapeHtml(metadata.year)}` : ''}${metadata.journal ? ` · ${escapeHtml(metadata.journal)}` : ''}</div><div class="source-list">SOURCES · ${escapeHtml((result.sources || []).join(' / ') || 'metadata cache')}</div></div><div class="result-actions"><button class="secondary-button" data-save="${index}">Save reference</button></div></div>
    ${citations}${bibtex}${warnings}`;
}

function renderResponse(result) {
  if (result.status === 'needs_confirmation') {
    const candidates = (result.candidates || []).map(({ candidate_id, metadata }) => `
      <div class="candidate-card"><div><h3>${escapeHtml(metadata.title)}</h3><p>${escapeHtml(authorLine(metadata))}${metadata.year ? ` · ${escapeHtml(metadata.year)}` : ''}${metadata.journal ? ` · ${escapeHtml(metadata.journal)}` : ''}</p></div><button class="secondary-button" data-candidate="${escapeHtml(candidate_id)}">Choose</button></div>`).join('');
    results.innerHTML = `<div class="result-banner"><div class="result-status"><span class="status-mark">?</span><span>CHOOSE A MATCH</span></div></div><p class="muted">${escapeHtml(result.message || 'Several records may match this input.')}</p><div class="candidate-list">${candidates}</div>`;
  } else if (result.status === 'success') {
    results.innerHTML = renderSuccess(result);
  } else {
    results.innerHTML = `<div class="warnings">${escapeHtml(result.message || 'No matching record was found. Try a DOI or a more specific title.')}</div>`;
  }
  results.hidden = false;
}

async function postJson(url, body) {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
  return data;
}

async function generate(candidateId) {
  const styles = selectedStyles();
  if (!styles.length) throw new Error('Choose at least one citation style.');
  const body = {
    input: input.value.trim(), styles,
    include_bibtex: document.querySelector('#bibtex-toggle').checked,
    validate: document.querySelector('#validate-toggle').checked,
  };
  if (candidateId) body.candidate_id = candidateId;
  const lines = body.input.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const batch = document.querySelector('#batch-toggle').checked && lines.length > 1;
  const data = batch
    ? await postJson('/api/v1/batch', { ...body, input: lines.join('\n') })
    : await postJson('/api/v1/citation', body);
  if (batch) {
    lastResults = data.results || [];
    results.innerHTML = `<div class="result-banner"><div class="result-status"><span class="status-mark">✓</span><span>${lastResults.length} REFERENCES PROCESSED</span></div><button class="secondary-button" data-download-batch="download">Download BibTeX</button></div>${lastResults.map((result, index) => `<div class="batch-result"><div class="block-heading"><span>REFERENCE ${String(index + 1).padStart(2, '0')}</span></div>${result.status === 'success' ? renderSuccess(result, index) : `<div class="warnings">${escapeHtml(result.message || result.status)}</div>`}</div>`).join('')}`;
    results.hidden = false;
  } else {
    lastResults = [data];
    renderResponse(data);
  }
  await refreshLibrary();
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!input.value.trim()) return;
  results.hidden = true;
  progress.hidden = false;
  submitButton.disabled = true;
  document.querySelector('#progress-label').textContent = 'Searching bibliographic sources…';
  try {
    await generate();
  } catch (error) {
    results.innerHTML = `<div class="warnings">${escapeHtml(error.message)}</div>`;
    results.hidden = false;
  } finally {
    progress.hidden = true;
    submitButton.disabled = false;
  }
});

document.querySelector('#reference-input').addEventListener('input', (event) => {
  document.querySelector('#char-count').textContent = `${event.target.value.length.toLocaleString()} / 20,000`;
});

results.addEventListener('click', async (event) => {
  const copyButton = event.target.closest('[data-copy]');
  const candidateButton = event.target.closest('[data-candidate]');
  const saveButton = event.target.closest('[data-save]');
  const downloadButton = event.target.closest('[data-download-batch]');
  if (copyButton) {
    await navigator.clipboard.writeText(copyButton.dataset.copy);
    copyButton.textContent = 'Copied';
  }
  if (candidateButton) {
    progress.hidden = false;
    try { await generate(candidateButton.dataset.candidate); }
    catch (error) { results.insertAdjacentHTML('afterbegin', `<div class="warnings">${escapeHtml(error.message)}</div>`); }
    finally { progress.hidden = true; }
  }
  if (saveButton) {
    const result = lastResults[Number(saveButton.dataset.save) || 0];
    if (!result?.metadata) return;
    try {
      await postJson('/api/v1/library', { record: result.metadata, citations: result.citations, bibtex: result.bibtex });
      saveButton.textContent = 'Saved';
      saveButton.disabled = true;
      await refreshLibrary();
    } catch (error) { saveButton.textContent = error.message; }
  }
  if (downloadButton) downloadBib(lastResults.filter((item) => item.bibtex).map((item) => item.bibtex).join('\n\n'));
});

function downloadBib(contents) {
  if (!contents) return;
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([contents], { type: 'application/x-bibtex' }));
  link.download = 'references.bib';
  link.click();
  URL.revokeObjectURL(link.href);
}

async function refreshLibrary() {
  try {
    const response = await fetch('/api/v1/library');
    const items = await response.json();
    document.querySelector('#library-count').textContent = items.length;
    document.querySelector('#recent-list').innerHTML = items.slice(0, 6).map((item) => `<button class="recent-item" data-open-library="${escapeHtml(item.id)}" title="${escapeHtml(item.title)}">${escapeHtml(item.title || 'Untitled reference')}</button>`).join('') || '<span class="muted small">Your saved references will appear here.</span>';
    const library = document.querySelector('#library-items');
    library.innerHTML = items.map((item) => `<article class="library-row" id="item-${escapeHtml(item.id)}"><div><h3>${escapeHtml(item.title || 'Untitled reference')}</h3><p>${escapeHtml(authorLine(item.record || {}))}${item.year ? ` · ${escapeHtml(item.year)}` : ''}${item.doi ? ` · ${escapeHtml(item.doi)}` : ''}</p></div><div class="library-actions"><button class="icon-button" data-copy="${escapeHtml(item.bibtex || '')}">Copy BibTeX</button><button class="icon-button" data-delete="${escapeHtml(item.id)}">Remove</button></div></article>`).join('') || '<div class="empty-state">No saved references yet.</div>';
  } catch { /* The interface remains usable while the API is unavailable. */ }
}

document.querySelector('#library-items').addEventListener('click', async (event) => {
  const copyButton = event.target.closest('[data-copy]');
  if (copyButton) {
    await navigator.clipboard.writeText(copyButton.dataset.copy);
    copyButton.textContent = 'Copied';
    return;
  }
  const button = event.target.closest('[data-delete]');
  if (!button) return;
  await fetch(`/api/v1/library/${encodeURIComponent(button.dataset.delete)}`, { method: 'DELETE' });
  await refreshLibrary();
});

document.querySelector('#export-library').addEventListener('click', async () => {
  const response = await fetch('/api/v1/library');
  const items = await response.json();
  downloadBib(items.map((item) => item.bibtex).filter(Boolean).join('\n\n'));
});

document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => {
  const libraryView = button.dataset.view === 'library';
  document.querySelector('#compose-view').hidden = libraryView;
  document.querySelector('#library-view').hidden = !libraryView;
  document.querySelectorAll('[data-view]').forEach((item) => item.classList.toggle('active', item === button));
  if (libraryView) refreshLibrary();
}));

document.querySelector('#recent-list').addEventListener('click', (event) => {
  const item = event.target.closest('[data-open-library]');
  if (!item) return;
  document.querySelector('[data-view="library"]').click();
  document.querySelector(`#item-${CSS.escape(item.dataset.openLibrary)}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

fetch('/api/health').then((response) => {
  if (!response.ok) throw new Error('offline');
  document.querySelector('.service-state').classList.add('online');
  document.querySelector('#service-label').textContent = 'Service online';
}).catch(() => { document.querySelector('#service-label').textContent = 'Service offline'; });

refreshLibrary();