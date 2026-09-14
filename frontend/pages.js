async function loadHistory(){
  const rows=await api('/api/history');
  $('historyRows').innerHTML=rows.map(x=>`<tr><td>${esc(new Date(x.created_at).toLocaleString())}</td><td>${esc(x.filename)}</td><td>${Number.isFinite(x.wear_rate)?fmt(x.wear_rate*100)+'%':'—'}</td><td>${esc(modeLabels[x.retrieval_mode] || '舊版分析')}</td><td>${esc(x.status_label || '舊紀錄未保存狀態')}</td></tr>`).join('');
}
async function loadCases(){
  const rows=await api('/api/cases');
  $('databaseCases').innerHTML=rows.map(x=>`<article><b>${esc(x.id)}</b><small>磨耗率 ${fmt(x.wear_rate*100)}% · ${fmt(x.hours_used)} 小時</small><button class="delete-case" data-id="${esc(x.id)}">移除案例</button></article>`).join('');
  document.querySelectorAll('.delete-case').forEach(button=>button.onclick=async()=>{
    if(!confirm(`確定移除案例 ${button.dataset.id}？`))return;
    try{await api(`/api/cases/${encodeURIComponent(button.dataset.id)}`,{method:'DELETE'});await loadCases();}
    catch(error){$('pageError').textContent=error.message;}
  });
}
async function loadSettings(){
  const settings=await api('/api/settings');
  for(const [key,value] of Object.entries(settings)){const input=$('settingsForm').elements.namedItem(key);if(input)input.value=value;}
  await showIndexes();
}
async function showIndexes(){
  const rows=await api('/api/indexes');
  $('indexStatus').textContent=rows.map(x=>`${modeLabels[x.mode]}：${x.indexed_count} 筆已建索引\n${(x.failures||[]).map(f=>`${f.case_id}: ${f.embedding_status}`).join('\n')}`).join('\n\n');
}
document.querySelectorAll('nav button').forEach(button=>button.onclick=async()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===button));
  document.querySelectorAll('.screen').forEach(x=>x.classList.toggle('active',x.id===button.dataset.page));
  $('pageError').textContent='';
  try{if(button.dataset.page==='history')await loadHistory();if(button.dataset.page==='database')await loadCases();if(button.dataset.page==='settings')await loadSettings();}
  catch(error){$('pageError').textContent=error.message;}
});
$('addCase').onclick=()=>{$('caseForm').hidden=!$('caseForm').hidden;};
$('caseForm').onsubmit=async e=>{
  e.preventDefault();const data=new FormData(e.target);data.set('wear_rate',Number(data.get('wear_percent'))/100);data.delete('wear_percent');
  const button=e.target.querySelector('button');button.disabled=true;
  try{await api('/api/cases',{method:'POST',body:data});e.target.reset();e.target.hidden=true;await loadCases();}
  catch(error){$('pageError').textContent=error.message;}finally{button.disabled=false;}
};
$('settingsForm').onsubmit=async e=>{
  e.preventDefault();const raw=Object.fromEntries(new FormData(e.target));
  const settings=Object.fromEntries(Object.entries(raw).map(([key,value])=>[key,key==='retrieval_mode'?value:Number(value)]));settings.top_k=5;
  try{await api('/api/settings',{...jsonPost(settings),method:'PUT'});$('pageError').textContent='設定已儲存，後續分析將使用新門檻。';
    if(!busy){$('retrievalMode').value=settings.retrieval_mode;$('retrievalMode').onchange();}refreshHealth();}
  catch(error){$('pageError').textContent=error.message;}
};
async function maintenance(action){
  ['checkModel','rebuildIndex','evaluate'].forEach(id=>$(id).disabled=true);
  $('maintenanceStatus').textContent='處理中，首次載入或重建可能需要數分鐘…';
  try{
    const mode=$('settingsForm').elements.namedItem('retrieval_mode').value;
    if(action==='evaluate'){
      const report=await api('/api/validate');
      $('evaluationResult').innerHTML='<table><thead><tr><th>模式</th><th>樣本數</th><th>MAE</th><th>RMSE</th><th>狀態</th></tr></thead><tbody>'+Object.entries(report.models).map(([key,value])=>`<tr><td>${esc(modeLabels[key])}</td><td>${value.sample_count??'—'}</td><td>${fmt(value.mae,2)}</td><td>${fmt(value.rmse,2)}</td><td>${esc(value.reason||value.status)}</td></tr>`).join('')+'</tbody></table><p>誤差單位：百分點。相同查詢與候選案例集；未按實體刀具分組。</p>';
      $('maintenanceStatus').textContent=report.all_modes_available?'比較完成。':'部分模式尚未就緒；下表僅比較已完成的模型。';
    }else{
      const result=await api(action==='checkModel'?'/api/models/load':'/api/indexes/rebuild',jsonPost({mode}));
      $('maintenanceStatus').textContent=action==='checkModel'?'模型已就緒。':`索引重建完成：${result.indexed_count} 筆有效、${result.failures.length} 筆排除。`;
    }
    await showIndexes();
  }catch(error){$('maintenanceStatus').textContent=error.message;}
  finally{['checkModel','rebuildIndex','evaluate'].forEach(id=>$(id).disabled=false);refreshHealth();}
}
['checkModel','rebuildIndex','evaluate'].forEach(id=>$(id).onclick=()=>maintenance(id));
