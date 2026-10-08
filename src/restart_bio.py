"""User-authorized reevaluation of unchanged Bio R1, followed by rounds 2–5."""
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
    config_path=ROOT/'config/bio-terra.json'
    config=json.loads(config_path.read_text())
    run=ROOT/'runs/experiments'/config['experiment_id']
    root=run/'evolution/biology'
    folder=root/'biology-round-01'
    candidate=folder/'candidate'
    source=json.loads((folder/'source.json').read_text())
    if bundle_hash(candidate)!=source['candidate_sha256']:
        raise RuntimeError('Candidate changed; cannot reevaluate')
    record=root/'round-01-reevaluation.json'
    state={'status':'running','authorization':'User requested restart based on current implementation',
           'job':'biology-r01-authorized-reevaluation-01','original_job':'biology-r01-search',
           'candidate_sha256':source['candidate_sha256'],'started_at':datetime.now(timezone.utc).isoformat()}
    with record.open('x') as f:json.dump(state,f,indent=2)
    def save():record.write_text(json.dumps(state,indent=2)+'\n')
    try:
        subprocess.run([sys.executable,str(ROOT/'src/run_job.py'),'--name',state['job'],
            '--domain','biology','--config',str(config_path),'--bundle',str(candidate),'--attempts','3'],check=True)
        rows=collect(run/'jobs'/state['job'])
        names=[Path(t).name for t in config['domains']['biology']]
        if len(rows)!=6 or any(sum(r['task']==n for r in rows)!=3 for n in names):
            raise RuntimeError('Expected 3 trials per task')
        accept(rows,rows,names)
        proposal=json.loads((folder/'proposer-stdout.json').read_text())
        verdict={'round':1,'job':state['job'],'accepted':True,'rule':'initial_measured_incumbent',
            'passes':sum(r['reward'] for r in rows),'trials':6,'paired_local_improvement':False,
            'proposal':proposal['result'],'diff':(folder/'candidate.diff').read_text(),**source}
        with (folder/'decision.json').open('x') as f:json.dump(verdict,f,indent=2)
        with (root/'history.json').open('x') as f:json.dump([verdict],f,indent=2)
        state.update(status='complete',decision=verdict,finished_at=datetime.now(timezone.utc).isoformat());save()
    except BaseException as error:
        state.update(status='stopped',error_type=type(error).__name__,message=str(error));save();raise
    subprocess.run([sys.executable,str(ROOT/'src/evolve.py'),'--domain','biology',
        '--config',str(config_path),'--resume-after-round1'],check=True)

if __name__=='__main__':main()
