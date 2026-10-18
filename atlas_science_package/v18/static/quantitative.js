/* ATLAS v1.8 quantitative workspace: no untrusted source text inserted as HTML. */
'use strict';
const $=id=>document.getElementById(id);
let report=null; let count=0;
const UNITS=['1','%','m','mm','cm','km','AU','pc','kpc','Mpc','s','ms','min','h','yr','Myr','Gyr','kg','g','N','J','eV','keV','MeV','Pa','kPa','MPa','Hz','kHz','K','m/s','cm/s','km/s','m/s^2','cm/s^2','km/s^2','W'];
const make=(root,tag,contents,cls)=>{const el=document.createElement(tag); if(contents!==undefined)el.textContent=String(contents);if(cls)el.className=cls;root.append(el);return el};
function input(el,key,label,val,type='text'){
  const box=make(el,'div'); const l=make(box,'label',label); l.htmlFor=`${el.dataset.id}-${key}`;
  const inp=make(box,'input'); inp.id=l.htmlFor;inp.dataset.key=key; inp.type=type;inp.value=val;
  if(type==='number'){inp.step='any';inp.inputMode='decimal';}
  return inp;
}
function select(el,key,label,opts,val){const box=make(el,'div');const l=make(box,'label',label);
  const inp=make(box,'select');inp.dataset.key=key;
  for(const option of opts){const o=make(inp,'option',option);o.value=option;}
  inp.value=val; l.htmlFor=`${el.dataset.id}-${key}`;inp.id=l.htmlFor;return inp;
}
function quantity(el,side,defaults){const section=make(el,'div');section.dataset.id=`${el.dataset.id}-${side}`;
  make(section,'h3',side==='prediction'?'Prediction':'Measurement');
  input(section,'observable','Observable',defaults.observable);
  input(section,'conditions','Experimental conditions',defaults.conditions);
  input(section,'value','Value',defaults.value,'number');
  select(section,'unit','Unit',UNITS,defaults.unit);
  input(section,'standard_uncertainty','Standard uncertainty (1σ; optional)',defaults.standard_uncertainty,'number');
  section.dataset.side=side;
}
function addCase(){if(count>=6)return;count++;
  const id=`Q${count}`;const card=make($('cases'),'article',undefined,'paper');card.dataset.caseId=id;card.dataset.id=id;
  make(card,'h3',`${id} · Prediction against measurement`);
  input(card,'label','Case label',count===1?'Galaxy orbital speed':'Comparison '+count);
  const area=make(card,'div',undefined,'twocol');area.dataset.id=id;
  const example={observable:'orbital speed',conditions:'galaxy radius 10 kpc',value:'220',unit:'km/s',standard_uncertainty:'10'};
  quantity(area,'prediction',example);quantity(area,'measurement',{...example,value:'215',standard_uncertainty:'8'});
  select(card,'uncertainty_model','Uncertainty assumption',['none','independent_gaussian_1sigma','correlation_supplied_gaussian_1sigma'],'none');
  input(card,'correlation','Correlation ρ (only when supplied Gaussian model)','', 'number');
  $('add').disabled=count>=6;
}
function getValue(el,key){return el.querySelector(`[data-key="${key}"]`).value.trim()}
function readQuantity(side){const q={observable:getValue(side,'observable'),conditions:getValue(side,'conditions'),
  value:getValue(side,'value'),unit:getValue(side,'unit')};
  const u=getValue(side,'standard_uncertainty');if(u!=='')q.standard_uncertainty=u;
  return q;
}
function buildPayload(){const comparisons=[];
  for(const card of $('cases').children){const parts=card.querySelectorAll('[data-side]');
    const model=getValue(card,'uncertainty_model');const c={case_id:card.dataset.caseId,
      label:getValue(card,'label'),prediction:readQuantity(parts[0]),measurement:readQuantity(parts[1]),uncertainty_model:model};
    if(model==='correlation_supplied_gaussian_1sigma'){c.correlation=getValue(card,'correlation');}
    comparisons.push(c);
  }
  const obj={comparisons};const q=$('research').value.trim();if(q)obj.research_question=q;
  const checks=$('quotes').value.trim();if(checks){obj.source_checks=JSON.parse(checks);
    if(!Array.isArray(obj.source_checks))throw Error('Quote checks must be a JSON array');}
  return obj;
}
function panel(root,heading,text){const el=make(root,'article',undefined,'paper');make(el,'h3',heading);
  const pre=make(el,'pre',typeof text==='string'?text:JSON.stringify(text,null,2),'meta');
  pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';
}
function show(data){report=data;for(const id of ['results','sources','audit'])$(id).replaceChildren();
  for(const c of data.cases||[]){const math=c.calculation||{};panel($('results'),`${c.case_id} · ${c.calculation_status}`,
    `${c.label}\nMeasurement – prediction: ${math.measurement_minus_prediction_si??'not computed'} ${math.canonical_unit||''}\n`+
    `Combined 1σ: ${math.combined_standard_uncertainty_si??'not computed'}\nStandardized residual: ${math.standardized_residual??'not computed'}\n`+
    `Scientific validity: ${c.scientific_validity}\n${(c.limitations||[]).join('\n')}`);}
  const source=data.source_audit||{};panel($('audit'),source.status||'NOT_REQUESTED',
    `Quotes: ${JSON.stringify(source.quotes||[],null,2)}\nBudgets: ${JSON.stringify(source.budgets||{},null,2)}\nTrace: ${JSON.stringify(source.execution_trace||[],null,2)}`);
  for(const p of source.citation_ledger||[]){panel($('sources'),p.citation_id,
    `${p.title||'Publication'}\nDOI: ${p.doi}\n${p.excerpt}\nSection ${p.section}, paragraph ${p.paragraph}\nSHA-256: ${p.excerpt_sha256}`);}
  if(!(source.citation_ledger||[]).length)make($('sources'),'p','No crosschecked primary-source excerpts located.','muted');
  for(const l of data.limitations||[])make($('results'),'p',`• ${l}`,'muted');
  $('export').disabled=false;
}
async function run(){const button=$('run');button.disabled=true;$('status').textContent='Checking numerical inputs and optional bounded evidence…';
  try{const payload=buildPayload();const session=await fetch('/auth/session',{cache:'no-store'});
    if(session.status===401){location.assign('/login');throw Error('Login required');}
    if(!session.ok)throw Error('Could not authenticate session');
    const csrf=(await session.json()).csrf||'';const headers={'Content-Type':'application/json'};
    if(csrf)headers['X-Atlas-CSRF']=csrf;
    const token=$('token').value.trim();if(token)headers['X-Atlas-Token']=token;
    const response=await fetch('/api/science/quantitative',{method:'POST',headers,cache:'no-store',body:JSON.stringify(payload)});
    if(!response.ok){let err={};try{err=await response.json();}catch{};
      throw Error((typeof err.detail==='string'?err.detail:`HTTP ${response.status}`).slice(0,240));}
    show(await response.json());$('status').textContent='Calculation complete. No scientific truth verdicts were issued.';
  }catch(err){$('status').textContent=`Unavailable: ${err.message}`;}finally{button.disabled=false;}}
function exportJSON(){if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='atlas-quantitative-v18.json';a.click();URL.revokeObjectURL(url);}
$('add').addEventListener('click',addCase);$('run').addEventListener('click',run);$('export').addEventListener('click',exportJSON);
addCase();
