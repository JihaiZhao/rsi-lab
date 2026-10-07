"""Fresh same-task repeats after the selected source has been frozen."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from job_spec import ROOT
from native_bundle import bundle_hash

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--domain',choices=['biology','chemistry'],required=True)
    a=p.parse_args()
    selected=json.loads((ROOT/'runs/evolution'/a.domain/'selected.json').read_text())
    bundle=Path(selected['bundle']) if selected['bundle'] else ROOT/'harness/working'
    if bundle_hash(bundle)!=selected['sha256']:
        raise RuntimeError('Selected source changed after freezing')
    if (ROOT/'runs/domain-stops'/f'{a.domain}.json').exists():
        raise RuntimeError('Domain has a stop record; no automatic re-evaluation')
    protocol=json.loads((ROOT/'config/experiment.json').read_text())
    for arm in ['h0','selected']:
        command=[sys.executable,str(ROOT/'src/run_job.py'),'--name',f'{a.domain}-{arm}-final-01',
            '--domain',a.domain,'--attempts',str(protocol['final_trials_per_task_per_arm'])]
        if arm=='selected' and selected['bundle']:command+=['--bundle',selected['bundle']]
        subprocess.run(command,check=True)
        from evaluation import collect
        rows=collect(ROOT/'runs/jobs'/f'{a.domain}-{arm}-final-01')
        expected=len(protocol['domains'][a.domain])*protocol['final_trials_per_task_per_arm']
        if len(rows)!=expected:
            raise RuntimeError('Final evaluation has missing trials; do not report completion')
        if any(r.get('api_error') or r.get('exception') or r.get('model_audit_error') for r in rows):
            raise RuntimeError('Final evaluation had an execution error; stop without retry')

if __name__=='__main__':main()
