import * as storage from './storage.mjs';

const $=id=>document.getElementById(id);
const LABELS={greedy:'Greedy',hc:'Hill Climbing',sa:'Simulated Annealing',ga:'Genetic Algorithm',custom:'Custom Python'};
const COLORS={greedy:'#34495E',hc:'#2E86C1',sa:'#C0472A',ga:'#1E8C86',custom:'#9A7400'};
const SHAPES={greedy:'square',hc:'triangle',sa:'diamond',ga:'circle',custom:'star'};
function markerShape(method,cx,cy,r,fill){const s=SHAPES[method]||'circle',c=fill||COLORS[method]||'#34495E';if(s==='square')return`<rect x="${cx-r*.85}" y="${cy-r*.85}" width="${r*1.7}" height="${r*1.7}" rx="${r*.25}" fill="${c}"/>`;if(s==='triangle')return`<path d="M${cx},${cy-r*1.1}L${cx+r},${cy+r*.75}L${cx-r},${cy+r*.75}Z" fill="${c}"/>`;if(s==='diamond')return`<path d="M${cx},${cy-r*1.15}L${cx+r*1.05},${cy}L${cx},${cy+r*1.15}L${cx-r*1.05},${cy}Z" fill="${c}"/>`;if(s==='star'){let d='';for(let i=0;i<10;i++){const a=Math.PI/5*i-Math.PI/2,q=i%2?r*.5:r*1.15;d+=`${i?'L':'M'}${(cx+q*Math.cos(a)).toFixed(2)},${(cy+q*Math.sin(a)).toFixed(2)}`;}return`<path d="${d}Z" fill="${c}"/>`;}return`<circle cx="${cx}" cy="${cy}" r="${r}" fill="${c}"/>`;}
const methodMark=(method,dashed=false)=>`<svg class="method-mark" width="${dashed?28:12}" height="12" viewBox="0 0 ${dashed?28:12} 12" aria-hidden="true">${dashed?`<path d="M0,6H28" stroke="${COLORS[method]||'#34495E'}" stroke-width="2.4" stroke-dasharray="5 3"/>`:''}${markerShape(method,dashed?14:6,6,4.6)}</svg>`;
const ROOM_MODE={weekly:'ห้องรายสัปดาห์ (weekly)',fixed:'ห้องคงที่ (fixed)'};
function runMode(run,batch=state.batch){return run?.room_mode||batch?.config?.room_mode||'weekly';}
function batchModes(batch=state.batch){const modes=[...new Set((batch?.results||[]).map(r=>runMode(r,batch)))];return modes.length?modes:[batch?.config?.room_mode||'weekly'];}
function modeSuffix(run){return batchModes().length>1?` · ${runMode(run)}`:'';}
const STATUS={completed:'จบการค้นหา',evaluation_budget:'ครบงบประเมิน',time_limit:'ถึงเวลาที่กำหนด',error:'โค้ดผิดพลาด',invalid_solution:'ไม่ผ่านข้อห้าม',worker_timeout:'หยุดเมื่อเกินเวลา',cancelled:'ยกเลิก'};
const DAYS=['จันทร์','อังคาร','พุธ','พฤหัสบดี','ศุกร์','เสาร์','อาทิตย์'];
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(value,digits=0)=>Number.isFinite(value)?value.toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'—';
const state={dataset:null,datasetText:'',datasetHash:'',datasetLabel:'',batch:null,worker:null,pending:new Map(),nextId:1,
  running:false,cancelled:false,preparedHash:null,preparedMeta:null,storageFailed:false,currentProgress:[],currentLogs:[]};

function banner(message,success=false){$('banner').textContent=message;$('banner').classList.remove('hidden');$('banner').classList.toggle('success',success);}
function hideBanner(){$('banner').classList.add('hidden');}
function view(name){document.querySelectorAll('.view').forEach(el=>el.classList.toggle('hidden',el.id!==`view-${name}`));document.querySelectorAll('.nav-item').forEach(el=>{el.classList.toggle('active',el.dataset.view===name);if(el.dataset.view===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});if(name==='history')renderHistory();if(name==='results')renderResults();window.scrollTo({top:0,behavior:'instant'});}
document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>view(el.dataset.view)));
document.querySelectorAll('[data-file-picker]').forEach(button=>button.addEventListener('click',()=>{const input=$(button.dataset.filePicker);if(!input.disabled)input.click();}));
async function sha(text){const bytes=typeof text==='string'?new TextEncoder().encode(text):text;const hash=await crypto.subtle.digest('SHA-256',bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');}
function download(name,content,type='application/json'){const blob=new Blob([content],{type});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),5000);}
function safeFilename(name){return String(name).replace(/[^a-zA-Z0-9._-]/g,'_').slice(0,90);}
function csvCell(value){let text=String(value??'');if(/^[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
function csv(rows){return '\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n');}
async function unpack(bytes){if(!globalThis.DecompressionStream)throw new Error('เบราว์เซอร์นี้ยังไม่รองรับ gzip กรุณาอัปโหลดไฟล์ JSON ที่แตกแล้ว');return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();}

async function setDataset(text,label,{keepBatch=false}={}){
  if(state.running)throw new Error('รอให้การทดลองปัจจุบันจบก่อนเปลี่ยนข้อมูล');
  if(text.length>20*1024*1024)throw new Error('ข้อมูล JSON ใหญ่เกิน 20 MB');
  const data=JSON.parse(text);
  for(const field of ['classes','rooms','recurring_sessions','external_classes','student_groups','instructors'])if(!Array.isArray(data[field]))throw new Error(`ไม่พบ ${field} ในข้อมูล`);
  if(data.schema_version!=='1.0'||!data.calendar?.week_ids?.length)throw new Error('ต้องใช้ข้อมูลตาม schema_version 1.0 ของโครงงาน');
  if(!data.constraints||!data.objectives)throw new Error('ไม่พบกฎข้อจำกัดหรือวิธีคิดคะแนน');
  const hash=await sha(text);
  state.dataset=data;state.datasetText=text;state.datasetHash=hash;state.datasetLabel=label;state.preparedHash=null;
  disposeWorker();
  if(!keepBatch)state.batch=null;
  $('dataset-name').textContent=label;
  $('dataset-meta').textContent=`${data.dataset_id} · ตรวจรูปแบบ JSON แล้ว`;
  const counts=[data.classes.length,data.recurring_sessions.reduce((n,s)=>n+s.active_weeks.length,0),
    `${data.rooms.filter(r=>r.schedulable&&r.kind==='lecture').length} + ${data.rooms.filter(r=>r.schedulable&&r.kind==='computer_lab').length}`,data.calendar.week_ids.length];
  $('dataset-stats').querySelectorAll('strong').forEach((node,i)=>node.textContent=typeof counts[i]==='number'?num(counts[i]):counts[i]);
  $('dataset-hash').textContent='Dataset SHA-256: '+hash;
  const details=document.querySelector('.assumptions');
  [...details.querySelectorAll('p:not(#dataset-hash)')].forEach(p=>p.remove());
  const note=document.createElement('p');
  note.textContent=`ปฏิทิน ${data.calendar.week_ids.length} สัปดาห์ · มีคาบที่ต้องใช้ Lab ${data.recurring_sessions.reduce((n,s)=>n+s.lab_weeks.length,0)} คาบรายสัปดาห์ · Seed สร้างข้อมูล ${data.generator?.seed??'ไม่ระบุ'}`;
  details.insertBefore(note,details.querySelector('a'));
  const scope=document.createElement('p');scope.textContent=data.constraints.external_student_overlap_is_hard?'กรณีเข้มงวด: รวมความชนของนักศึกษากับตารางภายนอกเป็นข้อห้าม':'กรณีหลัก: นักศึกษาห้ามชนกันภายใน CS ส่วนภายนอกล็อกห้อง ผู้สอน และ explicit rules ตามข้อมูล';details.insertBefore(scope,details.querySelector('a'));
  const assumed=document.createElement('p');assumed.textContent=data.benchmark_kind==='adapted_synthetic_from_unitime_not_original_score'?'ข้อมูลดัดแปลงจาก UniTime มีปฏิทิน ประเภทห้อง ผู้สอนบางส่วน และ Lab รายสัปดาห์แบบจำลอง':'ตรวจที่มาและสมมติฐานในไฟล์ที่อัปโหลดก่อนสรุปผล';details.insertBefore(assumed,details.querySelector('a'));
  $('run-button').disabled=false;$('run-status').textContent='พร้อมเริ่มทดลอง';
  try{await storage.saveDataset({hash,text,label});}catch(error){storageWarning(error);}
  renderResults();
}
function storageWarning(error){if(!state.storageFailed)banner('บันทึกประวัติอัตโนมัติไม่สำเร็จ กรุณาดาวน์โหลดชุดผล JSON เก็บไว้: '+error.message);state.storageFailed=true;}
async function persist(){if(!state.batch)return;try{await storage.saveExperiment(state.batch);}catch(error){storageWarning(error);}}
async function defaultDataset(){const response=await fetch('../../data/fall-cs.json.gz');if(!response.ok)throw new Error('โหลด Fall CS ไม่สำเร็จ');const text=await unpack(await response.arrayBuffer());const metadata=await (await fetch('../../data/provenance.json')).json();if(await sha(text)!==metadata.dataset_sha256)throw new Error('ไฟล์ Fall CS ไม่ตรงกับ checksum ที่บันทึกไว้');await setDataset(text,'Fall CS · Weekly Labs v1');}
$('dataset-upload').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>12*1024*1024)throw new Error('ไฟล์อัปโหลดใหญ่เกิน 12 MB');const text=file.name.endsWith('.gz')?await unpack(await file.arrayBuffer()):await file.text();hideBanner();await setDataset(text,file.name);}catch(error){banner(error.message);}finally{event.target.value='';}});
$('reset-dataset').addEventListener('click',()=>defaultDataset().catch(error=>banner(error.message)));
$('download-dataset').addEventListener('click',()=>{if(state.dataset)download(safeFilename(state.dataset.dataset_id)+'.json',state.datasetText);});

function selectedMethods(){const result=[...document.querySelectorAll('input[name=algorithm]:checked')].map(x=>x.value);if($('include-custom').checked)result.push('custom');return result;}
function queueSummary(){const count=Math.max(0,Number($('repeats').value)||0),methods=selectedMethods();$('queue-count').textContent=`${methods.length*count} รัน`;$('queue-description').textContent=`${methods.length} วิธี × ${count} seed · งบ ${num(Number($('budget').value))} / รัน · ${ROOM_MODE[$('room-mode').value]}`;}
document.querySelectorAll('input[name=algorithm],#include-custom,#repeats,#budget,#room-mode').forEach(el=>el.addEventListener('input',queueSummary));
function number(id){const input=$(id);if(!input.checkValidity())throw new Error(`ตรวจค่าที่กรอก: ${input.closest('label')?.firstChild?.textContent||id}`);return Number(input.value);}
function settings(){
  const methods=selectedMethods();if(!methods.length)throw new Error('เลือกอัลกอริทึมอย่างน้อย 1 วิธี');
  const start=number('start-seed'),repeats=number('repeats');if(start+repeats-1>4294967295)throw new Error('ช่วง seed เกิน 2^32-1');
  const parameters={hc:{restart_patience:number('hc-patience')},sa:{initial_acceptance:number('sa-acceptance'),cooling_rate:number('sa-cooling')},ga:{population_size:number('ga-population'),tournament_size:number('ga-tournament'),elites:number('ga-elites'),crossover_rate:number('ga-crossover'),mutation_rate:number('ga-mutation')},custom:JSON.parse($('custom-parameters').value)};
  if(parameters.custom===null||Array.isArray(parameters.custom)||typeof parameters.custom!=='object')throw new Error('Custom parameters ต้องเป็น JSON object');
  if(parameters.ga.elites>=parameters.ga.population_size||parameters.ga.tournament_size>parameters.ga.population_size)throw new Error('GA: Elite ต้องน้อยกว่าประชากร และ Tournament ไม่เกินประชากร');
  return {name:$('experiment-name').value.trim()||'Fall CS experiment',methods,seeds:Array.from({length:repeats},(_,i)=>start+i),budget:number('budget'),seconds:number('time-limit'),room_mode:$('room-mode').value==='fixed'?'fixed':'weekly',parameters};
}
function disposeWorker(){if(state.worker)state.worker.terminate();state.worker=null;state.preparedHash=null;for(const {reject,timer} of state.pending.values()){clearTimeout(timer);reject(new Error(state.cancelled?'cancelled':'Worker was restarted'));}state.pending.clear();}
function ensureWorker(){
  if(state.worker)return;
  state.worker=new Worker(new URL('./worker.mjs',import.meta.url),{type:'module'});
  state.worker.onmessage=({data})=>{
    if(data.type==='phase'){$('progress-detail').textContent=data.message;return;}
    if(data.type==='progress'){
      state.currentProgress.push(data.payload);
      $('live-metrics').textContent=`ประเมิน ${data.payload.evaluations} / ${data.payload.budget} · ขาด ${data.payload.objectives[0]} คาบ · Lab เกิน ${num(data.payload.objectives[1]/60,1)} ชม.`;
      return;
    }
    if(data.type==='stdout'||data.type==='stderr'){if(state.currentLogs.length<100)state.currentLogs.push(data.line);return;}
    const pending=state.pending.get(data.id);if(!pending)return;clearTimeout(pending.timer);state.pending.delete(data.id);if(data.error)pending.reject(new Error(data.error));else pending.resolve(data.result);
  };
  state.worker.onerror=event=>{const message=event.message||'Python worker โหลดไม่สำเร็จ ตรวจการเชื่อมต่อ CDN';for(const {reject,timer}of state.pending.values()){clearTimeout(timer);reject(new Error(message));}state.pending.clear();};
}
function rpc(type,payload,timeout){ensureWorker();const id=state.nextId++;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{state.pending.delete(id);const error=new Error(type==='run'?'worker_timeout':'โหลด Python หรือเตรียมข้อมูลนานเกินกำหนด กรุณาลองใหม่');reject(error);disposeWorker();},timeout);state.pending.set(id,{resolve,reject,timer});state.worker.postMessage({id,type,...payload});});}
async function prepare(){if(state.preparedHash===state.datasetHash)return state.preparedMeta;const result=await rpc('prepare',{datasetText:state.datasetText,datasetHash:state.datasetHash},120000);state.preparedHash=state.datasetHash;state.preparedMeta=result;return result;}
function lock(running){$('run-button').disabled=running||!state.dataset;$('stop-button').disabled=!running;for(const id of ['dataset-upload','reset-dataset','include-custom','repeats','budget','time-limit','start-seed','experiment-name','room-mode'])$(id).disabled=running;document.querySelectorAll('input[name=algorithm]').forEach(el=>el.disabled=running);document.querySelector('[data-file-picker=dataset-upload]').disabled=running;document.querySelector('[data-file-picker=import-results]').disabled=running;}
function failedRun(job,error,config){return {algorithm:job.algorithm,room_mode:config.room_mode||'weekly',seed:job.seed,status:error==='cancelled'?'cancelled':error==='worker_timeout'?'worker_timeout':'error',valid:false,metrics:null,validation:{valid:false,violation_count:null,violations:[]},solution:null,evaluations:state.currentProgress.at(-1)?.evaluations||0,budget:config.budget,time_limit_seconds:config.seconds,search_seconds:null,trace:state.currentProgress,error:{message:error},parameters:config.parameters[job.algorithm]||{},dataset_id:state.dataset.dataset_id,dataset_sha256:state.datasetHash,engine_version:'1.0.0'};}
async function startExperiment(){
  if(state.running)return;let config;
  try{config=settings();}catch(error){banner(error.message);return;}
  hideBanner();state.running=true;state.cancelled=false;lock(true);state.currentProgress=[];state.currentLogs=[];
  const jobs=config.seeds.flatMap(seed=>config.methods.map(algorithm=>({algorithm,seed})));
  state.batch={id:crypto.randomUUID(),name:config.name,created_at:new Date().toISOString(),status:'running',dataset_hash:state.datasetHash,dataset_id:state.dataset.dataset_id,dataset_label:state.datasetLabel,config,run_order:jobs,results:[],custom_source:config.methods.includes('custom')?$('custom-code').value:'',browser:{user_agent:navigator.userAgent,logical_processors:navigator.hardwareConcurrency||null},code_snapshot:{}};
  await persist();$('run-progress').max=jobs.length;$('run-progress').value=0;$('run-fraction').textContent=`0 / ${jobs.length}`;$('run-status').textContent='กำลังเตรียมการทดลอง';
  try{
    const meta=await prepare();if(state.cancelled)throw new Error('cancelled');
    state.batch.preparation={...meta};delete state.batch.preparation.code_snapshot;state.batch.code_snapshot=meta.code_snapshot;state.batch.engine_sha256=await sha(JSON.stringify(meta.code_snapshot));
    await persist();
    for(let index=0;index<jobs.length;index++){
      if(state.cancelled)break;const job=jobs[index];state.currentProgress=[];state.currentLogs=[];
      $('run-status').textContent=`${LABELS[job.algorithm]} · seed ${job.seed}`;$('progress-detail').textContent=`รันที่ ${index+1} จาก ${jobs.length} · เตรียมข้อมูลร่วม ${num(meta.preprocessing_seconds,2)} วินาที (ไม่นับในเวลาค้นหา)`;
      let result;
      try{
        const currentMeta=await prepare();if(await sha(JSON.stringify(currentMeta.code_snapshot))!==state.batch.engine_sha256)throw new Error('โค้ด runtime เปลี่ยนระหว่างทดลอง กรุณาเริ่มชุดใหม่');
        result=await rpc('run',{algorithm:job.algorithm,seed:job.seed,config,datasetHash:state.datasetHash,customCode:state.batch.custom_source},(config.seconds+12)*1000);
      }catch(error){result=failedRun(job,state.cancelled?'cancelled':error.message,config);disposeWorker();}
      result.run_index=index;result.logs=state.currentLogs.slice();state.batch.results.push(result);
      $('run-progress').value=index+1;$('run-fraction').textContent=`${index+1} / ${jobs.length}`;
      await persist();renderResults();
      if(job.algorithm==='custom')disposeWorker();
    }
    state.batch.status=state.cancelled?'cancelled':'completed';
  }catch(error){state.batch.status=state.cancelled?'cancelled':'error';state.batch.error=error.message;if(!state.cancelled)banner(error.message);}
  finally{
    state.batch.finished_at=new Date().toISOString();state.running=false;lock(false);await persist();
    $('run-status').textContent=state.cancelled?'หยุดและเก็บผลที่มีแล้ว':state.batch.status==='error'?'การทดลองหยุดด้วยข้อผิดพลาด':state.storageFailed?'เสร็จแล้ว · กรุณาดาวน์โหลดผล':'เสร็จและบันทึกผลแล้ว';
    $('progress-detail').textContent=`ได้ผล ${state.batch.results.length} จาก ${jobs.length} รัน · ดาวน์โหลด CSV หรือชุดผล JSON ได้`;
    renderResults();if(state.batch.results.length)view('results');
    if(state.batch.status==='completed'&&state.batch.results.some(r=>r.valid))celebrate();
  }
}
function celebrate(){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const layer=document.createElement('div'),colors=['#FFD23F','#2BA8A2','#EF6C4A','#5DADE2','#3CC4BD','#FFE47A'];layer.className='confetti';layer.setAttribute('aria-hidden','true');
  for(let i=0;i<36;i++){const piece=document.createElement('i'),angle=Math.random()*Math.PI*2,dist=120+Math.random()*220;
    piece.style.cssText=`left:50%;top:38%;background:${colors[i%colors.length]};--dx:${(Math.cos(angle)*dist).toFixed(0)}px;--dy:${(Math.sin(angle)*dist+60).toFixed(0)}px;--rot:${(Math.random()*540-270).toFixed(0)}deg;animation-delay:${(Math.random()*60).toFixed(0)}ms`;layer.append(piece);}
  document.body.append(layer);setTimeout(()=>layer.remove(),700);
}
$('run-button').addEventListener('click',startExperiment);
$('stop-button').addEventListener('click',()=>{state.cancelled=true;disposeWorker();$('run-status').textContent='กำลังหยุดและบันทึกผลที่มี';});

function mean(values){return values.length?values.reduce((a,b)=>a+b,0)/values.length:NaN;}
function median(values){if(!values.length)return NaN;const sorted=values.slice().sort((a,b)=>a-b);const m=Math.floor(sorted.length/2);return sorted.length%2?sorted[m]:(sorted[m-1]+sorted[m])/2;}
function sd(values){if(values.length<2)return values.length?0:NaN;const avg=mean(values);return Math.sqrt(values.reduce((n,v)=>n+(v-avg)**2,0)/(values.length-1));}
function methodLabel(method){return `<span class="method-label">${methodMark(method)}${esc(LABELS[method]||method)}</span>`;}
function statusLabel(run){const failed=!run.valid;const partial=run.valid&&run.metrics?.unassigned_weekly_sessions>0;return `<span class="status ${failed?'failed':partial?'partial':''}">${esc(STATUS[run.status]||run.status)}${partial?' · ตารางบางส่วน':''}</span>`;}
function renderResults(){
  const batch=state.batch,results=batch?.results||[];$('result-count').textContent=results.length;
  $('results-empty').classList.toggle('hidden',results.length>0);$('results-content').classList.toggle('hidden',!results.length);
  for(const id of ['export-csv','export-json'])$(id).disabled=!results.length;
  if(!results.length)return;
  $('results-description').textContent=`${batch.name} · ${results.length} / ${batch.run_order?.length||results.length} รัน${batch.imported?' · นำเข้า ไม่ได้รันใหม่':''}`;
  $('result-meta').innerHTML=[batch.dataset_id,batchModes(batch).map(m=>ROOM_MODE[m]||m).join(' + '),`Dataset ${batch.dataset_hash.slice(0,12)}`,`งบ ${batch.config.budget} / รัน`,`Python ${batch.preparation?.pyodide_version||'native'}`,`Code ${(batch.engine_sha256||'').slice(0,12)}`].map(x=>`<span>${esc(x)}</span>`).join('');
  const groups=[...new Set(results.map(r=>`${r.algorithm}\u0000${runMode(r,batch)}`))];
  const summaries=groups.map(group=>{const [algorithm,mode]=group.split('\u0000'),rows=results.filter(r=>r.algorithm===algorithm&&runMode(r,batch)===mode),valid=rows.filter(r=>r.valid&&r.metrics);return{algorithm,mode,rows,valid,key:[median(valid.map(r=>r.metrics.unassigned_weekly_sessions)),median(valid.map(r=>r.metrics.unnecessary_lab_minutes)),median(valid.map(r=>r.metrics.room_changes))]};});
  summaries.sort((a,b)=>{for(let i=0;i<3;i++){const x=Number.isFinite(a.key[i])?a.key[i]:Infinity,y=Number.isFinite(b.key[i])?b.key[i]:Infinity;if(x!==y)return x-y;}return 0;});
  const rankKey=s=>s.key.map(v=>Number.isFinite(v)?v:Infinity).join('|');let rank=0,lastKey=null;
  summaries.forEach((s,i)=>{if(!s.valid.length){s.rank=null;return;}const k=rankKey(s);if(k!==lastKey){rank=i+1;lastKey=k;}s.rank=rank;});
  const rankBadge=r=>r?`<span class="rank-badge r${Math.min(r,4)}" title="อันดับ ${r}"><span class="sr-only">อันดับ </span>${r}</span>`:`<span class="rank-badge none" title="ไม่มีคำตอบที่ตรวจผ่าน">–</span>`;
  $('summary-body').innerHTML=summaries.map(s=>{const hours=s.valid.map(r=>r.metrics.unnecessary_lab_hours);return`<tr${s.rank===1?' class="best"':''}><td>${rankBadge(s.rank)}${methodLabel(s.algorithm)}${esc(modeSuffix(s.rows[0]))}</td><td class="number">${s.valid.length} / ${s.rows.length}</td><td class="number">${num(s.key[0],1)}</td><td class="number">${num(mean(hours),2)} ± ${num(sd(hours),2)}</td><td class="number">${num(s.key[2],1)}</td><td class="number">${num(mean(s.rows.filter(r=>Number.isFinite(r.search_seconds)).map(r=>r.search_seconds)),3)}</td></tr>`;}).join('');
  $('runs-body').innerHTML=results.map(r=>`<tr><td>${methodLabel(r.algorithm)}<br><span class="micro mono">seed ${esc(r.seed)}${esc(modeSuffix(r))}</span></td><td>${statusLabel(r)}${r.error?`<p class="error-text">${esc(r.error.message).slice(0,500)}</p>`:''}</td><td class="number">${num(r.metrics?.unassigned_weekly_sessions)}</td><td class="number">${num(r.metrics?.unnecessary_lab_hours,2)}</td><td class="number">${num(r.metrics?.room_changes)}</td><td class="number">${num(r.evaluations)}</td><td class="number">${num(r.search_seconds,3)}</td><td class="number">${num(r.validation?.violation_count)}</td></tr>`).join('');
  const oldSeed=$('chart-seed').value,seeds=[...new Set(results.map(r=>r.seed))];$('chart-seed').replaceChildren(...seeds.map(seed=>new Option(String(seed),String(seed))));if(seeds.includes(Number(oldSeed)))$('chart-seed').value=oldSeed;
  const oldRun=$('schedule-run').value;$('schedule-run').replaceChildren(...results.map((r,i)=>new Option(`${LABELS[r.algorithm]||r.algorithm} · ${r.seed}${modeSuffix(r)}${r.valid?'':' · ไม่ผ่าน'}`,String(i))));if(Number(oldRun)<results.length)$('schedule-run').value=oldRun||'0';
  const oldWeek=$('schedule-week').value;$('schedule-week').replaceChildren(...state.dataset.calendar.week_ids.map(w=>new Option(String(w),String(w))));if(state.dataset.calendar.week_ids.includes(Number(oldWeek)))$('schedule-week').value=oldWeek;
  renderChart();renderSchedule();
}
function renderChart(){
  const results=(state.batch?.results||[]).filter(r=>r.valid&&r.seed===Number($('chart-seed').value));const metric=Number($('chart-metric').value),scale=metric===1?60:1;
  const traces=results.map(r=>({method:r.algorithm,suffix:modeSuffix(r),dashed:batchModes().length>1&&runMode(r)==='fixed',points:(Array.isArray(r.trace)?r.trace:[]).filter(p=>Number.isFinite(p.objectives?.[metric])&&Number.isFinite(p.evaluations)).map(p=>[p.evaluations,p.objectives[metric]/scale])})).filter(x=>x.points.length);
  if(!traces.length){$('convergence-chart').textContent='ยังไม่มี trace ที่ตรวจผ่านสำหรับ seed นี้';$('chart-legend').textContent='';return;}
  const width=1000,height=280,left=65,right=20,top=20,bottom=40,maxX=Math.max(1,state.batch.config.budget),maxY=Math.max(1,...traces.flatMap(t=>t.points.map(p=>p[1])))*1.1;
  const x=n=>left+n/maxX*(width-left-right),y=n=>height-bottom-n/maxY*(height-top-bottom);
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="คำตอบดีที่สุดเทียบจำนวนครั้งประเมิน"><rect width="1000" height="280" fill="#FFFFFF"/>`;
  for(let i=0;i<=4;i++){const v=maxY*i/4;svg+=`<line x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}" stroke="#DDEDEB" stroke-dasharray="${i?'4 4':'0'}"/><text x="${left-10}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="#5B6B7A">${num(v,metric===1?1:0)}</text>`;}
  for(const v of [0,Math.round(maxX/2),maxX])svg+=`<text x="${x(v)}" y="${height-20}" text-anchor="middle" font-size="11" fill="#5B6B7A">${v}</text>`;
  for(const trace of traces){const path=trace.points.map((p,i)=>`${i?'L':'M'}${x(p[0])},${y(p[1])}`).join(' ');svg+=`<path d="${path}" fill="none" stroke="${COLORS[trace.method]||'#34495E'}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"${trace.dashed?' stroke-dasharray="7 5"':''}/>`;for(const p of [trace.points[0],trace.points.at(-1)])svg+=`<g stroke="#FFFFFF" stroke-width="1.5">${markerShape(trace.method,x(p[0]),y(p[1]),5)}</g>`;}
  svg+=`<text x="${width/2}" y="${height-3}" text-anchor="middle" font-size="11" fill="#5B6B7A">จำนวนครั้งประเมินคำตอบ</text></svg>`;$('convergence-chart').innerHTML=svg;$('chart-legend').innerHTML=traces.map(t=>`<span>${methodMark(t.method,t.dashed)}${esc((LABELS[t.method]||t.method)+t.suffix)}</span>`).join('');
}
const clock=minute=>`${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`;
const hrs=minutes=>{const h=minutes/60;return num(h,Number.isInteger(h)?0:Number.isInteger(h*10)?1:2);};
const byId=(a,b)=>String(a).localeCompare(String(b),'en',{numeric:true});
const slot=(sessionId,week)=>`${sessionId}\u0000${week}`;
const roomKind=kind=>kind==='computer_lab'?'Computer lab':kind==='lecture'?'ห้องบรรยาย':'ห้องอื่น';
const currentRun=()=>state.batch?.results?.[Number($('schedule-run').value)];
const sortedClasses=()=>state.dataset.classes.slice().sort((a,b)=>byId(a.id,b.id));
const classSessions=c=>state.dataset.recurring_sessions.filter(s=>s.class_id===c.id).sort((a,b)=>(a.ordinal??0)-(b.ordinal??0)||byId(a.id,b.id));
const viewCache=new WeakMap();
// Counts exactly like engine/solution_validator.py: a row counts once per (session, week), only in an active week of a session whose class has a chosen time.
// Unnecessary Lab = session duration_minutes in a computer_lab during a week outside lab_weeks. A room change = a different room from the previous assigned active week.
function runView(run){
  if(!run?.solution||!state.dataset)return null;const cached=viewCache.get(run);if(cached?.dataset===state.dataset)return cached;
  const d=state.dataset,classes=new Map(d.classes.map(c=>[c.id,c])),sessions=new Map(d.recurring_sessions.map(s=>[s.id,s])),rooms=new Map(d.rooms.map(r=>[r.id,r])),meetings=new Map(),assigned=new Map(),rows=[];
  for(const c of d.classes){const option=c.time_options.find(o=>o.id===run.solution.class_time_options?.[c.id]);for(const m of option?.meetings||[])meetings.set(m.session_id,m);}
  for(const row of Array.isArray(run.solution.weekly_room_assignments)?run.solution.weekly_room_assignments:[]){
    const s=sessions.get(row?.session_id),room=rooms.get(row?.room_id),m=meetings.get(row?.session_id);
    if(!s||!room||!Number.isInteger(row.week)||assigned.has(slot(s.id,row.week))||!s.active_weeks.includes(row.week)||!m)continue;
    const needs_lab=s.lab_weeks.includes(row.week),item={session_id:s.id,week:row.week,room_id:room.id,room_kind:room.kind,class_id:s.class_id,course_id:classes.get(s.class_id)?.course_id,day:m.day,start:m.start_minute,end:m.start_minute+m.duration_minutes,minutes:s.duration_minutes,needs_lab,unnecessary:room.kind==='computer_lab'&&!needs_lab,changed:false};
    assigned.set(slot(s.id,row.week),item);rows.push(item);
  }
  const stats=new Map(d.classes.map(c=>[c.id,{changes:0,unnecessary:0,unassigned:0,rooms:new Set()}]));let changes=0,unnecessary=0;
  for(const s of d.recurring_sessions){let previous=null;for(const week of s.active_weeks.slice().sort((a,b)=>a-b)){const item=assigned.get(slot(s.id,week));if(!item){if(stats.has(s.class_id))stats.get(s.class_id).unassigned++;continue;}item.changed=previous!==null&&item.room_id!==previous;previous=item.room_id;}}
  for(const r of rows){const st=stats.get(r.class_id);changes+=r.changed;if(r.unnecessary)unnecessary+=r.minutes;if(!st)continue;st.changes+=r.changed;if(r.unnecessary)st.unnecessary+=r.minutes;st.rooms.add(r.room_id);}
  const labs=d.rooms.filter(r=>r.kind==='computer_lab').map(r=>r.id).sort(byId),heat=new Map(labs.map(id=>[id,new Map()]));
  for(const r of rows){const lab=heat.get(r.room_id);if(!lab)continue;const cell=lab.get(r.week)||{need:0,extra:0};cell[r.unnecessary?'extra':'need']+=r.minutes;lab.set(r.week,cell);}
  const view={dataset:d,rows,assigned,meetings,stats,changes,unnecessary,labs,heat};viewCache.set(run,view);return view;
}
function metricCheck(value,metric,format,label){return Number.isFinite(metric)?(value===metric?`<span class="ok">✓ ตรงกับ “${label}” ของรันนี้ (${format(metric)})</span>`:`<span class="warn">ไม่ตรงกับ “${label}” ของรันนี้ (${format(metric)})</span>`):'<span class="muted">รันนี้ไม่มีผลตรวจให้เทียบ</span>';}
function renderWeekTable(run,v){const week=Number($('schedule-week').value),rows=(v?.rows||[]).filter(r=>r.week===week).sort((a,b)=>a.day-b.day||a.start-b.start||a.session_id.localeCompare(b.session_id));$('schedule-body').innerHTML=rows.map(r=>`<tr><td>${DAYS[r.day]}</td><td class="mono">${clock(r.start)}–${clock(r.end)}</td><td>${esc(r.class_id)}<br><span class="micro mono">${esc(r.session_id)}</span></td><td>${esc(r.room_id)}<br><span class="micro">${roomKind(r.room_kind)}</span></td><td>${r.needs_lab?'จำเป็น':'ไม่จำเป็น'}</td></tr>`).join('')||'<tr><td colspan="5">ไม่มีคาบที่จัดได้ในสัปดาห์นี้</td></tr>';const assigned=new Set(rows.map(r=>r.session_id)),missing=state.dataset.recurring_sessions.filter(s=>s.active_weeks.includes(week)&&!assigned.has(s.id));$('unassigned-title').textContent=`คาบที่ยังจัดไม่ได้ในสัปดาห์ ${week}: ${missing.length} คาบ`;$('unassigned-list').innerHTML=missing.map(s=>`<span>${esc(s.id)}</span>`).join('');}
function renderHeatmap(run,v){
  const table=$('heatmap-table'),summary=$('heatmap-summary');if(!v||!v.labs.length){summary.textContent=v?'ชุดข้อมูลนี้ไม่มีห้อง Lab':'รันนี้ไม่มีตารางให้แสดง';table.innerHTML='';delete summary.dataset.unnecessaryMinutes;return;}
  const weeks=state.dataset.calendar.week_ids,get=(lab,w)=>v.heat.get(lab).get(w)||{need:0,extra:0},sum=list=>list.reduce((n,c)=>({need:n.need+c.need,extra:n.extra+c.extra}),{need:0,extra:0});
  const max=Math.max(1,...v.labs.flatMap(lab=>weeks.map(w=>{const c=get(lab,w);return c.need+c.extra;})));
  const split=c=>`${hrs(c.need)}${c.extra?`<b class="extra-text">+${hrs(c.extra)}</b>`:''}`;
  const cell=(c,label)=>{const total=c.need+c.extra;if(!total)return`<td class="hm-cell empty" data-need="0" data-extra="0"><span aria-hidden="true">·</span><span class="sr-only">${label}: ไม่ได้ใช้</span></td>`;return`<td class="hm-cell" style="--fill:${(0.05+0.32*total/max).toFixed(3)}" data-need="${c.need}" data-extra="${c.extra}" title="${label}: รวม ${hrs(total)} ชม. · จำเป็น ${hrs(c.need)} · ไม่จำเป็น ${hrs(c.extra)}"><span class="hm-num" aria-hidden="true">${split(c)}</span><span class="hm-bar" aria-hidden="true"><i class="need" style="width:${(c.need/max*100).toFixed(1)}%"></i><i class="extra" style="width:${(c.extra/max*100).toFixed(1)}%"></i></span><span class="sr-only">${label}: จำเป็น ${hrs(c.need)} ชม. ไม่จำเป็น ${hrs(c.extra)} ชม.</span></td>`;};
  const totals=c=>`<td class="total">${hrs(c.need)}</td><td class="total extra-text">${hrs(c.extra)}</td><td class="total"><b>${hrs(c.need+c.extra)}</b></td>`;
  const all=sum(v.labs.flatMap(lab=>weeks.map(w=>get(lab,w))));
  table.innerHTML=`<caption class="sr-only">ชั่วโมงใช้ห้อง Lab แต่ละสัปดาห์ แยกจำเป็นและไม่จำเป็น</caption><thead><tr><th rowspan="2" scope="col">ห้อง Lab</th><th colspan="${weeks.length}" scope="colgroup" class="center">สัปดาห์ที่</th><th colspan="3" scope="colgroup" class="center">รวมทั้งเทอม (ชม.)</th></tr><tr>${weeks.map(w=>`<th scope="col" class="center">${esc(w)}</th>`).join('')}<th scope="col">จำเป็น</th><th scope="col">ไม่จำเป็น</th><th scope="col">รวม</th></tr></thead><tbody>${v.labs.map(lab=>`<tr><th scope="row">${esc(lab)}</th>${weeks.map(w=>cell(get(lab,w),`${esc(lab)} สัปดาห์ ${esc(w)}`)).join('')}${totals(sum(weeks.map(w=>get(lab,w))))}</tr>`).join('')}</tbody><tfoot><tr><th scope="row">รวมทุกห้อง</th>${weeks.map(w=>`<td class="center">${split(sum(v.labs.map(lab=>get(lab,w))))}</td>`).join('')}${totals(all)}</tr></tfoot>`;
  summary.dataset.unnecessaryMinutes=all.extra;
  summary.innerHTML=`ห้อง Lab ${v.labs.length} ห้อง · ใช้รวม <b>${hrs(all.need+all.extra)}</b> ชม. · จำเป็น <b>${hrs(all.need)}</b> ชม. · ไม่จำเป็น <b class="extra-text">${hrs(all.extra)}</b> ชม. ${metricCheck(all.extra,run.metrics?.unnecessary_lab_minutes,m=>`${hrs(m)} ชม.`,'Lab ไม่จำเป็น')}`;
}
function renderClassOptions(){
  const v=runView(currentRun()),select=$('class-select'),old=select.value;if(!v){select.replaceChildren();$('class-match').textContent='';renderClassView();return;}
  const q=$('class-search').value.trim().toLowerCase(),only=$('class-changed-only').checked;
  const list=sortedClasses().filter(c=>{const st=v.stats.get(c.id);return(!only||st.changes>0)&&(!q||[c.id,c.course_id,...st.rooms].some(x=>String(x??'').toLowerCase().includes(q)));});
  select.replaceChildren(...list.map(c=>{const st=v.stats.get(c.id);return new Option(`${c.id} · ${c.course_id??'—'}${st.changes?` · เปลี่ยนห้อง ${st.changes}`:''}${st.unassigned?` · ขาด ${st.unassigned}`:''}`,c.id);}));
  if(list.some(c=>c.id===old))select.value=old;
  $('class-match').textContent=`${list.length} / ${state.dataset.classes.length} คลาส`;renderClassView();
}
function renderClassView(){
  const run=currentRun(),v=runView(run),table=$('class-table'),summary=$('class-summary');if(!v){summary.textContent='รันนี้ไม่มีตารางให้แสดง';table.innerHTML='';return;}
  const total=`<br><span class="muted">ทั้งรัน: เปลี่ยนห้อง <b>${num(v.changes)}</b> ครั้ง</span> ${metricCheck(v.changes,run.metrics?.room_changes,num,'เปลี่ยนห้อง')}`;
  const c=state.dataset.classes.find(x=>x.id===$('class-select').value);if(!c){summary.innerHTML=`ไม่พบคลาสที่ตรงกับเงื่อนไข ลองล้างคำค้นหรือเอาเครื่องหมาย “เฉพาะคลาสที่เปลี่ยนห้อง” ออก${total}`;table.innerHTML='';return;}
  const st=v.stats.get(c.id),sessions=classSessions(c),weeks=state.dataset.calendar.week_ids;
  summary.innerHTML=`<b>${esc(c.id)}</b> · คอร์ส ${esc(c.course_id??'—')} · นักศึกษา ${num(c.student_count)} คน · ${sessions.length} คาบ/สัปดาห์ · เปลี่ยนห้อง <b>${st.changes}</b> ครั้ง · Lab ไม่จำเป็น <b class="extra-text">${hrs(st.unnecessary)}</b> ชม. · ยังจัดไม่ได้ ${st.unassigned} คาบ${total}`;
  const cell=(s,w)=>{const needs=s.lab_weeks.includes(w),lab=needs?'<span class="badge lab">ต้องใช้ Lab</span>':'';if(!s.active_weeks.includes(w))return'<td class="cv-cell off">ไม่มีเรียน</td>';const r=v.assigned.get(slot(s.id,w));if(!r)return`<td class="cv-cell missing${needs?' lab':''}"><b>ยังจัดไม่ได้</b><span class="badges">${lab}</span></td>`;return`<td class="cv-cell${r.changed?' changed':''}${needs?' lab':''}${r.unnecessary?' extra':''}"><span class="mono room">${esc(r.room_id)}</span> <span class="micro">${roomKind(r.room_kind)}</span><span class="badges">${r.changed?'<span class="badge changed">เปลี่ยนห้อง</span>':''}${lab}${r.unnecessary?'<span class="badge extra">Lab ไม่จำเป็น</span>':''}</span></td>`;};
  table.innerHTML=`<caption class="sr-only">ห้องของคลาส ${esc(c.id)} แต่ละสัปดาห์</caption><thead><tr><th scope="col">สัปดาห์</th>${sessions.map(s=>{const m=v.meetings.get(s.id);return`<th scope="col">${esc(s.id)}<br><span class="micro">${m?`${DAYS[m.day]} ${clock(m.start_minute)}–${clock(m.start_minute+m.duration_minutes)}`:'ยังไม่มีเวลาเรียน'}</span></th>`;}).join('')}</tr></thead><tbody>${weeks.map(w=>`<tr><th scope="row">${esc(w)}</th>${sessions.map(s=>cell(s,w)).join('')}</tr>`).join('')}</tbody>`;
}
const TABS=['week','heatmap','class'];let scheduleTab='week';
function selectTab(name,focus=false){scheduleTab=name;for(const t of TABS){const on=t===name,tab=$(`tab-${t}`);tab.setAttribute('aria-selected',String(on));tab.tabIndex=on?0:-1;$(`pane-${t}`).hidden=!on;}if(focus)$(`tab-${name}`).focus();renderSchedule();}
TABS.forEach((t,i)=>{const tab=$(`tab-${t}`);tab.addEventListener('click',()=>selectTab(t));tab.addEventListener('keydown',event=>{const step={ArrowRight:1,ArrowLeft:-1}[event.key],next=step?TABS[(i+step+TABS.length)%TABS.length]:event.key==='Home'?TABS[0]:event.key==='End'?TABS.at(-1):null;if(next){event.preventDefault();selectTab(next,true);}});});
function renderSchedule(){const run=currentRun();if(!run)return;const v=runView(run);$('schedule-description').textContent=run.valid?`ตารางตรวจผ่านข้อห้าม · ${ROOM_MODE[runMode(run)]||runMode(run)}`:'คำตอบนี้ไม่ผ่านหรือไม่มีตาราง ห้ามใช้สรุปว่าอัลกอริทึมดีกว่า';for(const id of ['export-room-csv','export-class-csv'])$(id).disabled=!v;if(scheduleTab==='heatmap')renderHeatmap(run,v);else if(scheduleTab==='class')renderClassOptions();else renderWeekTable(run,v);$('validation-details').textContent=JSON.stringify({status:run.status,validation:run.validation,error:run.error,logs:run.logs},null,2);}
for(const id of ['chart-seed','chart-metric'])$(id).addEventListener('change',renderChart);for(const id of ['schedule-run','schedule-week'])$(id).addEventListener('change',renderSchedule);
$('class-select').addEventListener('change',renderClassView);$('class-search').addEventListener('input',renderClassOptions);$('class-changed-only').addEventListener('change',renderClassOptions);
$('export-csv').addEventListener('click',()=>{const b=state.batch;const headers=['experiment_id','dataset_id','dataset_sha256','room_mode','algorithm','seed','status','valid','unassigned_weekly_sessions','unnecessary_lab_minutes','unnecessary_lab_hours','room_changes','hard_violations','evaluations','attempted_evaluations','budget','search_seconds','validation_seconds','time_limit_seconds','code_sha256','engine_version','parameters_json'];const rows=b.results.map(r=>[b.id,r.dataset_id,r.dataset_sha256,r.room_mode||b.config.room_mode||'weekly',r.algorithm,r.seed,r.status,r.valid,r.metrics?.unassigned_weekly_sessions,r.metrics?.unnecessary_lab_minutes,r.metrics?.unnecessary_lab_hours,r.metrics?.room_changes,r.validation?.violation_count,r.evaluations,r.attempted_evaluations,r.budget,r.search_seconds,r.validation_seconds,r.time_limit_seconds,r.code_sha256,r.engine_version,JSON.stringify(r.parameters)]);download(`results-${b.id}.csv`,csv([headers,...rows]),'text/csv;charset=utf-8');});
$('export-json').addEventListener('click',()=>{const payload={format:'timetable-lab-experiment/v1',exported_at:new Date().toISOString(),batch:state.batch,dataset_text:state.datasetText};download(`experiment-${state.batch.id}.json`,JSON.stringify(payload,null,2));});
function exportSchedule(kind){
  const run=currentRun(),v=runView(run);if(!v){banner('รันนี้ไม่มีตารางให้ส่งออก');return;}
  const meta=[run.algorithm,runMode(run),run.seed],time=m=>m?[DAYS[m.day],clock(m.start_minute),clock(m.start_minute+m.duration_minutes)]:['','',''];let headers,rows;
  if(kind==='room'){
    headers=['algorithm','room_mode','seed','room_id','room_kind','week','day','start','end','class_id','course_id','session_id','requires_lab','lab_use'];
    rows=v.rows.slice().sort((a,b)=>byId(a.room_id,b.room_id)||a.week-b.week||a.day-b.day||a.start-b.start||byId(a.session_id,b.session_id)).map(r=>[...meta,r.room_id,r.room_kind,r.week,DAYS[r.day],clock(r.start),clock(r.end),r.class_id,r.course_id,r.session_id,r.needs_lab,r.room_kind==='computer_lab'?(r.needs_lab?'จำเป็น':'ไม่จำเป็น'):'']);
  }else{
    headers=['algorithm','room_mode','seed','class_id','course_id','session_id','week','day','start','end','room_id','room_kind','requires_lab','room_changed','unnecessary_lab','status'];
    rows=sortedClasses().flatMap(c=>classSessions(c).flatMap(s=>state.dataset.calendar.week_ids.filter(w=>s.active_weeks.includes(w)).map(w=>{const r=v.assigned.get(slot(s.id,w));return[...meta,c.id,c.course_id,s.id,w,...time(v.meetings.get(s.id)),r?.room_id??'',r?.room_kind??'',s.lab_weeks.includes(w),!!r?.changed,!!r?.unnecessary,r?'จัดแล้ว':'ยังจัดไม่ได้'];})));
  }
  download(`schedule-by-${kind}-${safeFilename(`${run.algorithm}-${runMode(run)}-${run.seed}`)}.csv`,csv([headers,...rows]),'text/csv;charset=utf-8');
}
$('export-room-csv').addEventListener('click',()=>exportSchedule('room'));$('export-class-csv').addEventListener('click',()=>exportSchedule('class'));

async function renderHistory(){try{const batches=(await storage.loadExperiments()).sort((a,b)=>b.created_at.localeCompare(a.created_at));$('history-list').innerHTML=batches.map(b=>`<article class="panel history-card"><div><h2>${esc(b.name)}</h2><p>${esc(b.dataset_id)} · ${esc(batchModes(b).join(' + '))} · ${b.results.length} รัน · ${new Intl.DateTimeFormat('th-TH',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Bangkok'}).format(new Date(b.created_at))}</p><span class="tag">${esc(b.status)}${b.imported?' · นำเข้า':''}</span></div><button class="button secondary history-open" data-id="${esc(b.id)}" ${state.running?'disabled':''}>เปิดผลการทดลอง ↗</button></article>`).join('')||'<div class="empty panel"><h2>ยังไม่มีประวัติการทดลอง</h2><p>ผลจะถูกบันทึกหลังแต่ละรันโดยอัตโนมัติ</p></div>';$('history-list').querySelectorAll('.history-open').forEach(button=>button.addEventListener('click',async()=>{try{const batch=batches.find(b=>b.id===button.dataset.id),dataset=await storage.loadDataset(batch.dataset_hash);if(!dataset)throw new Error('ไม่พบข้อมูลประกอบ กรุณานำเข้าชุดผล JSON ที่ส่งออกไว้');await setDataset(dataset.text,dataset.label,{keepBatch:true});state.batch=batch;view('results');}catch(error){banner(error.message);}}));}catch(error){storageWarning(error);$('history-list').textContent='ไม่สามารถเปิดฐานข้อมูลประวัติในเบราว์เซอร์นี้ได้';}}
$('import-results').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(state.running)throw new Error('รอให้การทดลองปัจจุบันจบก่อนนำเข้าผล');if(file.size>60*1024*1024)throw new Error('ชุดผลใหญ่เกิน 60 MB');const payload=JSON.parse(file.name.endsWith('.gz')?await unpack(await file.arrayBuffer()):await file.text());if(payload.format!=='timetable-lab-experiment/v1'||typeof payload.dataset_text!=='string'||!Array.isArray(payload.batch?.results)||payload.batch.results.length>1000)throw new Error('รูปแบบชุดผลไม่ถูกต้อง');const b=payload.batch;
if(typeof b.name!=='string'||typeof b.dataset_hash!=='string'||!Number.isFinite(Date.parse(b.created_at))||!Number.isInteger(b.config?.budget)||b.config.budget<1||b.config.budget>100000||!Array.isArray(b.config.methods)||!b.results.every(r=>r&&typeof r.algorithm==='string'&&Number.isInteger(r.seed)&&typeof r.status==='string'&&typeof r.valid==='boolean'&&Array.isArray(r.trace)&&(!r.valid||(r.metrics&&['unassigned_weekly_sessions','unnecessary_lab_minutes','unnecessary_lab_hours','room_changes'].every(k=>Number.isFinite(r.metrics[k])&&r.metrics[k]>=0)))&&(!r.solution||(typeof r.solution==='object'&&Array.isArray(r.solution.weekly_room_assignments)))))throw new Error('ข้อมูลตั้งค่าหรือผลรายรันในชุดผลไม่ครบ');
if(await sha(payload.dataset_text)!==payload.batch.dataset_hash)throw new Error('Hash ของชุดข้อมูลไม่ตรงกับผลที่นำเข้า');await setDataset(payload.dataset_text,payload.batch.dataset_label||'Imported dataset',{keepBatch:true});state.batch={...payload.batch,id:crypto.randomUUID(),imported:true,imported_from:payload.batch.id};await persist();view('results');banner('นำเข้าชุดผลแล้ว โดยไม่ได้รันอัลกอริทึมใหม่',true);}catch(error){banner(error.message);}finally{event.target.value='';}});

const CUSTOM_TEMPLATE=`# Example: random search using the shared decoder and evaluation budget.\n# context.initial has already used evaluation 1.\n\ndef solve(problem, context, parameters):\n    while True:\n        context.check()\n        genome = problem.random_genome(context.rng)\n        context.evaluate(genome)\n\n    # The runner returns context.best when the budget/time limit is reached.\n`;
try{$('custom-code').value=localStorage.getItem('timetable-lab-custom-code')||CUSTOM_TEMPLATE;}catch{$('custom-code').value=CUSTOM_TEMPLATE;}
$('save-code').addEventListener('click',()=>{try{if(!$('custom-code').value.trim())throw new Error('ยังไม่มีโค้ด');JSON.parse($('custom-parameters').value);localStorage.setItem('timetable-lab-custom-code',$('custom-code').value);$('include-custom').checked=true;queueSummary();$('code-status').textContent='เลือก Custom Python ไว้ในการทดลองแล้ว';}catch(error){banner(error.message);}});
$('code-upload').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>200000)throw new Error('ไฟล์โค้ดใหญ่เกิน 200 KB');$('custom-code').value=await file.text();$('code-status').textContent='เปิดไฟล์แล้ว กดใช้โค้ดนี้เพื่อเลือกในการทดลอง';}catch(error){banner(error.message);}finally{event.target.value='';}});
$('download-code').addEventListener('click',()=>download('custom_algorithm.py',$('custom-code').value,'text/x-python'));
queueSummary();defaultDataset().catch(error=>{banner(error.message);$('dataset-name').textContent='โหลดข้อมูลไม่สำเร็จ';$('run-status').textContent='กรุณาลองโหลด Fall CS อีกครั้ง';});

// Presets (#12): fill every run setting from the tuned parameter file used by the final experiment.
const PRESET_INPUTS=['experiment-name','room-mode','budget','time-limit','start-seed','repeats','hc-patience','sa-acceptance','sa-cooling','ga-population','ga-tournament','ga-elites','ga-crossover','ga-mutation'];
const PRESET_DEFAULTS=Object.fromEntries(PRESET_INPUTS.map(id=>[id,$(id).tagName==='SELECT'?[...$(id).options].find(o=>o.defaultSelected)?.value:$(id).defaultValue]));
let tunedCache=null;
async function tunedParameters(){if(!tunedCache)tunedCache=fetch('../../experiments/tuning/selected-parameters.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json();}).catch(()=>null);return tunedCache;}
function presetValues(tuned){const p=tuned||{},hc=p.hc||{},sa=p.sa||{},ga=p.ga||{};return{'hc-patience':hc.restart_patience,'sa-acceptance':sa.initial_acceptance,'sa-cooling':sa.cooling_rate,'ga-population':ga.population_size,'ga-tournament':ga.tournament_size,'ga-elites':ga.elites,'ga-crossover':ga.crossover_rate,'ga-mutation':ga.mutation_rate};}
async function applyPreset(name){
  const note=$('preset-note');let values={...PRESET_DEFAULTS},message='กลับเป็นค่าเริ่มต้นของเว็บ (พารามิเตอร์ยังไม่จูน)';
  if(name!=='default'){
    const tuned=await tunedParameters();
    if(!tuned){note.textContent='โหลดไฟล์พารามิเตอร์ที่จูนแล้วไม่ได้ (experiments/tuning/selected-parameters.json) จึงไม่เปลี่ยนค่า';return;}
    Object.assign(values,presetValues(tuned),{'room-mode':'weekly','start-seed':'1001'});
    if(name==='quick'){Object.assign(values,{'experiment-name':'Fall CS · ลองเร็ว (พารามิเตอร์ที่จูนแล้ว)',budget:'30','time-limit':'120',repeats:'1'});message='ลองเร็ว: 4 วิธี × 1 seed (1001) งบ 30 พารามิเตอร์ที่จูนแล้ว ใช้เวลาราว 1 นาทีหลังโหลด Python เสร็จ';}
    else{Object.assign(values,{'experiment-name':'Fall CS · Final experiment (docs/protocol.md)',budget:'500','time-limit':'3600',repeats:'30'});message='ตามการทดลองสุดท้าย: 4 วิธี × seed 1001–1030 งบ 500 พารามิเตอร์ที่จูนแล้ว · ในเบราว์เซอร์ใช้เวลาหลายชั่วโมง ถ้าจะทำซ้ำทั้งชุดแนะนำคำสั่ง python3 engine/batch.py ใน README';}
  }
  for(const id of PRESET_INPUTS){if(values[id]!==undefined&&values[id]!==null)$(id).value=String(values[id]);}
  document.querySelectorAll('input[name=algorithm]').forEach(x=>{x.checked=true;});$('include-custom').checked=false;
  document.querySelectorAll('[data-preset]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.preset===name)));
  queueSummary();
  const invalid=PRESET_INPUTS.filter(id=>!$(id).checkValidity());
  note.textContent=invalid.length?`ชุดค่านี้มีช่องที่ไม่ผ่านเกณฑ์ของฟอร์ม: ${invalid.join(', ')}`:message;
}
document.querySelectorAll('[data-preset]').forEach(b=>{b.setAttribute('aria-pressed','false');b.addEventListener('click',()=>applyPreset(b.dataset.preset));});
