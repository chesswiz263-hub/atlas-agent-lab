/* v1.6: no HTML injection from research responses. All text rendered via textContent. */
'use strict';
const at = id => document.getElementById(id);
let current = null;
function text(parent, tag, content, className) {
  const n = document.createElement(tag);
  n.textContent = String(content ?? '');
  if (className) n.className = className;
  parent.appendChild(n); return n;
}
function entry(parent, heading, data) {
  const n = text(parent, 'article', '', 'paper');
  text(n, 'h3', heading);
  const v = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  const p = text(n, 'pre', v, 'meta');
  p.style.whiteSpace = 'pre-wrap'; p.style.overflowWrap = 'anywhere';
  return n;
}
function show(report) {
  current = report;
  for (const id of ['answer','coverage','trace','sources','foundation']) at(id).replaceChildren();
  entry(at('answer'), report.answer_status || 'Report', report.answer || 'No report');
  text(at('answer'), 'p', `Report SHA-256: ${report.report_sha256 || 'Unavailable'}`, 'muted');
  text(at('answer'), 'p', `Model: ${report.model_interpretation?.status || 'NOT_REQUESTED'}`, 'muted');
  for (const item of report.limitations || []) text(at('answer'), 'p', `• ${item}`, 'muted');
  entry(at('coverage'), 'Decomposition', report.decomposition || {});
  for (const gap of report.coverage?.labels || []) entry(at('coverage'), `${gap.id}: ${gap.status}`, gap);
  entry(at('trace'), 'Budgets', report.budgets || {});
  for (const step of report.execution_trace || []) entry(at('trace'), step.stage, step);
  for (const source of report.citation_ledger || []) {
    entry(at('sources'), source.citation_id, `${source.title || 'Source'}\n${source.excerpt || ''}\nDOI: ${source.doi}\n${source.section}, paragraph ${source.paragraph}\nDocument hash: ${source.document_sha256}\nExcerpt hash: ${source.excerpt_sha256}\nVerification: ${source.verification}`);
  }
  if (!(report.citation_ledger || []).length) text(at('sources'), 'p', 'No crosschecked source-text excerpts. No source-supported scientific conclusion is available.', 'muted');
  entry(at('foundation'), 'Existing v1.5 research result', {
    literature_status: report.foundation?.literature?.status,
    arxiv_status: report.foundation?.arxiv_discovery?.status,
    formal_checks: report.foundation?.calculations,
    theory_comparison: report.foundation?.theory_comparison,
  });
  for (const f of report.followups || []) entry(at('foundation'), `Follow-up ${f.id}: ${f.status}`, f);
  at('export').disabled = false;
}
async function run() {
  at('run').disabled = true; at('status').textContent = 'Research running within the selected limits…';
  try {
    const subquestions = at('subquestions').value.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    if (subquestions.length > 3) throw Error('Up to three subquestions are allowed');
    const payload = {
      question: at('question').value.trim(), subquestions,
      literature: at('literature').value, arxiv: at('arxiv').value,
      max_followups: Number(at('followups').value), provider: at('provider').value
    };
    const model = at('model').value.trim(); if (model) payload.model = model;
    const session = await fetch('/auth/session', {cache:'no-store'});
    if (session.status === 401) { window.location.assign('/login'); throw Error('Login required'); }
    if (!session.ok) throw Error('Could not validate private session');
    const csrf = (await session.json()).csrf || '';
    const headers = {'Content-Type':'application/json'};
    if (csrf) headers['X-Atlas-CSRF'] = csrf;
    const token = at('token').value.trim(); if (token) headers['X-Atlas-Token'] = token;
    const response = await fetch('/api/science/decompose', {
      method:'POST', headers, cache:'no-store', body:JSON.stringify(payload)
    });
    if (!response.ok) {
      let error = {}; try { error = await response.json(); } catch {}
      throw Error((typeof error.detail === 'string' ? error.detail : `HTTP ${response.status}`).slice(0,220));
    }
    show(await response.json()); at('status').textContent = 'Completed. Review unresolved evidence gaps and verification labels.';
  } catch (e) { at('status').textContent = `Unavailable: ${e.message}`; }
  finally { at('run').disabled = false; }
}
function save() {
  if (!current) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));
  const a = document.createElement('a'); a.href=url; a.download='atlas-research-v16.json'; a.click();
  URL.revokeObjectURL(url);
}
at('run').addEventListener('click',run);
at('export').addEventListener('click',save);
