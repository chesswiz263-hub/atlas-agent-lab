/* ATLAS public browser. No credentials, SDK keys, or remote execution in public code.
 * On GitHub Pages this is a clearly labeled local demo. Real research requires
 * authenticated SAME-ORIGIN ATLAS FastAPI routes on a separately hosted service.
 */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const STORAGE_KEY = 'atlas-public-ui-v2-chats';
  const THEME_KEY = 'atlas-public-ui-v2-theme';
  const MAX_CHATS = 24;
  const MAX_MESSAGES = 48;
  const MAX_STORED_CHARS = 180000;
  const WORKSPACES = {
    research: {name:'Research', subtitle:'Research workspace', icon:'◈', page:'decompose.html', description:'Bounded research planning, discovery and follow-up searches'},
    physics: {name:'Physics', subtitle:'Physics & engineering', icon:'⚛', page:'physics.html', description:'Formal physics checks and arXiv metadata discovery'},
    math: {name:'Mathematics', subtitle:'Mathematical workspace', icon:'∑', page:'workflow.html', description:'Symbolic calculations in the unified workflow'},
    evidence: {name:'Evidence', subtitle:'Evidence review', icon:'▤', page:'claims.html', description:'Claim-level assessment with verified passage locators'},
    quantitative: {name:'Quantitative', subtitle:'Quantitative analysis', icon:'◫', page:'quantitative.html', description:'Unit-aware measurements, uncertainties and comparisons'},
    extraction: {name:'Extraction', subtitle:'Data extraction', icon:'⌁', page:'extraction.html', description:'Find numeric expressions in checked source passages'}
  };
  const isPublicPages = location.hostname === 'github.io' || location.hostname.endsWith('.github.io');
  let connection = {mode:'demo', csrf:'', model_enabled:false, reason:isPublicPages ? 'GitHub Pages hosts the frontend only.' : 'Backend has not been verified.'};
  let chats = loadChats();
  let currentId = null;
  let workspace = 'research';
  let busy = false;
  let requestController = null;

  function safeGet(key){try{return localStorage.getItem(key);}catch{return null;}}
  function safeSet(key, value){try{localStorage.setItem(key,value);return true;}catch{return false;}}
  function loadChats() {
    try {
      const data = JSON.parse(safeGet(STORAGE_KEY) || '[]');
      if (!Array.isArray(data)) return [];
      return data.slice(0,MAX_CHATS).filter(c => c && typeof c.id === 'string' && typeof c.title === 'string' && Array.isArray(c.messages))
        .map(c => ({id:c.id.slice(0,64), title:c.title.slice(0,90), workspace:WORKSPACES[c.workspace] ? c.workspace : 'research', messages:c.messages.slice(-MAX_MESSAGES).filter(m=>m && ['user','assistant'].includes(m.role) && typeof m.text === 'string').map(m=>({role:m.role,text:m.text.slice(0,6500),tag:String(m.tag||'').slice(0,75),isDemo:Boolean(m.isDemo),presentation:m.presentation&&m.presentation.kind==='mathematics'&&JSON.stringify(m.presentation).length<26000?m.presentation:null}))}));
    } catch {return [];}
  }
  function saveChats(){
    // Reports are transient: don't silently persist scientific material/large provenance blobs.
    const value=JSON.stringify(chats.slice(0,MAX_CHATS));
    if (value.length<=MAX_STORED_CHARS) safeSet(STORAGE_KEY,value);
  }
  function makeId(){return (typeof crypto!=='undefined' && crypto.randomUUID) ? crypto.randomUUID() : 'local-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8);}
  function currentChat(){return chats.find(c=>c.id===currentId)||null;}
  function ensureChat(){
    let c=currentChat();
    if (!c){c={id:makeId(),title:'New research',workspace,messages:[]};chats.unshift(c);currentId=c.id;}
    return c;
  }
  function newChat(){
    if (busy) return;
    currentId=null; $('messages').replaceChildren(); document.body.classList.remove('has-chat'); $('prompt').value=''; $('prompt').focus(); renderHistory(); closeSidebar();
  }
  function switchWorkspace(value){
    if (!WORKSPACES[value] || busy)return;
    workspace=value; $('modeSelect').value=value; $('headerWorkspace').textContent=WORKSPACES[value].subtitle;
    document.querySelectorAll('.workspace').forEach(btn=>btn.classList.toggle('active',btn.dataset.workspace===value));
    const chat=currentChat(); if(chat && !chat.messages.length) chat.workspace=value;
    closeSidebar();
  }
  function openChat(id){
    if(busy)return;
    const c=chats.find(v=>v.id===id);if(!c)return;
    currentId=id;switchWorkspace(c.workspace);$('messages').replaceChildren();
    for(const message of c.messages) appendMessage(message.role,message.text,{tag:message.tag,isDemo:message.isDemo,presentation:message.presentation,save:false});
    renderHistory();closeSidebar();$('prompt').focus();
  }
  function renderHistory(){
    const list=$('historyList');list.replaceChildren();
    if (!chats.length){const p=document.createElement('p');p.className='history-empty';p.textContent='Your conversations live here.';list.append(p);return;}
    for(const c of chats){
      const entry=document.createElement('div');entry.className='history-entry'+(c.id===currentId?' selected':'');
      const open=document.createElement('button');open.type='button';open.className='history-open';open.textContent=c.title;open.title=c.title;open.addEventListener('click',()=>openChat(c.id));
      const del=document.createElement('button');del.type='button';del.className='delete-entry';del.textContent='×';del.title='Delete conversation';del.setAttribute('aria-label','Delete '+c.title);del.addEventListener('click',()=>{if(busy)return;chats=chats.filter(x=>x.id!==c.id);if(currentId===c.id)newChat();saveChats();renderHistory();});
      entry.append(open,del);list.append(entry);
    }
  }
  function setTheme(value){
    const theme=value==='light'?'light':'dark';document.body.dataset.theme=theme;
    $('themeLabel').textContent=theme==='dark'?'Light appearance':'Dark appearance';safeSet(THEME_KEY,theme);
  }
  function sidebarOpen(value){$('sidebar').classList.toggle('open',value);$('sidebarOverlay').hidden=!value;}
  function closeSidebar(){sidebarOpen(false);}
  function toolsOpen(value){$('toolsPanel').classList.toggle('open',value);$('toolsPanel').setAttribute('aria-hidden',String(!value));$('toolsOverlay').hidden=!value;}
  function scrollBottom(){const panel=$('main');requestAnimationFrame(()=>{panel.scrollTop=panel.scrollHeight;});}
  function span(className,text){const s=document.createElement('span');s.className=className;s.textContent=text;return s;}
  function element(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;}
  // Formula markup is rendered from SymPy-produced MathML data only.
  // Import only known MathML tags, never HTML/script/event attributes.
  const MATH_NS='http://www.w3.org/1998/Math/MathML';
  const MATH_TAGS=new Set('math mrow mi mn mo msup msub msubsup mfrac msqrt mroot munder mover munderover mtable mtr mtd mtext mstyle mspace mfenced mphantom mpadded menclose'.split(' '));
  const MATH_ATTRS=new Set('xmlns display mathvariant stretchy form separator lspace rspace open close width height depth accent accentunder minsize maxsize'.split(' '));
  function safeMathXML(mathml){
    if(typeof mathml!=='string'||!mathml||mathml.length>4200)return null;
    const source='<math xmlns="'+MATH_NS+'" display="block">'+mathml+'</math>';
    const documentXML=new DOMParser().parseFromString(source,'application/xml');
    if(documentXML.querySelector('parsererror'))return null;
    const root=documentXML.documentElement;
    for(const item of [root,...Array.from(root.getElementsByTagName('*'))]){
      if(item.namespaceURI!==MATH_NS || !MATH_TAGS.has(item.localName))return null;
      for(const attr of Array.from(item.attributes)){
        if(!MATH_ATTRS.has(attr.name)||/url\(|javascript:|data:/i.test(attr.value))return null;
      }
    }
    return document.importNode(root,true);
  }
  function renderMathExpression(parent,latex,xml,raw){
    const shell=element('div','math-formula');
    const math=safeMathXML(xml);
    if(math){shell.append(math);shell.setAttribute('aria-label',String(latex||raw||'Mathematical expression').slice(0,1000));}
    else if(latex){shell.append(element('code','math-source',latex));}
    else if(raw){shell.append(element('code','math-source',raw));}
    if(shell.hasChildNodes())parent.append(shell);
  }
  function renderMathPresentation(container,view){
    const heading=element('div','math-result-title','Result');container.append(heading);
    renderMathExpression(container,view.result_latex,view.result_mathml,view.result_raw);
    if(view.why){const lead=element('p','math-intuition',view.why);container.append(lead);}
    if(view.tutor_note){
      const tutor=element('p','math-tutor-note',view.tutor_note);container.append(tutor);
      container.append(element('small','math-ai-note','AI explanation is supplementary; symbolic mathematics remains the authority.'));
    }
    if(Array.isArray(view.steps)&&view.steps.length){
      container.append(element('h3','math-section-title','Step-by-step explanation'));
      const ol=element('ol','math-step-list');
      for(const item of view.steps.slice(0,12)){
        if(!item||typeof item!=='object')continue;
        const li=element('li','math-step');
        li.append(element('h4','math-step-title',String(item.title||'Apply the rule').slice(0,100)));
        li.append(element('p','math-step-explainer',String(item.explanation||'').slice(0,450)));
        renderMathExpression(li,item.latex,item.mathml,'');
        ol.append(li);
      }
      container.append(ol);
    }
    const check=String(view.verification||'NOT_CHECKED');
    container.append(element('div','math-verify',check==='DIFFERENTIATION_CHECKED'?'✓ Differentiation check passed':
      check.includes('CHECKED')?'Verification: '+check.replaceAll('_',' ').toLowerCase():
      'Verification status: '+check.replaceAll('_',' ').toLowerCase()));
    if(Array.isArray(view.notes))for(const note of view.notes.slice(0,4)){
      if(typeof note==='string')container.append(element('p','math-note',note.slice(0,260)));
    }
    const rawDetails=element('details','math-raw');
    rawDetails.append(element('summary','','Show raw symbolic result'));
    rawDetails.append(element('pre','',String(view.result_raw||'').slice(0,1100)));
    container.append(rawDetails);
  }
  function appendMessage(role,text,options={}){
    const msg=element('section','message '+role);if(role==='user'){
      msg.append(element('div','message-body',text));
    } else {
      const head=element('div','assistant-label');head.append(span('assistant-glyph','◈'),span('','ATLAS'));
      const answer=element('div','answer-text');
      const refs=Array.isArray(options.report?.citation_ledger)?options.report.citation_ledger:[];
      const refMap=new Map(refs.filter(x=>x&&typeof x.citation_id==='string').map(x=>[x.citation_id,x]));
      const view=options.report?.presentation || options.presentation;
      const regex=/\[([A-Za-z][A-Za-z0-9.]{1,35})\]/g;let last=0;let match;
      if(view && view.kind==='mathematics') {
        renderMathPresentation(answer,view);
      } else {
      while((match=regex.exec(text))!==null){
        answer.append(document.createTextNode(text.slice(last,match.index)));last=regex.lastIndex;
        const source=refMap.get(match[1]);const doi=String(source?.doi||'');
        const target=typeof source?.source_url==='string'&&/^https:\/\//.test(source.source_url)?source.source_url:
                     /^10\.[0-9]{4,9}\//.test(doi)?'https://doi.org/'+encodeURI(doi):'';
        if(source&&target){const link=element('a','inline-citation',match[0]);link.href=target;link.target='_blank';link.rel='noopener noreferrer';link.title='Open source '+match[1];answer.append(link);}
        else if(source){const link=element('a','inline-citation',match[0]);link.href='#atlas-source-'+match[1].replace(/[^a-zA-Z0-9-]/g,'-');link.title='See located source excerpt '+match[1];answer.append(link);}else answer.append(document.createTextNode(match[0]));
      }
      answer.append(document.createTextNode(text.slice(last)));
      }
      msg.append(head,answer);
      if(options.tag||options.isDemo){const meta=element('div','answer-meta');meta.append(span('meta-tag'+(options.isDemo?' warning':''),options.tag||'BROWSER DEMO'));msg.append(meta);}
      if(options.report) attachReport(msg,options.report);
    }
    $('messages').append(msg);document.body.classList.add('has-chat');scrollBottom();
    if(options.save!==false){const c=ensureChat();c.messages.push({role,text,tag:options.tag||'',isDemo:Boolean(options.isDemo),presentation:options.report?.presentation?.kind==='mathematics'?options.report.presentation:null});c.messages=c.messages.slice(-MAX_MESSAGES);saveChats();renderHistory();}
    return msg;
  }
  function attachReport(msg, report){
    const details=element('details','result-details');const summary=element('summary','', 'Sources, Methods & Verification');details.append(summary);
    const content=element('div','detail-content');const ledger=Array.isArray(report.citation_ledger)?report.citation_ledger:Array.isArray(report.source_index)?report.source_index:[];
    if(ledger.length){content.append(element('p','',`${ledger.length} located source-text record(s). Passage identity is not scientific claim verification.`));const list=element('div','source-list');
      for(const rec of ledger.slice(0,12)){
        if(!rec||typeof rec!=='object')continue;
        const item=element('div','source-card');const label=String(rec.citation_id||rec.id||'Source locator').slice(0,50);item.id='atlas-source-'+label.replace(/[^a-zA-Z0-9-]/g,'-');
        item.append(element('strong','',label));
        if(typeof rec.excerpt==='string')item.append(element('p','',rec.excerpt.slice(0,350)));
        if(typeof rec.text==='string'&&!rec.excerpt)item.append(element('p','',rec.text.slice(0,350)));
        const doi=String(rec.doi||'').trim();
        if(/^(10\.[0-9]{4,9}\/[a-zA-Z0-9._;()/:+-]+)$/.test(doi)){
          const a=element('a','','DOI: '+doi);a.href='https://doi.org/'+encodeURI(doi);a.target='_blank';a.rel='noopener noreferrer';item.append(a);
        }
        list.append(item);
      }
      content.append(list);
    }
    const diag=report.research_diagnostics;
    if(diag && Array.isArray(diag.categories_requested)){
      const covered=Array.isArray(diag.categories_covered)?diag.categories_covered:[];
      const missing=Array.isArray(diag.categories_missing)?diag.categories_missing:[];
      content.append(element('p','', 'Evidence categories: '+covered.length+'/'+diag.categories_requested.length+' located in source text. Missing: '+(missing.join(', ')||'none')+'.'));
    }
    const checks=report.claim_validation;
    if(checks && typeof checks.accepted_claims==='number'){
      content.append(element('p','', 'Claim textual-support screen: '+checks.accepted_claims+' accepted; '+checks.rejected_claims+' rejected. This is not scientific entailment verification.'));
      if(Array.isArray(checks.checks)){
        const ul=element('ul','claim-audit-list');
        for(const check of checks.checks.slice(0,10)){
          ul.append(element('li','', 'Claim '+String(check.index||'?')+': '+String(check.status||'')+' ('+String(check.reason||'')+')'));
        }
        content.append(ul);
      }
    }
    content.append(element('p','', 'The raw report is included for audit. It is not independently proof-checked by this browser.'));
    const pre=element('pre','report-json',JSON.stringify(report,null,2).slice(0,65000));content.append(pre);
    const dl=element('button','secondary-button','Download JSON report');dl.type='button';dl.addEventListener('click',()=>{
      const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=url;a.download='atlas-research-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
    });content.append(dl);details.append(content);msg.append(details);
  }
  function loading(){const msg=element('section','message assistant loading-message');const label=element('div','assistant-label');label.append(span('assistant-glyph','◈'),span('','ATLAS'));
    const content=element('div','answer-text');const pulse=element('span','loading-pulse');for(let i=0;i<3;i++)pulse.append(element('i'));
    content.append(pulse,document.createTextNode('Examining your request…'));msg.append(label,content);$('messages').append(msg);scrollBottom();return msg;
  }
  function plainAnswer(question,mode){
    const q=question.trim().replace(/[?!.]$/,'').trim();
    const match=q.match(/^(?:what is\s+|calculate\s+|compute\s+)?([+-]?\d+(?:\.\d+)?)\s*([+\-*/×÷])\s*([+-]?\d+(?:\.\d+)?)$/i);
    if(match){const a=Number(match[1]),b=Number(match[3]),op=match[2];const value=op==='+'?a+b:op==='-'?a-b:op==='*'||op==='×'?a*b:b===0?NaN:a/b;
      return Number.isFinite(value)?{text:`${match[1]} ${op} ${match[3]} = ${value.toLocaleString('en-US',{maximumSignificantDigits:14})}\n\nCalculated locally in your browser. No scientific sources or AI model were involved.`,tag:'LOCAL CALCULATION'}:{text:'This expression has no finite real-number result under the local arithmetic demo.',tag:'LOCAL CALCULATION'};
    }
    if(/(safeguards|reliable).*(agents|ai)|(?:agents|ai).*(safeguards|reliable)/i.test(q)){
      return {text:'Sample ATLAS knowledge excerpt:\n\n“Production-grade tool-using agents need three baseline safeguards: explicit tool allowlists, enforced step and cost budgets, and end-to-end traces of model decisions and tool results.”\n\nSource: bundled examples/knowledge/agent_reliability_playbook.md (demonstration corpus only). This browser has not performed an external literature search or independently verified the claim.',tag:'BUNDLED SAMPLE · NOT EXTERNAL VERIFICATION'};
    }
    if(/^(what can atlas do|what is atlas|help|features)\b/i.test(q)){
      return {text:'ATLAS combines a model-agnostic agent runtime with research workflows for publication discovery, bounded evidence searches, symbolic mathematics, physics calculations, claim assessment, quantitative comparisons, and source-anchored data extraction.\n\nThis public preview displays the chat interface and limited deterministic examples. Live research requires the authenticated Python backend. From the Tools panel, connected installations expose the specialist workspaces.',tag:'PRODUCT GUIDE · BROWSER DEMO'};
    }
    const specialty=WORKSPACES[mode]?.name||'Research';
    return {text:`This is the ATLAS public browser preview, not a live scientific answer.\n\nYour question has been added to the ${specialty} workspace. A connected ATLAS backend would run the permitted research tools, collect evidence and calculations, then return a report with explicit verification labels.\n\nGitHub Pages cannot execute the Python research engine. Until a separately hosted and authenticated backend is available, I won't invent literature, citations, or a model-generated answer.\n\nTry “What safeguards make AI agents reliable?” for a bundled example, or “Calculate 25 * 16” for browser-only arithmetic.`,tag:'OFFLINE PREVIEW · NO LIVE RESEARCH'};
  }
  async function checkBackend(){
    if(isPublicPages){connection={mode:'demo',csrf:'',reason:'GitHub Pages cannot run the Python backend.'};updateConnection();return;}
    const abort=new AbortController();const id=setTimeout(()=>abort.abort(),3500);
    try{
      const r=await fetch('/auth/session',{credentials:'same-origin',cache:'no-store',signal:abort.signal});
      if(r.ok){const obj=await r.json();connection={mode:'live',csrf:typeof obj.csrf==='string'?obj.csrf:'',model_enabled:obj.model_enabled===true,reason:'Authenticated ATLAS research server is connected.'};}
      else if(r.status===401||r.status===403)connection={mode:'login',csrf:'',reason:'ATLAS backend found, but login is required.'};
      else connection={mode:'demo',csrf:'',reason:'No compatible authenticated ATLAS backend detected.'};
    }catch{connection={mode:'demo',csrf:'',reason:'No compatible ATLAS backend detected on this origin.'};}
    finally{clearTimeout(id);updateConnection();}
  }
  function updateConnection(){
    const status=$('connectionLabel'),dot=$('statusDot');dot.className='status-dot '+(connection.mode==='live'?'live':'demo');
    status.textContent=connection.mode==='live'?'Engine connected':connection.mode==='login'?'Sign in required':'Browser demo';
    $('engineStatus').textContent=connection.reason+' Model synthesis: '+(connection.model_enabled?'configured for source-backed requests':'off or not fully configured (math and evidence research available)')+'.';
    renderTools();
  }
  function renderTools(){
    const el=$('toolLinks');el.replaceChildren();
    for(const [id,obj] of Object.entries(WORKSPACES)){
      const isLive=connection.mode==='live';const link=document.createElement(isLive?'a':'div');link.className='tool-link'+(isLive?'':' disabled');
      if(isLive){link.href='/static/'+obj.page;link.title='Open '+obj.name+' structured workspace';}
      else {link.title='Available after connecting to the authenticated backend';}
      link.append(span('',obj.icon));const body=element('div');body.append(element('strong','',obj.name),element('small','',obj.description));link.append(body,span('tool-arrow',isLive?'↗':'◌'));el.append(link);
    }
  }
  function getRequest(mode, question){
    const chat=currentChat();
    // Limit prior messages; current question has already been inserted into chat.
    const preceding=(chat?.messages||[]).slice(0,-1).slice(-4).map(m=>({role:m.role,text:m.text.slice(0,650)}));
    return {url:'/api/atlas/chat',body:{question,workspace:mode,history:preceding}};
  }
  async function realResearch(question,mode){
    if(connection.mode!=='live')throw new Error('Research backend not connected');
    const request=getRequest(mode,question);
    requestController=new AbortController();
    const headers={'Content-Type':'application/json'};if(connection.csrf)headers['X-Atlas-CSRF']=connection.csrf;
    const response=await fetch(request.url,{method:'POST',headers,body:JSON.stringify(request.body),credentials:'same-origin',cache:'no-store',signal:requestController.signal});
    if(response.status===401||response.status===403){connection={mode:'login',csrf:'',reason:'Session expired or access denied.'};updateConnection();throw new Error('Login required or access denied. Visit /login on your private backend.');}
    if(!response.ok){let detail='Request failed (HTTP '+response.status+')';try{const j=await response.json();if(typeof j.detail==='string')detail=j.detail.slice(0,250);}catch{}throw new Error(detail);}
    const report=await response.json();if(!report||typeof report!=='object'||typeof report.answer!=='string')throw new Error('Unexpected response from research backend');
    return report;
  }
  async function send(){
    if(busy)return;
    const prompt=$('prompt').value.trim();if(!prompt)return;
    const mode=workspace;
    if(prompt.length>500&&connection.mode==='live'){
      appendMessage('assistant','The connected research API permits at most 500 characters per question. Please shorten the question or use the specialized workspace.',{tag:'REQUEST LIMIT'});return;
    }
    busy=true;$('send').disabled=true;$('newChat').disabled=true;$('prompt').value='';
    const c=ensureChat();if(c.messages.length===0){c.title=prompt.length>51?prompt.slice(0,50)+'…':prompt;c.workspace=mode;}
    appendMessage('user',prompt);const pending=loading();
    try{
      if(connection.mode==='live'){
        const report=await realResearch(prompt,mode);pending.remove();
        const result=appendMessage('assistant',report.answer,{tag:(report.answer_status||'BOUNDED RESEARCH REPORT').replace(/_/g,' ').slice(0,80),report});
        if(mode==='quantitative'||mode==='extraction'||mode==='evidence'){
          const note=element('p','', 'For structured '+WORKSPACES[mode].name.toLowerCase()+' tasks, use the specialized workspace in Tools.');
          result.append(note);
        }
      } else {
        // Do not simulate a model response when Pages has no actual backend.
        const demo=plainAnswer(prompt,mode);pending.remove();appendMessage('assistant',demo.text,{tag:demo.tag,isDemo:true});
      }
    }catch(error){pending.remove();appendMessage('assistant','ATLAS could not complete this request: '+(error?.name==='AbortError'?'Request canceled.':String(error?.message||'Unknown error').slice(0,270))+'\n\nNo scientific claim or citation was verified in this attempt.',{tag:'RESEARCH UNAVAILABLE'});}
    finally{busy=false;requestController=null;$('send').disabled=false;$('newChat').disabled=false;$('prompt').focus();renderHistory();}
  }
  // Bind controls
  $('newChat').addEventListener('click',newChat);
  $('send').addEventListener('click',send);
  $('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}});
  $('prompt').addEventListener('input',()=>{const t=$('prompt');t.style.height='auto';t.style.height=Math.min(180,Math.max(58,t.scrollHeight))+'px';});
  $('modeSelect').addEventListener('change',e=>switchWorkspace(e.target.value));
  document.querySelectorAll('.workspace').forEach(btn=>btn.addEventListener('click',()=>switchWorkspace(btn.dataset.workspace)));
  document.querySelectorAll('.suggestion').forEach(btn=>btn.addEventListener('click',()=>{const prompt=btn.dataset.prompt||'';$('prompt').value=prompt;$('prompt').focus();}));
  $('themeToggle').addEventListener('click',()=>setTheme(document.body.dataset.theme==='dark'?'light':'dark'));
  $('openSidebar').addEventListener('click',()=>sidebarOpen(true));$('closeSidebar').addEventListener('click',closeSidebar);$('sidebarOverlay').addEventListener('click',closeSidebar);
  $('toolsButton').addEventListener('click',()=>toolsOpen(true));$('connectionButton').addEventListener('click',()=>toolsOpen(true));$('closeTools').addEventListener('click',()=>toolsOpen(false));$('toolsOverlay').addEventListener('click',()=>toolsOpen(false));
  $('retryConnection').addEventListener('click',checkBackend);
  $('clearHistory').addEventListener('click',()=>{if(busy)return;if(chats.length&&!window.confirm('Delete all conversations saved in this browser?'))return;chats=[];saveChats();newChat();});
  window.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();newChat();}if(e.key==='Escape'){closeSidebar();toolsOpen(false);}});
  setTheme(safeGet(THEME_KEY)||'dark');switchWorkspace('research');renderHistory();renderTools();checkBackend();
})();
