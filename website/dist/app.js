const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>x==null?'—':(100*x).toFixed(1)+'%';
const REASONS={
 first_measured_incumbent:'First measured candidate; becomes the version to beat (no claim against the unmeasured native agent).',
 credible_gain:'Accepted: higher pass rate with posterior probability of being better at or above the pre-registered 0.8.',
 unresolved_in_noise_band:'Not accepted: the difference is within one trial of six, and the candidate was neither simpler nor cheaper.',
 in_band_simpler:'Accepted: within the noise band and simpler than the parent.',
 in_band_cheaper_not_more_complex:'Accepted: within the noise band and at least 15% cheaper without added complexity.',
 below_noise_floor_of_best:'Not accepted: more than one trial below the best accepted score.',
 regression:'Not accepted: lower pass rate than the parent.',gain_not_credible:'Not accepted: higher, but not credibly.',
 screened_out:'Stopped after the screening trials against a working parent.',
 gate_failed:'Never evaluated: did not pass the automatic gate after the allowed repairs.',
 critic_rejected:'Never evaluated: rejected by the critic after the allowed repairs.',plan_invalid:'Never evaluated: invalid plan.'};
const passes=(r,task)=>r.trials.filter(t=>t.task.includes(task)).reduce((s,t)=>s+t.reward,0);
const count=(r,task)=>r.trials.filter(t=>t.task.includes(task)).length;
fetch('experiment.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{
 const sel=d.rounds.find(r=>r.round===d.selected_round),model=d.models.policy;
 const total=r=>r.trials.reduce((s,t)=>s+t.reward,0);
 document.getElementById('run-state').textContent=sel?`Selected version · Round ${sel.round} · ${pct(sel.score)}`:'No version selected';
 document.getElementById('run-detail').textContent=sel?`Claude Sonnet 5.5 (${model.effort}) · ${total(sel)} of ${sel.trials.length} trials passed. All displayed trials passed the model audit.`:'';
 document.getElementById('score-chart').innerHTML=d.rounds.map(r=>r.trials_run?`<div class="bar-row"><span>Round ${r.round}</span><div class="bar-track" role="img" aria-label="${total(r)} of ${r.trials.length} trials passed"><div class="bar-fill${r.accepted?'':' muted'}" style="width:${100*r.score}%"></div></div><span class="bar-value">${total(r)} / ${r.trials.length}</span></div>`:`<div class="bar-row"><span>Round ${r.round}</span><div class="bar-track pending" role="img" aria-label="Not evaluated"></div><span class="bar-value">not run</span></div>`).join('')
  +(d.external_reference?`<div class="external"><div><b>${d.external_reference.reported_percent}%</b><span>External benchmark reference</span></div><p>${esc(d.external_reference.source.replace(/^./,c=>c.toUpperCase()))}. Not run locally and not a paired comparison.</p></div>`:'');
 const tag=r=>r.round===d.selected_round?'<span class="tag kept">Selected</span>':r.accepted?'<span class="tag kept">Accepted</span>':r.trials_run?'<span class="tag discarded">Not accepted</span>':'<span class="tag">Not evaluated</span>';
 document.getElementById('scores').innerHTML=d.rounds.map(r=>`<tr><td>Round ${r.round}</td><td>${r.trials_run?passes(r,'propylene')+' / '+count(r,'propylene'):'—'}</td><td>${r.trials_run?passes(r,'suzuki')+' / '+count(r,'suzuki'):'—'}</td><td>${r.trials_run?total(r)+' / '+r.trials.length:'—'}</td><td>${r.p_superior==null?'—':r.p_superior.toFixed(2)}</td><td>${tag(r)}</td></tr>`).join('');
 document.getElementById('notes').innerHTML=d.notes.map(n=>`<li>${esc(n)}</li>`).join('');
 const tabs=document.getElementById('round-tabs');
 tabs.innerHTML=d.rounds.map(r=>`<button type="button" data-round="${r.round}">Round ${r.round}${r.round===d.selected_round?' · Selected':''}</button>`).join('');
 function attempts(r){return r.attempts.map(a=>`<li><b>Attempt ${a.attempt}</b> · gate ${a.gate_passed?'passed':'failed'}${a.gate_errors.length?': '+esc(a.gate_errors.join('; ')):''}${a.critic?` · critic ${a.critic.approved?'approved':'rejected'}${a.critic.approved?'':': '+esc(a.critic.reasons[0])}`:''}</li>`).join('');}
 function show(n){
  const r=d.rounds.find(r=>r.round===n),p=r.plan||{};
  tabs.querySelectorAll('button').forEach(b=>{const on=Number(b.dataset.round)===n;b.classList.toggle('active',on);b.setAttribute('aria-selected',String(on));});
  const preds=p.predictions?Object.entries(p.predictions.tasks).map(([t,v])=>`${esc(t.split('-')[0])}: predicted <b>${esc(v)}</b>${r.task_rates?`, observed ${passes(r,t.split('-')[0])}/${count(r,t.split('-')[0])}`:''}`).join(' · '):'';
  document.getElementById('round-content').innerHTML=`<div class="round-top"><h3>${esc(r.title)}</h3>${tag(r)}</div><p class="round-summary">${esc(r.summary)}</p>
  <div class="round-facts"><div><h4>Result</h4><p>${r.trials_run?`${total(r)} of ${r.trials.length} trials passed (${pct(r.score)}).`:'No trials were run.'} ${esc(REASONS[r.reason]||r.reason)}${r.recorded_offline?' Decision applied offline after a controller fault; no extra model calls.':''}</p></div>
  <div><h4>Evidence strength</h4><p>${!r.trials_run?'Not evaluated.':r.p_superior==null?'No parent to compare with.':`Posterior probability of beating its parent: ${r.p_superior.toFixed(2)} (parent ${pct(r.incumbent_score)}).`} ${r.tokens_per_trial?`About ${(r.tokens_per_trial/1e6).toFixed(2)}M tokens per trial.`:''}</p></div>
  <div><h4>What changed</h4><p>${esc((r.changed_files||[]).join(', '))} · edit budget ${r.edit_budget} mechanism${r.edit_budget>1?'s':''}</p></div>
  <div><h4>Prediction vs outcome</h4><p>${preds||'—'}</p></div></div>
  ${r.observation?`<p class="footnote">${esc(r.observation)}</p>`:''}
  ${n===d.selected_round?'<a class="data-link" href="selected-harness.md" download>Download the selected harness files</a>':''}
  <details><summary>The proposer's plan and hypotheses</summary><div class="prose"><b>Problem.</b> ${esc(p.problem)}\n\n${(p.edits||[]).map(e=>`<b>${esc(e.component)}</b> (${esc(e.files.join(', '))}). ${esc(e.hypothesis)}`).join('\n\n')}\n\n<b>Regression risk.</b> ${esc(p.regression_risk)}</div></details>
  <details><summary>Gate and critic history (${r.attempts.length} attempt${r.attempts.length===1?'':'s'})</summary><ul class="trial-list">${attempts(r)}</ul></details>
  <details><summary>Exact changes from its parent</summary><pre>${esc(r.diff)}</pre></details>
  ${r.trials.length?`<details><summary>Inspect the ${r.trials.length} scored trials</summary><ul class="trial-list">${r.trials.map(t=>`<li>${esc(t.task)} · ${esc(t.trial)} (${esc(t.job.endsWith('screen')?'screen':'top-up')}): ${t.reward?'Pass':'Fail'}${t.harness_interventions?` · hook intervened ${t.harness_interventions}×`:''}</li>`).join('')}</ul></details>`:''}
  <details><summary>Source fingerprint</summary><pre>candidate ${esc(r.candidate_sha256)}\nparent    ${esc(r.parent_sha256)}</pre></details>`;
 }
 tabs.addEventListener('click',e=>{const b=e.target.closest('button[data-round]');if(b)show(Number(b.dataset.round));});
 show(d.selected_round||d.rounds[0].round);
 document.getElementById('updated').textContent='Snapshot: '+new Date(d.updated_at).toLocaleString('en-US',{timeZone:'UTC'})+' UTC · '+d.experiment_id;
}).catch(()=>{document.getElementById('run-state').textContent='Results unavailable';document.getElementById('run-detail').textContent='Reload to retrieve the published snapshot.';});
