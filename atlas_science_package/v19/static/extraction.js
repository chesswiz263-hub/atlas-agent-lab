/* ATLAS v1.9 source-anchored numeric extraction. Display untrusted text via textContent only. */
'use strict';
const $ = id => document.getElementById(id);
let report = null;
const make = (el,tag,value,cls) => {const item=document.createElement(tag); if(value!==undefined)item.textContent=String(value);if(cls)item.className=cls;el.append(item);return item;};
function card(root,heading,body){const div=make(root,'article',undefined,'paper');make(div,'h3',heading);const pre=make(div,'pre',body,'meta');pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';}
function selectionLabel(c){return `${c.candidate_id.slice(0,10)} · ${c.literal} · ${c.doi} · ${c.section} ¶${c.paragraph}`;}
function populate(data){report=data;$('candidates').replaceChildren();$('comparison').replaceChildren();
  const candidates=data.candidates||[];
  for(const c of candidates){card($('candidates'),`${c.literal} — ${c.candidate_id.slice(0,12)}`,
    `${c.title||'Untitled'}\nDOI: ${c.doi}\nCitation: ${c.citation_id}\nSection: ${c.section} ¶${c.paragraph}\n`+
    `Printed uncertainty: ${c.printed_uncertainty??'none'} (not interpreted)\nSource excerpt: ${c.excerpt}\n`+
    `Exact span: ${c.excerpt_offset[0]}–${c.excerpt_offset[1]}\nExcerpt SHA-256: ${c.excerpt_sha256}\n`+
    `Role: NOT VERIFIED; text cues: ${(c.textual_cues||[]).join(', ')}`);}
  if(!candidates.length)make($('candidates'),'p','No eligible number–unit mentions found in verified primary-text excerpts.','muted');
  for(const id of ['prediction','measurement']){const node=$(id);node.replaceChildren();
    for(const c of candidates){const opt=make(node,'option',selectionLabel(c));opt.value=c.candidate_id;}}
  if(candidates.length>1)$('measurement').selectedIndex=1;
  $('compare').disabled=candidates.length<2;$('export').disabled=false;
  card($('comparison'),'Source status',`${data.source_status}\n${(data.limitations||[]).join('\n')}`);
}
function payload(){const question=$('question').value.trim();if(question.length<15)throw Error('Enter a research question of at least 15 characters');
  const limit=Number($('limit').value);if(!Number.isInteger(limit)||limit<1||limit>24)throw Error('Maximum mentions must be between 1 and 24');
  return {research_question:question,max_candidates:limit};}
async function callAPI(body){const session=await fetch('/auth/session',{cache:'no-store'});
  if(session.status===401){location.assign('/login');throw Error('Login required');}
  if(!session.ok)throw Error('Authentication unavailable');
  const csrf=(await session.json()).csrf||'';const headers={'Content-Type':'application/json'};
  if(csrf)headers['X-Atlas-CSRF']=csrf;const token=$('token').value.trim();if(token)headers['X-Atlas-Token']=token;
  const response=await fetch('/api/science/extract',{method:'POST',headers,cache:'no-store',body:JSON.stringify(body)});
  if(!response.ok){let error={};try{error=await response.json();}catch{};
    throw Error((typeof error.detail==='string'?error.detail:`HTTP ${response.status}`).slice(0,220));}
  return response.json();}
async function discover(){const button=$('discover');button.disabled=true;$('status').textContent='Searching bounded primary-text sources…';
  try{const answer=await callAPI(payload());populate(answer);$('status').textContent=`Located ${answer.candidates.length} source-anchored numeric mention(s). Scientific roles remain unverified.`;
  }catch(error){$('status').textContent=`Unavailable: ${error.message}`;}finally{button.disabled=false;}}
async function compare(){const button=$('compare');button.disabled=true;$('status').textContent='Rechecking sources and performing reviewed arithmetic…';
  try{if(!$('review').checked)throw Error('Review the original excerpts and confirm their context first');
    const type=$('uncertainty').value;
    if(type!=='none'&&!$('sigma').checked)throw Error('Confirm the printed uncertainties are Gaussian 1σ before statistical analysis');
    const entry={case_id:'Q1',label:$('label').value.trim(),prediction_candidate_id:$('prediction').value,
      measurement_candidate_id:$('measurement').value,observable:$('observable').value.trim(),conditions:$('conditions').value.trim(),
      user_confirms_roles_and_context:true,uncertainty_model:type,user_confirms_uncertainties_gaussian_1sigma:$('sigma').checked};
    if(type==='correlation_supplied_gaussian_1sigma')entry.correlation=$('correlation').value.trim();
    const body=payload();body.comparisons=[entry];const answer=await callAPI(body);
    populate(answer);$('comparison').replaceChildren();for(const item of answer.comparisons||[]){card($('comparison'),`${item.case_id} · ${item.status}`,
      JSON.stringify(item,null,2));}
    $('status').textContent='Comparison finished. Check the re-fetched source status and limitations.';
  }catch(error){$('status').textContent=`Unavailable: ${error.message}`;}finally{$('compare').disabled=!(report&&report.candidates&&report.candidates.length>=2);}}
function download(){if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='atlas-extraction-v19.json';a.click();URL.revokeObjectURL(url);}
$('discover').addEventListener('click',discover);$('compare').addEventListener('click',compare);$('export').addEventListener('click',download);
