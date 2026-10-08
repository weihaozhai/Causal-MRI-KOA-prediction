'use strict';
let token='', lastResult=null, inputVersion=0, loading=false;
const $=id=>document.getElementById(id);
const panels=[...document.querySelectorAll('.viewport')];
const volumes=new Map();
const configReady=fetch('/api/config').then(r=>r.json()).then(c=>{token=c.token;});
async function api(path,options={}){
  await configReady;
  const r=await fetch(path,{...options,headers:{'X-Local-Token':token,...options.headers}});
  if(!r.ok){let error='Operation failed';try{error=(await r.json()).error||error;}catch{}throw new Error(error);}
  return r;
}
function status(id,text,error=false){$(id).textContent=text;$(id).classList.toggle('error',error);}
document.querySelectorAll('.grades').forEach(block=>{
  for(let i=0;i<4;i++){const label=document.createElement('label'),input=document.createElement('input'),span=document.createElement('span');
    input.type='radio';input.name=block.dataset.feature;input.value=i;input.required=true;span.textContent=i;
    label.append(input,span);block.append(label);}
});
function invalidateResult(){inputVersion++;lastResult=null;$('result-content').hidden=true;$('empty-results').hidden=false;$('download').disabled=true;status('form-status','');}
$('prediction-form').addEventListener('input',invalidateResult);
function applyZoom(panel){
  const z=Number(panel.querySelector('.panel-zoom').value),screen=panel.querySelector('.screen'),img=panel.querySelector('img');
  screen.classList.toggle('zoomed',z>1);img.style.width=z>1?(z*100)+'%':'';img.style.height='';
}
async function render(panel){
  const meta=volumes.get(panel.querySelector('.sequence-select').value);
  if(!meta)return;
  const version=panel._version=(panel._version||0)+1,slider=panel.querySelector('input[type=range]');
  const width=Number(panel.querySelector('.panel-width').value),level=Number(panel.querySelector('.panel-level').value);
  if(!(width>0)||!Number.isFinite(level))return;
  panel.querySelector('output').textContent=(Number(slider.value)+1)+'/'+(Number(slider.max)+1);
  const q=new URLSearchParams({id:meta.id,plane:panel.dataset.plane,index:slider.value,width,level});
  try{
    const blob=await(await api('/api/slice?'+q)).blob();
    if(version!==panel._version||panel.querySelector('.sequence-select').value!==meta.id)return;
    const img=panel.querySelector('img'),previous=panel._url;panel._url=URL.createObjectURL(blob);
    img.src=panel._url;img.hidden=false;panel.querySelector('.placeholder').hidden=true;
    if(previous)URL.revokeObjectURL(previous);applyZoom(panel);
  }catch(error){status('image-status',error.message,true);}
}
function selectSequence(panel){
  panel._version=(panel._version||0)+1;
  const meta=volumes.get(panel.querySelector('.sequence-select').value),slider=panel.querySelector('input[type=range]');
  if(!meta){
    panel.querySelector('img').hidden=true;panel.querySelector('.placeholder').hidden=false;
    panel.querySelector('.orientation').hidden=true;slider.disabled=true;slider.max=0;slider.value=0;
    panel.querySelector('output').textContent='—';panel.querySelector('.sequence-select').title='';
    panel.querySelector('.panel-width').value='1000';panel.querySelector('.panel-level').value='500';
    panel.querySelector('.panel-zoom').value='1';applyZoom(panel);return;
  }
  const axis={sagittal:0,coronal:1,axial:2}[panel.dataset.plane];
  slider.max=meta.size[axis]-1;slider.value=Math.floor(meta.size[axis]/2);slider.disabled=false;
  panel.querySelector('.panel-width').value=meta.window.toFixed(3);
  panel.querySelector('.panel-level').value=meta.level.toFixed(3);
  panel.querySelector('.panel-zoom').value='1';
  const orientation=panel.querySelector('.orientation');
  orientation.textContent=meta.oblique?'Oblique: acquisition axes':{axial:'A ↑ · P ↓ · R ← · L →',coronal:'S ↑ · I ↓ · R ← · L →',sagittal:'S ↑ · I ↓ · A ← · P →'}[panel.dataset.plane];
  orientation.hidden=false;
  panel.querySelector('.sequence-select').title=meta.name;
  render(panel);
}
function updateOptions(){
  panels.forEach(panel=>{
    const select=panel.querySelector('.sequence-select'),previous=select.value;
    select.replaceChildren(new Option('Select sequence',''));
    volumes.forEach(v=>select.add(new Option(v.name,v.id)));
    select.disabled=!volumes.size;
    if(volumes.has(previous)){select.value=previous;return;}
    const pattern={sagittal:/(sag|sagittal)/i,coronal:/(cor|coronal)/i,axial:/(axial|tra|transverse|(^|[_\W])ax([_\W]|$))/i}[panel.dataset.plane];
    const chosen=[...volumes.values()].find(v=>pattern.test(v.name))||[...volumes.values()][0];
    select.value=chosen?chosen.id:'';selectSequence(panel);
  });
  $('filename').textContent=volumes.size?volumes.size+' MRI sequence'+(volumes.size>1?'s':'')+' loaded':'Choose or drop MRI sequences';
}
panels.forEach(panel=>{
  const plane=panel.dataset.plane;
  const select=document.createElement('select');select.className='sequence-select';select.setAttribute('aria-label',plane+' sequence');select.disabled=true;
  select.add(new Option('Select sequence',''));panel.querySelector('.view-title').after(select);
  const controls=document.createElement('div');controls.className='panel-tools';
  controls.innerHTML='<label>Width<input class="panel-width" type="number" min="0.001" step="any" value="1000"></label><label>Level<input class="panel-level" type="number" step="any" value="500"></label><label>Zoom<select class="panel-zoom"><option value="1">Fit</option><option value="1.5">150%</option><option value="2">200%</option><option value="3">300%</option></select></label><button class="panel-auto" type="button">Auto</button>';
  panel.append(controls);
  select.addEventListener('change',()=>selectSequence(panel));
  panel.querySelector('input[type=range]').addEventListener('input',()=>render(panel));
  ['.panel-width','.panel-level'].forEach(s=>panel.querySelector(s).addEventListener('change',()=>render(panel)));
  panel.querySelector('.panel-zoom').addEventListener('change',()=>applyZoom(panel));
  panel.querySelector('.panel-auto').addEventListener('click',()=>{
    const meta=volumes.get(select.value);if(!meta)return;
    panel.querySelector('.panel-width').value=meta.window;panel.querySelector('.panel-level').value=meta.level;render(panel);
  });
  panel.querySelector('.screen').addEventListener('wheel',e=>{
    if(!volumes.has(select.value)||e.ctrlKey)return;e.preventDefault();
    const slider=panel.querySelector('input[type=range]');
    slider.value=Math.min(Number(slider.max),Math.max(0,Number(slider.value)+(e.deltaY>0?1:-1)));render(panel);
  },{passive:false});
});
async function uploadFiles(files){
  if(loading)return;
  const list=[...files];if(!list.length)return;
  loading=true;$('file').disabled=true;$('clear').disabled=true;
  const firstImport=!volumes.size;let successes=0;const errors=[];
  for(let i=0;i<list.length;i++){
    const file=list[i];
    if(!/\.(nii|nii\.gz|nrrd)$/i.test(file.name)||file.size>200*1024*1024){errors.push(file.name+': unsupported format or file exceeds 200 MB');continue;}
    status('image-status','Loading sequence '+(i+1)+' of '+list.length+'…');
    try{
      const data=new FormData();data.append('file',file);
      const meta=await(await api('/api/upload',{method:'POST',body:data})).json();
      volumes.set(meta.id,meta);successes++;
    }catch(error){errors.push(file.name+': '+error.message);}
  }
  if(firstImport&&successes){$('prediction-form').reset();invalidateResult();status('form-status','Enter clinical details and scores for the current knee.');}
  updateOptions();
  $('metadata').textContent='';
  status('image-status',errors.length?(successes+' loaded. '+errors.join(' · ')):volumes.size+' sequences available. Choose a sequence for each view.',!!errors.length);
  loading=false;$('file').disabled=false;$('clear').disabled=false;$('file').value='';
}
$('file').addEventListener('change',e=>uploadFiles(e.target.files));
['dragenter','dragover'].forEach(event=>$('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.add('drag');}));
['dragleave','drop'].forEach(event=>$('drop').addEventListener(event,e=>{e.preventDefault();$('drop').classList.remove('drag');}));
$('drop').addEventListener('drop',e=>uploadFiles(e.dataTransfer.files));
$('clear').addEventListener('click',async()=>{
  if(loading)return;
  try{
    await api('/api/clear',{method:'POST',body:'{}'});volumes.clear();updateOptions();
    panels.forEach(p=>{if(p._url){URL.revokeObjectURL(p._url);p._url=null;}});
    $('prediction-form').reset();invalidateResult();$('metadata').textContent='';
    status('image-status','All sequences cleared from application memory.');
  }catch(error){status('image-status',error.message,true);}
});
async function restoreVolumes(){
  try{
    const existing=await(await api('/api/volumes')).json();
    existing.forEach(v=>volumes.set(v.id,v));updateOptions();
    if(existing.length)status('image-status',existing.length+' sequences available. Choose a sequence for each view.');
  }catch(error){status('image-status','Restart the local server to enable multiple sequences.',true);}
}
restoreVolumes();
$('prediction-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const version=inputVersion;
  const inputs={age:Number($('age').value),sex_num:Number($('sex').value)};
  for(const name of ['cart_area_PL','cart_area_FMA','bml_size_SS']){
    const selected=document.querySelector(`input[name="${name}"]:checked`);
    if(!selected){status('form-status','Please complete all three scores.',true);return;}
    inputs[name]=Number(selected.value);
  }
  const button=document.querySelector('.predict-button');button.disabled=true;
  try{
    const r=await(await api('/api/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(inputs)})).json();
    if(version!==inputVersion)return;
    lastResult={...r,created_at:new Date().toISOString(),model:'OAI five-feature frozen Cox model',purpose:'Research use only; probabilities are Cox net-risk estimates without death competing-risk adjustment.'};
    $('empty-results').hidden=true;$('result-content').hidden=false;
    $('group').textContent=r.group;$('group').style.color=r.group==='High risk'?'#b96250':'#397e83';
    $('group-note').textContent=`Training-cohort tertile: ${r.tertile} risk`;
    for(const y of ['5','10']){$('risk'+y).textContent=(r.risk[y]*100).toFixed(1)+'%';$('bar'+y).style.width=(r.risk[y]*100)+'%';}
    $('age-warning').hidden=!r.outside_training_age;$('download').disabled=false;
    status('form-status','Complete. Recalculate after changing any input.');
  }catch(e){status('form-status',e.message,true);}finally{button.disabled=false;}
});
$('download').addEventListener('click',()=>{if(!lastResult)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='OAI_knee_prediction.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
