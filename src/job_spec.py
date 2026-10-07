"""Build configurations only. No evaluation, model call, download or subprocess."""
import argparse
import copy
import json
from pathlib import Path
from native_bundle import bundle_hash, validate_bundle

ROOT=Path(__file__).resolve().parents[1]
MODEL='claude-sonnet-5-5'


def build(arm,task,bundle=None,attempts=3):
    task_path=Path(task)
    if task_path.is_absolute() or '..' in task_path.parts:
        raise ValueError('Task must be relative to the official tasks directory')
    if attempts<1:raise ValueError('Attempts must be positive')
    baseline=json.loads((ROOT/'harness/H0/manifest.json').read_text())
    agent=copy.deepcopy(baseline['agent'])
    if agent['model_name']!=MODEL:raise ValueError('H0 model differs from Sonnet 5.5')
    if arm=='candidate':
        if bundle is None:raise ValueError('Candidate requires an explicit archived bundle')
        bundle=Path(bundle).resolve()
        errors=validate_bundle(bundle)
        if errors:raise ValueError('; '.join(errors))
        agent.update(name=None,import_path='native_agent:RSIClaudeCode')
        agent['kwargs'].update(harness_dir=str(bundle),harness_sha256=bundle_hash(bundle))
    elif arm!='baseline':raise ValueError('Unknown arm')
    elif bundle is not None:raise ValueError('Bare H0 must not load a bundle')
    return {'job_name':f'draft-{arm}-{task_path.name}','jobs_dir':str(ROOT/'runs/jobs'),
        'n_attempts':attempts,'n_concurrent_trials':2,'environment':{'type':'docker'},
        'agents':[agent],'tasks':[{'path':str(ROOT/'external/as-bench/tasks'/task_path)}]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm',choices=['baseline','candidate'],required=True)
    parser.add_argument('--task',required=True)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--attempts',type=int,default=3)
    args=parser.parse_args()
    print(json.dumps(build(args.arm,args.task,args.bundle,args.attempts),indent=2))
