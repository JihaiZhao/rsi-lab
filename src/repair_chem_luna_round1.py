"""User-authorized repair of one pre-model Chem setup failure, followed by rounds 2–5."""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from job_spec import ROOT
from native_bundle import bundle_hash
from codex_evaluation import collect
from evaluation import accept


def main():
    config_path=ROOT/'config/chem-luna.json'
    config=json.loads(config_path.read_text())
    run=ROOT/'runs/experiments'/config['experiment_id']
    root=run/'evolution/chemistry'
    folder=root/'chemistry-round-01'
    candidate=folder/'candidate'
    source=json.loads((folder/'source.json').read_text())
    if bundle_hash(candidate)!=source['candidate_sha256']:
        raise RuntimeError('Candidate changed; cannot reevaluate')
    original='chemistry-r01-search'
    failed='propylene-active-learning__QgqYZAd'
    old=collect(run/'jobs'/original, expected_model='gpt-5.6-luna')
    missing=[r for r in old if r['trial']==failed]
    retained=[r for r in old if r['trial']!=failed]
    if len(old)!=6 or len(missing)!=1 or len(retained)!=5:
        raise RuntimeError('Unexpected original trial set')
    bad=missing[0]
    if bad['reward'] is not None or not bad['exception'] or bad['executed_models']:
        raise RuntimeError('Replacement is restricted to the recorded pre-model setup failure')
    if (Path(bad['path'])/'agent/codex.txt').exists():
        raise RuntimeError('Failed trial has model execution log; refuse replacement')
    names=[Path(t).name for t in config['domains']['chemistry']]
    accept(retained,retained,names)
    record=root/'round-01-reevaluation.json'
    state={'status':'running','authorization':'User explicitly requested completion of missing Propylene trial and continuation',
           'job':'chemistry-r01-propylene-repair-01','original_job':'chemistry-r01-search',
           'candidate_sha256':source['candidate_sha256'],'excluded_trials':[{'job':original,'trial':failed,'reason':'Pre-model runtime installation failure; original record preserved'}],'started_at':datetime.now(timezone.utc).isoformat()}
    with record.open('x') as f:json.dump(state,f,indent=2)
    def save():record.write_text(json.dumps(state,indent=2)+'\n')
    try:
        subprocess.run([sys.executable,str(ROOT/'src/run_job.py'),'--name',state['job'],
            '--domain','chemistry','--config',str(config_path),'--bundle',str(candidate),'--attempts','1','--task','chemistry/sargent-lab/propylene-active-learning'],check=True)
        replacement=collect(run/'jobs'/state['job'], expected_model='gpt-5.6-luna')
        if len(replacement)!=1 or replacement[0]['task']!='propylene-active-learning':
            raise RuntimeError('Expected exactly one replacement Propylene trial')
        rows=retained+replacement
        refs=[{'job':original,'trial':r['trial']} for r in retained]+[{'job':state['job'],'trial':replacement[0]['trial']}]
        names=[Path(t).name for t in config['domains']['chemistry']]
        if len(rows)!=6 or any(sum(r['task']==n for r in rows)!=3 for n in names):
            raise RuntimeError('Expected 3 trials per task')
        accept(rows,rows,names)
        proposal=json.loads((folder/'proposer-stdout.json').read_text())
        verdict={'round':1,'job':state['job'],'accepted':True,'rule':'initial_measured_incumbent',
            'effective_trial_refs':refs,'excluded_trials':state['excluded_trials'],
            'passes':sum(r['reward'] for r in rows),'trials':6,'paired_local_improvement':False,
            'proposal':proposal['result'],'diff':(folder/'candidate.diff').read_text(),**source}
        with (folder/'decision.json').open('x') as f:json.dump(verdict,f,indent=2)
        with (root/'history.json').open('x') as f:json.dump([verdict],f,indent=2)
        state.update(status='complete',decision=verdict,finished_at=datetime.now(timezone.utc).isoformat());save()
    except BaseException as error:
        state.update(status='stopped',error_type=type(error).__name__,message=str(error));save();raise
    subprocess.run([sys.executable,str(ROOT/'src/evolve.py'),'--domain','chemistry',
        '--config',str(config_path),'--resume-after-round1'],check=True)

if __name__=='__main__':main()
