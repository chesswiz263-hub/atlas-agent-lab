/* ATLAS science research workspace. Every untrusted value is inserted as text, not HTML. */
'use strict';
const el = id => document.getElementById(id);
let dossier = null;
let csrf = '';
function node(tag, text, className) { const x=document.createElement(tag); if (className) x.className=className; x.textContent=String(text ?? ''); return x; }
function add(target, tag, text, className) { const x=node(tag,text,className);target.appendChild(x);return x; }
async function session() {
  const r = await fetch('/auth/session', {cache:'no-store'});
  if (r.status === 401) { location.assign('/login'); throw new Error('Login required'); }
  if (!r.ok) throw new Error('Unable to validate ATLAS session');
  csrf = (await r.json()).csrf || '';
}
function showPaper(item) {
  const box=add(el('papers'),'article','','paper');
  add(box,'h3',`[${item.id}] ${item.title}`);
  add(box,'div',`${item.authors.join(', ') || 'Authors unknown'} · ${item.year || 'Unknown year'} · ${item.venue || 'Venue unknown'}`,'meta');
  const status=item.verification?.status || 'NOT_CHECKED';
  add(box,'span',status,'pill');
  if (item.verification?.update_notice_present) add(box,'span','POST-PUBLICATION UPDATE NOTICE','pill');
  if (item.doi_url) { const a=add(box,'a',item.doi_url); a.href=item.doi_url;a.target='_blank';a.rel='noopener noreferrer'; }
  add(box,'p',item.abstract || 'No indexed abstract available.');
  add(box,'p','Abstract is from OpenAlex indexed metadata, not checked against primary text.');
  const primary=item.primary_source || {};
  add(box,'div',`Repository full text: ${primary.status || 'NOT_ATTEMPTED'}`,'meta');
  if(primary.source_url){const a=add(box,'a','Open repository record ↗');a.href=primary.source_url;a.target='_blank';a.rel='noopener noreferrer';}
  if(primary.document_sha256) add(box,'div',`XML SHA256: ${primary.document_sha256}`,'meta');
  if(primary.license) add(box,'div',`License (as deposited): ${primary.license}`,'meta');
  for(const span of item.primary_passages || []) {
    const p=add(box,'div','','source-span');
    add(p,'strong',`[${span.citation_id}] ${span.section} · paragraph ${span.paragraph}`);
    add(p,'p',span.excerpt);
    add(p,'span','Exact repository excerpt; scientific interpretation NOT checked.','meta');
  }
}
function render(out) {
  dossier=out;
  el('answer').replaceChildren();
  add(el('answer'),'p',out.answer || 'No answer returned');
  add(el('answer'),'p',`Synthesis status: ${out.answer_status} · Discovery status: ${out.status}`,'muted');
  el('papers').replaceChildren();
  if (!out.papers.length) add(el('papers'),'p','No indexed papers found.','muted');
  for (const paper of out.papers) showPaper(paper);
  el('comparisons').replaceChildren();
  for (const h of out.hypothesis_comparison) {
    const b=add(el('comparisons'),'article','','paper');
    add(b,'h3',`${h.name} — ${h.status}`);
    add(b,'p',`Named in paper IDs: ${h.papers_mentioning_label.join(', ') || 'none'}. ${h.interpretation}`);
  }
  for(const q of out.quote_verifications || []) {
    const b=add(el('comparisons'),'article','','paper');
    add(b,'h3',`Literal quote check — ${q.status}`);
    add(b,'p',`DOI ${q.doi}${q.section ? ' · '+q.section+' / paragraph '+q.paragraph : ''}`);
    if(q.matched_excerpt) add(b,'p',q.matched_excerpt);
    add(b,'p','Matching literal text is not equivalent to validating a scientific claim.','meta');
  }
  for (const m of out.math_checks) {
    const b=add(el('comparisons'),'article','','paper');
    add(b,'h3',`∑ ${m.expression} — ${m.status}`);
    add(b,'p',m.result || m.difference || m.reason || 'Check completed');
    add(b,'p',m.scope,'muted');
  }
  if (!out.hypothesis_comparison.length && !out.math_checks.length) add(el('comparisons'),'p','No hypothesis or symbolic checks requested.','muted');
  el('export').disabled=false;
}
async function run() {
  const runButton=el('run');runButton.disabled=true;el('status').textContent='Searching publications and checking DOI metadata…';
  try {
    await session();
    const expression=el('math').value.trim();
    const payload={question:el('question').value.trim(),provider:el('provider').value,
      hypotheses:el('hypotheses').value.split(',').map(x=>x.trim()).filter(Boolean).slice(0,5),
      math_tasks:expression?[{expression,operation:el('mathOperation').value,variable:el('variable').value.trim() || 'x'}]:[]};
    payload.include_primary=el('includePrimary').checked;
    const doi=el('quoteDoi').value.trim(), exact=el('quoteText').value.trim();
    if(doi || exact){if(!doi || !exact)throw new Error('Supply both a DOI and quotation to verify text.');
      payload.quote_candidates=[{doi,quote:exact}];}
    if(el('model').value.trim()) payload.model=el('model').value.trim();
    const headers={'Content-Type':'application/json'};
    if(csrf) headers['X-Atlas-CSRF']=csrf;
    if(el('token').value.trim()) headers['X-Atlas-Token']=el('token').value.trim();
    const r=await fetch('/api/science/ask',{method:'POST',headers,body:JSON.stringify(payload),cache:'no-store'});
    if(r.status===401){const msg='Authentication required. Sign in or supply your operator API token.'; throw new Error(msg);}
    if(!r.ok){let d={};try{d=await r.json();}catch{}throw new Error((typeof d.detail==='string'?d.detail:`API HTTP ${r.status}`).slice(0,200));}
    render(await r.json());el('status').textContent='Completed. Check evidence and scope labels carefully.';
  }catch(e){el('status').textContent=`Research unavailable: ${e.message}`;}finally{runButton.disabled=false;}
}
function exportDossier(){if(!dossier)return;const blob=new Blob([JSON.stringify(dossier,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='atlas-science-dossier.json';a.click();URL.revokeObjectURL(url);}
el('run').addEventListener('click',run);
el('export').addEventListener('click',exportDossier);
