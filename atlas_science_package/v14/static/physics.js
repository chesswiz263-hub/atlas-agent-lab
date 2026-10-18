/* ATLAS v1.4 physics laboratory. Untrusted response fields are text-only. */
'use strict';
const el = id => document.getElementById(id);
let dossier = null;
function append(parent, tag, value, cls) {
  const x = document.createElement(tag);
  if (cls) x.className = cls;
  x.textContent = String(value ?? '');
  parent.appendChild(x);
  return x;
}
function jsonArray(id, limit) {
  const value = el(id).value.trim();
  let parsed;
  try { parsed = value ? JSON.parse(value) : []; }
  catch { throw new Error(`${id} must be valid JSON`); }
  if (!Array.isArray(parsed) || parsed.length > limit) throw new Error(`${id} needs at most ${limit} objects`);
  return parsed;
}
function resultCard(title, payload) {
  const card = append(el('checks'), 'article', '', 'paper');
  append(card, 'h3', title);
  const code = append(card, 'pre', JSON.stringify(payload, null, 2), 'meta');
  code.style.whiteSpace = 'pre-wrap';
  code.style.overflowWrap = 'anywhere';
}
function render(out) {
  dossier = out;
  el('summary').replaceChildren();
  append(el('summary'),'p',out.answer || 'No summary');
  append(el('summary'),'p',`Status: ${out.answer_status}`,'muted');
  for (const note of out.limitations || []) append(el('summary'),'p',`• ${note}`,'muted');
  el('papers').replaceChildren();
  append(el('papers'),'p',`arXiv: ${out.arxiv_discovery?.status || 'UNKNOWN'} · ${out.arxiv_discovery?.verification || 'no verification'}`,'muted');
  for (const paper of out.arxiv_discovery?.papers || []) {
    const card = append(el('papers'),'article','','paper');
    append(card,'h3',paper.title);
    append(card,'p',`${paper.arxiv_id} · ${paper.published} · ${paper.authors.join(', ')}`,'meta');
    append(card,'p',paper.abstract);
    append(card,'p',`${paper.status} · metadata SHA-256 ${paper.metadata_sha256}`,'muted');
    // Backend builds URLs from validated arXiv IDs; never trust arbitrary returned URLs.
    if (/^(?:\d{4}\.\d{4,5}|[A-Za-z.-]+(?:\.[A-Z]{2})?\/\d{7})(?:v[1-9]\d{0,2})?$/.test(paper.arxiv_id)) {
      const link = append(card,'a','Open arXiv record ↗');
      link.href = `https://arxiv.org/abs/${paper.arxiv_id}`;
      link.target='_blank'; link.rel='noopener noreferrer';
    }
  }
  el('checks').replaceChildren();
  for (const [field, label] of [['dimensional_checks','Dimensions'],['symbolic_checks','Symbolic'],['numerical_runs','Numerical']]) {
    for (const item of out[field] || []) resultCard(`${label} · ${item.status}`,item);
  }
  el('export').disabled = false;
}
async function run() {
  el('run').disabled = true;
  el('status').textContent = 'Running bounded physics research…';
  try {
    const payload = {question: el('question').value.trim(), search_arxiv: el('searchArxiv').checked,
      dimensional_tasks: jsonArray('dimTasks',4), symbolic_tasks: jsonArray('symTasks',4),
      numerical_tasks: jsonArray('numTasks',3)};
    const session = await fetch('/auth/session',{cache:'no-store'});
    if (session.status === 401) { location.assign('/login'); throw new Error('Sign in required'); }
    if (!session.ok) throw new Error('Could not validate session');
    const csrf = (await session.json()).csrf || '';
    const headers = {'Content-Type':'application/json'};
    if (csrf) headers['X-Atlas-CSRF'] = csrf;
    if (el('token').value.trim()) headers['X-Atlas-Token'] = el('token').value.trim();
    const r = await fetch('/api/science/physics',{method:'POST',headers,body:JSON.stringify(payload),cache:'no-store'});
    if (!r.ok) { let err = {}; try {err = await r.json();}catch{} throw new Error((typeof err.detail === 'string' ? err.detail : `HTTP ${r.status}`).slice(0,220)); }
    render(await r.json()); el('status').textContent = 'Completed. Inspect scope and evidence labels.';
  } catch (e) {el('status').textContent = `Unavailable: ${e.message}`;}
  finally {el('run').disabled = false;}
}
function exportJson() {if (!dossier) return; const blob = new Blob([JSON.stringify(dossier,null,2)],{type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download='atlas-physics-v14.json';a.click();URL.revokeObjectURL(url);}
el('run').addEventListener('click',run);
el('export').addEventListener('click',exportJson);
