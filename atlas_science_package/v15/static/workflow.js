/* ATLAS v1.5 unified workflow; server response and research data are untrusted.
   Always use textContent, never HTML interpolation or arbitrary server URLs. */
'use strict';
const el = id => document.getElementById(id);
let lastReport = null;
function add(parent, tag, value, css) {
  const node = document.createElement(tag);
  if (css) node.className = css;
  node.textContent = String(value ?? '');
  parent.appendChild(node);
  return node;
}
function card(parent, name, detail) {
  const node = add(parent, 'article', '', 'paper');
  add(node, 'h3', name);
  if (detail !== undefined) {
    const content = typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2);
    const body = add(node, 'pre', content, 'meta');
    body.style.whiteSpace = 'pre-wrap';
    body.style.overflowWrap = 'anywhere';
  }
  return node;
}
function asArray(id, limit) {
  const input = el(id).value.trim();
  let result;
  try { result = input ? JSON.parse(input) : []; }
  catch { throw Error(`${id}: expected a valid JSON array`); }
  if (!Array.isArray(result) || result.length > limit || result.some(v => !v || typeof v !== 'object' || Array.isArray(v))) {
    throw Error(`${id}: expected an array of up to ${limit} objects`);
  }
  return result;
}
function linkForDoi(cardEl, doi) {
  // Generate link exclusively from validated DOI-shaped string, no response URLs.
  if (typeof doi === 'string' && /^10\.\d{4,9}\/[a-zA-Z0-9._;()/:+-]{1,170}$/.test(doi)) {
    const link = add(cardEl, 'a', 'DOI record ↗');
    link.href = 'https://doi.org/' + encodeURIComponent(doi);
    link.rel = 'noopener noreferrer'; link.target = '_blank';
  }
}
function render(report) {
  lastReport = report;
  for (const id of ['answer','plan','sources','literatureResults','checks']) el(id).replaceChildren();
  add(el('answer'), 'pre', report.answer || '(No answer)', 'meta');
  add(el('answer'), 'p', `Status: ${report.answer_status || 'UNKNOWN'}`, 'muted');
  add(el('answer'), 'p', `Report fingerprint: ${report.report_sha256 || 'none'}`, 'muted');
  if (report.model_interpretation?.status) add(el('answer'), 'p', `Model interpretation: ${report.model_interpretation.status}`, 'muted');
  for (const line of report.limitations || []) add(el('answer'), 'p', `• ${line}`, 'muted');
  card(el('plan'), 'Execution plan', report.plan || {});
  for (const step of report.execution_trace || []) card(el('plan'), `${step.id} · ${step.tool}`, step);
  const sources = report.source_index || [];
  if (!sources.length) add(el('sources'), 'p', 'No crosschecked primary-text passages. Scientific conclusions are not substantiated by primary text in this run.', 'muted');
  for (const source of sources) {
    const entry = card(el('sources'), `${source.citation_id} · ${source.title}`, source.excerpt);
    add(entry, 'p', `${source.section}, paragraph ${source.paragraph} · ${source.verification}`, 'muted');
    add(entry, 'p', `DOI ${source.doi} · XML SHA-256 ${source.document_sha256}`, 'muted');
    linkForDoi(entry, source.doi);
  }
  const literature = report.literature || {};
  add(el('literatureResults'), 'p', `OpenAlex/Crossref/Europe PMC: ${literature.status || 'NOT_REQUESTED'} · arXiv: ${report.arxiv_discovery?.status || 'NOT_REQUESTED'} (metadata only)`, 'muted');
  for (const paper of literature.papers || []) {
    const entry = card(el('literatureResults'), paper.title || 'Untitled publication', `${paper.year || 'year not available'} · ${paper.verification?.status || 'UNCHECKED'} · ${paper.primary_source?.status || 'NO_PRIMARY_TEXT'}`);
    linkForDoi(entry, paper.doi);
  }
  for (const item of report.arxiv_discovery?.papers || []) {
    const entry = card(el('literatureResults'), `Preprint · ${item.title || 'Untitled'}`, `${item.arxiv_id || ''} · ${item.status || 'METADATA_ONLY'}`);
    if (typeof item.arxiv_id === 'string' && /^(?:\d{4}\.\d{4,5}|[A-Za-z.-]+(?:\.[A-Z]{2})?\/\d{7})(?:v[1-9]\d{0,2})?$/.test(item.arxiv_id)) {
      const anchor = add(entry, 'a', 'arXiv record ↗'); anchor.href = 'https://arxiv.org/abs/' + item.arxiv_id;
      anchor.rel = 'noopener noreferrer'; anchor.target = '_blank';
    }
  }
  if (report.theory_comparison?.theories?.length) card(el('literatureResults'), 'Theory evidence matrix (lexical, NOT independently assessed)', report.theory_comparison);
  for (const [key, label] of [['dimensional_checks','Dimension'], ['symbolic_checks','Symbolic'], ['numerical_runs','Numerical']]) {
    for (const check of report.calculations?.[key] || []) card(el('checks'), `${label} · ${check.status}`, check);
  }
  if (!el('checks').childElementCount) add(el('checks'), 'p', 'No formal calculation tasks selected.', 'muted');
  el('export').disabled = false;
}
async function run() {
  el('run').disabled = true; el('status').textContent = 'Running bounded research workflow…';
  try {
    const payload = {
      question: el('question').value.trim(), literature: el('literature').value, arxiv: el('arxiv').value,
      theories: asArray('theories',4), dimensional_tasks: asArray('dimensions',4),
      symbolic_tasks: asArray('symbolic',4), numerical_tasks: asArray('numerical',3),
      provider: el('provider').value, auto_symbolic: el('autoSymbolic').checked
    };
    const model = el('model').value.trim(); if (model) payload.model = model;
    const session = await fetch('/auth/session', {cache:'no-store'});
    if (session.status === 401) { window.location.assign('/login'); throw Error('Login required'); }
    if (!session.ok) throw Error('Cannot validate session');
    const csrf = (await session.json()).csrf || '';
    const headers = {'Content-Type':'application/json'};
    if (csrf) headers['X-Atlas-CSRF'] = csrf;
    const token = el('token').value.trim(); if (token) headers['X-Atlas-Token'] = token;
    const response = await fetch('/api/science/workflow', {
      method:'POST', headers, body: JSON.stringify(payload), cache:'no-store'
    });
    if (!response.ok) {
      let error = {}; try { error = await response.json(); } catch {}
      throw Error((typeof error.detail === 'string' ? error.detail : `HTTP ${response.status}`).slice(0,220));
    }
    render(await response.json()); el('status').textContent = 'Run complete. Inspect verification labels and limitations.';
  } catch (error) { el('status').textContent = `Unavailable: ${error.message}`; }
  finally { el('run').disabled = false; }
}
function exportReport() {
  if (!lastReport) return;
  const blob = new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href=url; a.download='atlas-research-v15.json'; a.click();
  URL.revokeObjectURL(url);
}
el('run').addEventListener('click',run);
el('export').addEventListener('click',exportReport);
