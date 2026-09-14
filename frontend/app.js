const $ = id => document.getElementById(id);
const modeLabels = {dinov2_roi:'DINOv2 ViT-B/14 · YOLO ROI',dinov3_roi:'DINOv3 ViT-B/16 · YOLO ROI',clip_roi:'CLIP · YOLO ROI（比較基準）',clip_full:'CLIP · 完整圖片（比較基準）'};
const fmt = (value, digits=1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let selectedFile, currentAnalysis, objectUrl, busy = false, generation = 0, previousFocus;
async function api(url, options={}) {
  const response = await fetch(url, options);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `請求失敗（${response.status}），請確認輸入及服務狀態。`);
  return result;
}
const jsonPost = body => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function updateWearGauge(value) {
  const available = Number.isFinite(value);
  const percent = available ? Math.min(100, Math.max(0, value)) : 0;
  $('rate').textContent = fmt(value);
  $('wearArc').setAttribute('stroke-dasharray', `${percent} ${100 - percent}`);
  $('wearGauge').setAttribute('aria-label', available ? `預估磨耗率：${fmt(value)}%` : '預估磨耗率：尚無可用結果');
}
function clearResults() {
  generation++;
  currentAnalysis = undefined;
  updateWearGauge(null);
  ['rate','similarity','wearStd','wearLevel','availability','recommendation'].forEach(id => $(id).textContent='—');
  $('caseCount').textContent='— / 5';
  $('statusBadge').textContent='尚未分析'; $('statusBadge').className='status-badge';
  $('cases').replaceChildren(Object.assign(document.createElement('p'),{textContent:'尚無檢索結果',className:'muted'}));
  $('topKSummary').textContent='完成分析後可展開查看'; $('topKDetails').open=false;
  $('reasons').replaceChildren(Object.assign(document.createElement('li'),{textContent:'完成分析後顯示品質檢查與判讀原因。'}));
  for (const id of ['detection']) { $(id).removeAttribute('src'); $(id).hidden=true; }
  $('empty').hidden=false;
  $('detectionText').textContent='等待刀具偵測';
  $('assistantQuestion').value=''; $('assistantAnswer').textContent='請先完成一次分析。'; $('askAssistant').disabled=true;
  $('progress').textContent='';
  $('analysisConclusion').textContent='完成分析後，這裡會顯示相似案例檢索與磨耗率摘要。';
}
function setBusy(value) {
  busy=value;
  ['choose','clear','file','retrievalMode'].forEach(id => $(id).disabled=value);
  $('analyze').disabled=value || !selectedFile;
}
function showImage(src, alt) {
  if (!src) return;
  previousFocus=document.activeElement;
  $('fullImage').src=src; $('fullImage').alt=alt || '圖片預覽';
  $('imageModal').classList.add('open'); $('imageModal').setAttribute('aria-hidden','false'); $('closeImageModal').focus();
}
function closeImage() {
  $('imageModal').classList.remove('open'); $('imageModal').setAttribute('aria-hidden','true');
  previousFocus?.focus();
}
['original','detection'].forEach(id => { $(id).tabIndex=0; $(id).onclick=()=>showImage($(id).getAttribute('src'),$(id).alt); $(id).onkeydown=e=>{if(e.key==='Enter')$(id).click();}; });
$('closeImageModal').onclick=closeImage;
$('imageModal').onclick=e=>{if(e.target===$('imageModal'))closeImage();};
document.addEventListener('keydown',e=>{if($('imageModal').classList.contains('open')) {if(e.key==='Escape')closeImage(); if(e.key==='Tab'){e.preventDefault();$('closeImageModal').focus();}}});
$('choose').onclick=$('drop').onclick=()=>{if(!busy)$('file').click();};
$('file').onchange=e=>{
  const file=e.target.files[0]; if(!file)return;
  if(file.size>20*1024*1024) {$('progress').textContent='圖片不可超過 20 MB。'; return;}
  clearResults(); selectedFile=file;
  if(objectUrl)URL.revokeObjectURL(objectUrl);
  objectUrl=URL.createObjectURL(file); $('original').src=objectUrl; $('original').hidden=false;
  $('drop').hidden=true; $('filename').textContent=file.name; $('analyze').disabled=false;
};
$('clear').onclick=()=>{
  clearResults(); selectedFile=undefined; $('file').value='';
  if(objectUrl)URL.revokeObjectURL(objectUrl); objectUrl=undefined;
  $('original').removeAttribute('src'); $('original').hidden=true; $('drop').hidden=false;
  $('filename').textContent='尚未選擇圖片'; $('analyze').disabled=true;
};
$('retrievalMode').onchange=()=>{clearResults();$('retrievalLabel').textContent=modeLabels[$('retrievalMode').value];};
function renderResult(result) {
  currentAnalysis=result;
  updateWearGauge(result.predicted_wear_percent);
  $('similarity').textContent=fmt(result.average_similarity,3);
  $('wearStd').textContent=Number.isFinite(result.wear_std_percent) ? `${fmt(result.wear_std_percent)} 百分點` : '—';
  $('caseCount').textContent=`${result.top_k.length} / 5`;
  $('statusBadge').textContent=result.status_label; $('statusBadge').className=`status-badge ${result.status}`;
  $('retrievalLabel').textContent=modeLabels[result.retrieval.mode];
  if(result.annotated_image_url){$('detection').src=result.annotated_image_url;$('detection').hidden=false;$('empty').hidden=true;}
  $('detectionText').textContent=result.tool_class ? `YOLO 類別：${result.tool_class}` : '未偵測到刀具';
  $('wearLevel').textContent=result.assessment.level; $('availability').textContent=result.assessment.availability;
  $('recommendation').textContent=result.assessment.recommendation;
  $('reasons').replaceChildren(...result.reasons.map(reason=>Object.assign(document.createElement('li'),{textContent:reason})));
  $('topKSummary').textContent=`${result.top_k.length} 筆案例 · 點擊圖片可放大`;
  const count = result.top_k.length;
  const model = result.retrieval.model;
  const exclusion = result.excluded_case_ids?.length ? `已排除 ${result.excluded_case_ids.length} 筆自身匹配案例，` : '';
  const estimate = Number.isFinite(result.predicted_wear_percent) ? `加權預估磨耗率為 ${fmt(result.predicted_wear_percent)}%。` : '目前無法估算磨耗率。';
  const retrievalSummary = count ? `${model} ${exclusion}找出 ${count} 個相似案例，${estimate}` : `${model} 未取得有效相似案例，${estimate}`;
  $('analysisConclusion').textContent=`${retrievalSummary} ${result.status_label}。${result.status_reason || ''}`;
  $('cases').replaceChildren(...result.top_k.map(item=>{
    const row=document.createElement('div'); row.className='case-row';
    const button=document.createElement('button'); button.className='case-image-button'; button.setAttribute('aria-label',`放大案例 ${item.case_id}`);
    const image=document.createElement('img');image.src=item.image_url;image.alt=item.case_id;button.append(image);button.onclick=()=>showImage(item.image_url,item.case_id);
    const info=document.createElement('div');info.innerHTML=`<b>#${item.rank}　${esc(item.case_id)}</b><small>相似度 ${fmt(item.similarity,3)}</small>`;
    const rate=document.createElement('strong');rate.textContent=`${fmt(item.wear_percent)}%`;
    row.append(button,info,rate);return row;
  }));
  $('askAssistant').disabled=false;
  $('assistantAnswer').textContent=result.expert_answer ? `${result.expert_answer.answer}（${result.expert_answer.source}）` : '分析完成，可輸入問題。';
}
$('analyze').onclick=async()=>{
  if(!selectedFile||busy)return;
  clearResults();setBusy(true);$('progress').textContent='正在執行偵測與影像檢索；首次建立索引可能需要數分鐘…';
  try{
    const data=new FormData();data.append('image',selectedFile);data.append('mode',$('retrievalMode').value);
    const result=await api('/api/analyze',{method:'POST',body:data});renderResult(result);
    $('progress').textContent=`分析完成 · ${result.status_label}`;
  }catch(error){$('progress').textContent=error.message;$('statusBadge').textContent='分析未完成';}
  finally{setBusy(false);refreshHealth();}
};
$('askAssistant').onclick=async()=>{
  const question=$('assistantQuestion').value.trim();if(!question||!currentAnalysis)return;
  const version=generation, analysisId=currentAnalysis.analysis_id;
  $('askAssistant').disabled=true;$('assistantAnswer').textContent='正在整理本次分析結果…';
  try{
    const result=await api('/api/assistant',jsonPost({question,analysis_id:analysisId}));
    if(version===generation)$('assistantAnswer').textContent=`${result.answer}（${result.source}）`;
  }catch(error){if(version===generation)$('assistantAnswer').textContent=error.message;}
  finally{if(version===generation)$('askAssistant').disabled=false;}
};
async function refreshHealth(){
  try{const health=await api('/api/health');$('serviceStatus').textContent='分析服務已連線';$('modelStatus').textContent=health.model_loaded?'預設模型已載入':'預設模型尚未載入';}
  catch{$('serviceStatus').textContent='服務未連線';$('modelStatus').textContent='請確認後端服務';}
}
async function initialize(){
  clearResults();await refreshHealth();
  try{const settings=await api('/api/settings');$('retrievalMode').value=settings.retrieval_mode;$('retrievalLabel').textContent=modeLabels[settings.retrieval_mode];}
  catch(error){$('progress').textContent=error.message;}
}
initialize();
