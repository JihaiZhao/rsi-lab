const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
fetch('experiment.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{
 document.getElementById('run-state').textContent='Best retained result · 66.7%';
 document.getElementById('run-detail').textContent='GPT-5.6 Luna (max) · Round 4 · 4 of 6 trials passed. All displayed trials passed the model and effort audit.';
 document.getElementById('score-chart').innerHTML=d.rounds.map(r=>`<div class="bar-row"><span>Round ${r.round}</span><div class="bar-track" role="img" aria-label="${r.passes} of 6 trials passed"><div class="bar-fill" style="width:${100*r.passes/6}%"></div></div><span class="bar-value">${(100*r.passes/6).toFixed(1)}%</span></div>`).join('');
 const taskScore=(r,name)=>r.trials.filter(t=>t.task.toLowerCase().includes(name)).reduce((s,t)=>s+t.reward,0);
 document.getElementById('scores').innerHTML=d.rounds.map(r=>`<tr><td>Round ${r.round}</td><td>${taskScore(r,'propylene')} / 3</td><td>${taskScore(r,'suzuki')} / 3</td><td>${r.passes} / 6</td><td><span class="tag kept">${r.round===4?'Best retained':'Accepted'+(r.round>1?' · amended':'')}</span></td></tr>`).join('');
 const tabs=document.getElementById('round-tabs');
 tabs.innerHTML=d.rounds.map(r=>`<button type="button" data-round="${r.round}">Round ${r.round}${r.round===4?' · Best':''}</button>`).join('');
 function show(n){
  const r=d.rounds.find(r=>r.round===n);
  tabs.querySelectorAll('button').forEach(b=>{b.classList.toggle('active',Number(b.dataset.round)===n);b.setAttribute('aria-pressed',String(Number(b.dataset.round)===n));});
  document.getElementById('round-content').innerHTML=`<h3>${esc(r.title)}</h3><p>${esc(r.summary)}</p><p><b>Starting point:</b> ${esc(r.parent)}. <b>Result:</b> ${r.passes}/6 passes. ${n===4?'Best retained version.':''}</p><p>Only <code>instructions.md</code> changed. The agent follows this guidance while writing and running its own task code; these bundles add no executable tools or standalone skills.</p><p class="footnote">Rounds 2 and 3 were initially rejected under the stricter per-task rule, then accepted when the selection rule changed to total passes improving or tying. Round 4 had already been proposed from Round 1. These are not four consecutive parent-to-child revisions.</p>${n===4?'<a class="data-link" href="selected-instructions.md" download>Download the selected instructions</a>':''}<details><summary>Read the actual instruction file</summary><pre>${esc(r.instructions)}</pre></details><details><summary>See the exact changes from its parent</summary><pre>${esc(r.diff)}</pre></details><details><summary>Inspect the six scored trials</summary><ul class="trial-list">${r.trials.map(t=>`<li>${esc(t.task)} · ${esc(t.trial)}: ${t.reward===1?'Pass':'Fail'}</li>`).join('')}</ul></details><details><summary>Source fingerprint</summary><pre>${esc(r.sha256)}</pre></details>`;
 }
 tabs.addEventListener('click',e=>{const b=e.target.closest('button[data-round]');if(b)show(Number(b.dataset.round));});
 show(d.selected_round);
 document.getElementById('updated').textContent='Snapshot: '+new Date(d.updated_at).toLocaleString('en-US',{timeZone:'UTC'})+' UTC';
}).catch(()=>{document.getElementById('run-state').textContent='Results unavailable';document.getElementById('run-detail').textContent='Reload to retrieve the published snapshot.';});
