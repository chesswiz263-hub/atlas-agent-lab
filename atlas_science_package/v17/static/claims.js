/* ATLAS v1.7. No research result inserted as HTML; data rendered as text. */
'use strict';
const $ = id => document.getElementById(id);
let lastReport = null;
function write(parent, tag, value, className) {
  const el = document.createElement(tag);
  el.textContent = String(value ?? '');
  if (className) el.className = className;
  parent.appendChild(el); return el;
}
function panel(parent, title, body) {
  const el = write(parent, 'article', '', 'paper');
  write(el,'h3',title);
  const content = write(el, 'pre', typeof body==='string' ? body : JSON.stringify(body,null,2), 'meta');
  content.style.whiteSpace = 'pre-wrap'; content.style.overflowWrap = 'anywhere';
}
function show(r) {
  lastReport = r;
  ['summary','matrix','modelResults','ledger','trace'].forEach(id => $(id).replaceChildren());
  panel($('summary'),r.claim_assessment_status || 'Pending human review',
        `Question: ${r.question || ''}\nSources: ${r.source_count ?? 0}\nReport SHA-256: ${r.report_sha256 || 'N/A'}`);
  for (const limitation of r.limitations || []) write($('summary'),'p',`• ${limitation}`,'muted');
  if (!(r.claims||[]).length) write($('matrix'),'p','No explicit scientific claims were supplied. ATLAS did not invent any.','muted');
  for (const c of r.claims || []) {
    const container=write($('matrix'),'article','','paper');
    write(container,'h3',`${c.claim_id} · ${c.status}`);
    write(container,'p',c.claim);
    for (const e of c.evidence || []) panel(container,
      `${e.citation_id} · NOT scientifically verified`,
      `Source: ${e.source_excerpt}\nTextual cues: ${(e.textual_role_signals||[]).join(', ')}\nMatched terms: ${(e.matched_terms||[]).join(', ')}\nStatus: ${e.relation_to_claim}`);
  }
  panel($('modelResults'),r.model_suggestions?.status || 'NOT_REQUESTED', r.model_suggestions?.proposals || []);
  for (const s of r.citation_ledger || []) panel($('ledger'),s.citation_id,
    `${s.title || 'Publication'}\n${s.excerpt}\nDOI: ${s.doi}\nSection: ${s.section}, paragraph: ${s.paragraph}\nDocument SHA-256: ${s.document_sha256}\nExcerpt SHA-256: ${s.excerpt_sha256}`);
  if (!(r.citation_ledger||[]).length) write($('ledger'),'p','No independently crosschecked source-text excerpts.','muted');
  panel($('trace'),'Budgets',r.budgets || {});
  for (const step of r.execution_trace || []) panel($('trace'),step.stage || 'Step',step);
  $('export').disabled = false;
}
async function run() {
  $('run').disabled=true; $('status').textContent='Research and claim audit running within limits…';
  try {
    const claims = $('claims').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    const subquestions = $('subquestions').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    if (claims.length>4 || subquestions.length>3) throw Error('Maximum: four claims and three subquestions');
    const payload = {
      question:$('question').value.trim(), claims, subquestions,
      literature:$('literature').value,arxiv:$('arxiv').value,
      max_followups:Number($('followups').value), max_evidence_per_claim:Number($('maxevidence').value),
      assessment_mode:$('mode').value,provider:$('provider').value,
    };
    const model=$('model').value.trim(); if (model) payload.model=model;
    const session=await fetch('/auth/session',{cache:'no-store'});
    if(session.status===401){location.assign('/login');throw Error('Login required');}
    if(!session.ok)throw Error('Could not authenticate private session');
    const csrf=(await session.json()).csrf||'';
    const headers={'Content-Type':'application/json'};
    if(csrf)headers['X-Atlas-CSRF']=csrf;
    const token=$('token').value.trim(); if(token)headers['X-Atlas-Token']=token;
    const response=await fetch('/api/science/claims',{method:'POST',headers,cache:'no-store',body:JSON.stringify(payload)});
    if(!response.ok){let err={};try{err=await response.json();}catch{};
      throw Error((typeof err.detail==='string'?err.detail:`HTTP ${response.status}`).slice(0,220));}
    show(await response.json());$('status').textContent='Completed. All support/challenge suggestions remain unverified.';
  }catch(e){$('status').textContent=`Unavailable: ${e.message}`;}
  finally{$('run').disabled=false;}
}
function exportJSON(){
  if(!lastReport)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='atlas-research-v17-claims.json';a.click();
  URL.revokeObjectURL(url);
}
$('run').addEventListener('click',run);
$('export').addEventListener('click',exportJSON);
